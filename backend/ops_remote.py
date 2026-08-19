"""Remote ops helpers for admin UI (Render restart / tunnel / GPU agent)."""

from __future__ import annotations

import re
from typing import Any, Optional

import httpx

from backend.config import Settings

RENDER_API = "https://api.render.com/v1"


class OpsError(RuntimeError):
    def __init__(self, message: str, *, status: int = 503):
        super().__init__(message)
        self.status = status


def _render_headers(settings: Settings) -> dict[str, str]:
    key = (settings.render_api_key or "").strip()
    if not key:
        raise OpsError(
            "Server restart isn’t configured yet. Add the Render API key on the cloud service, then try again.",
            status=503,
        )
    return {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }


async def restart_render_service(settings: Settings) -> dict[str, Any]:
    sid = (settings.render_service_id or "").strip()
    if not sid:
        raise OpsError("Server restart isn’t configured correctly.", status=500)
    headers = _render_headers(settings)
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            f"{RENDER_API}/services/{sid}/restart",
            headers=headers,
        )
    if r.status_code not in (200, 202):
        raise OpsError(
            "Couldn’t restart the cloud server. Try again in a minute.",
            status=502,
        )
    return {"ok": True, "service_id": sid, "action": "restart"}


async def _list_env_vars(settings: Settings) -> list[dict[str, Any]]:
    sid = settings.render_service_id.strip()
    headers = _render_headers(settings)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f"{RENDER_API}/services/{sid}/env-vars",
            headers=headers,
            params={"limit": 100},
        )
    if r.status_code != 200:
        raise OpsError(
            "Couldn’t read server settings. Try again in a minute.",
            status=502,
        )
    rows = r.json() if isinstance(r.json(), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        ev = row.get("envVar") if isinstance(row, dict) else None
        if not isinstance(ev, dict) or "key" not in ev:
            continue
        item: dict[str, Any] = {"key": str(ev["key"])}
        if ev.get("generateValue"):
            item["generateValue"] = True
        else:
            item["value"] = "" if ev.get("value") is None else str(ev["value"])
        out.append(item)
    return out


async def set_comfyui_url(settings: Settings, tunnel_url: str) -> dict[str, Any]:
    tunnel_url = (tunnel_url or "").strip().rstrip("/")
    if not re.match(r"^https://[a-zA-Z0-9.-]+", tunnel_url):
        raise OpsError(
            "That link doesn’t look right. Paste a full https://… address.",
            status=400,
        )

    sid = settings.render_service_id.strip()
    headers = _render_headers(settings)
    async with httpx.AsyncClient(timeout=90.0) as client:
        # Single-key PUT — never bulk-replace all env vars (wipes blank secrets).
        put = await client.put(
            f"{RENDER_API}/services/{sid}/env-vars/COMFYUI_URL",
            headers=headers,
            json={"value": tunnel_url},
        )
        if put.status_code not in (200, 201):
            raise OpsError(
                "Couldn’t save the tunnel link. Try again in a minute.",
                status=502,
            )
        dep = await client.post(
            f"{RENDER_API}/services/{sid}/deploys",
            headers=headers,
            json={"clearCache": "do_not_clear"},
        )
        if dep.status_code not in (200, 201, 202):
            # Private GitHub repo often makes deploy 404; restart still reloads env.
            rst = await client.post(
                f"{RENDER_API}/services/{sid}/restart",
                headers=headers,
            )
            if rst.status_code not in (200, 202):
                raise OpsError(
                    "Tunnel was saved, but the server update didn’t start. Try Connect again.",
                    status=502,
                )
            return {
                "ok": True,
                "comfyui_url": tunnel_url,
                "action": "env_update_and_restart",
            }
    return {
        "ok": True,
        "comfyui_url": tunnel_url,
        "action": "env_update_and_deploy",
    }


async def restart_gpu_comfy(settings: Settings) -> dict[str, Any]:
    base = (settings.gpu_agent_url or "").strip().rstrip("/")
    secret = (settings.gpu_agent_secret or "").strip()
    if not base:
        raise OpsError(
            "GPU restart isn’t set up yet. Start the GPU helper on your PC first.",
            status=503,
        )
    if not secret:
        raise OpsError("GPU restart isn’t set up yet (missing helper secret).", status=503)
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base}/restart",
            json={"secret": secret},
            headers={"X-Gpu-Secret": secret},
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text[:400]}
    if r.status_code not in (200, 202):
        raise OpsError(
            "Couldn’t reach the GPU helper on your PC. Make sure it’s running, then try again.",
            status=502,
        )
    return {"ok": True, "action": "gpu_restart", "agent": payload}


def ops_capabilities(settings: Settings) -> dict[str, Any]:
    return {
        "restart_api": bool((settings.render_api_key or "").strip()),
        "set_tunnel": bool((settings.render_api_key or "").strip()),
        "restart_comfy": bool(
            (settings.gpu_agent_url or "").strip()
            and (settings.gpu_agent_secret or "").strip()
        ),
        "scrub": True,
        "render_service_id": settings.render_service_id,
        "comfyui_url": settings.comfyui_url,
        "gpu_agent_configured": bool((settings.gpu_agent_url or "").strip()),
    }
