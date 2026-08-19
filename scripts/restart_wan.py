#!/usr/bin/env python3
"""Restart / wake Wan Studio stack from any PC that has this repo clone.

Requires gitignored ``tokens&cmd`` at repo root with:
  render=<Render API key>

Optional:
  gpu_agent=https://…   # if scripts/gpu_agent.py is exposed from the GPU PC

Usage (from repo root):
  python scripts/restart_wan.py              # restart Render API + wake + health
  python scripts/restart_wan.py --wake       # only wake / poll health (no restart)
  python scripts/restart_wan.py --status     # one-shot health check
  python scripts/restart_wan.py --tunnel https://xxxx.trycloudflare.com
  python scripts/restart_wan.py --gpu-restart   # ask GPU agent to bounce Comfy

Does NOT commit secrets. Safe to keep in the shared clone.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOKENS_FILE = REPO_ROOT / "tokens&cmd"
API_HEALTH = "https://wan-studio-api.onrender.com/api/health"
RENDER_API = "https://api.render.com/v1"
# Canonical production service (PRODUCTION_URLS.md)
SERVICE_ID = "srv-d9ot8spt0dsc73bqjv0g"


def _load_tokens() -> dict[str, str]:
    if not TOKENS_FILE.is_file():
        raise SystemExit(
            f"Missing {TOKENS_FILE.name}. Copy it from the GPU/main PC "
            "(gitignored). Need at least: render=<api_key>"
        )
    out: dict[str, str] = {}
    for line in TOKENS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip().lower()] = v.strip()
    return out


def _http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: object | None = None,
    timeout: float = 60.0,
) -> tuple[int, object]:
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = int(resp.status)
            if not raw:
                return code, None
            try:
                return code, json.loads(raw)
            except json.JSONDecodeError:
                return code, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw
        return int(exc.code), payload
    except Exception as exc:
        return 0, {"error": str(exc)}


def restart_render(token: str) -> None:
    print(f"Restarting Render service {SERVICE_ID} …")
    code, payload = _http_json(
        "POST",
        f"{RENDER_API}/services/{SERVICE_ID}/restart",
        token=token,
        timeout=90.0,
    )
    if code not in (200, 202):
        raise SystemExit(f"Render restart failed HTTP {code}: {payload}")
    print("Render restart accepted.")


def list_env_vars(token: str) -> list[dict[str, str]]:
    code, payload = _http_json(
        "GET",
        f"{RENDER_API}/services/{SERVICE_ID}/env-vars?limit=100",
        token=token,
    )
    if code != 200 or not isinstance(payload, list):
        raise SystemExit(f"List env-vars failed HTTP {code}: {payload}")
    out: list[dict[str, str]] = []
    for row in payload:
        ev = row.get("envVar") if isinstance(row, dict) else None
        if isinstance(ev, dict) and "key" in ev:
            item: dict[str, str] = {"key": str(ev["key"])}
            if "value" in ev and ev["value"] is not None:
                item["value"] = str(ev["value"])
            elif ev.get("generateValue"):
                # Keep generateValue entries as-is on rewrite
                item["generateValue"] = True  # type: ignore[assignment]
            else:
                item["value"] = ""
            out.append(item)
    return out


def set_comfy_url(token: str, tunnel_url: str) -> None:
    tunnel_url = tunnel_url.strip().rstrip("/")
    if not re.match(r"^https://[a-zA-Z0-9.-]+", tunnel_url):
        raise SystemExit(f"Invalid tunnel URL: {tunnel_url}")
    print(f"Updating COMFYUI_URL → {tunnel_url}")
    current = list_env_vars(token)
    found = False
    for item in current:
        if item.get("key") == "COMFYUI_URL":
            item["value"] = tunnel_url
            item.pop("generateValue", None)
            found = True
    if not found:
        current.append({"key": "COMFYUI_URL", "value": tunnel_url})
    # PUT replaces the full set — must send every key back.
    code, payload = _http_json(
        "PUT",
        f"{RENDER_API}/services/{SERVICE_ID}/env-vars",
        token=token,
        body=current,
        timeout=90.0,
    )
    if code != 200:
        raise SystemExit(f"Update env-vars failed HTTP {code}: {payload}")
    print("Env vars updated. Triggering deploy …")
    code2, payload2 = _http_json(
        "POST",
        f"{RENDER_API}/services/{SERVICE_ID}/deploys",
        token=token,
        body={"clearCache": "do_not_clear"},
        timeout=90.0,
    )
    if code2 not in (200, 201, 202):
        raise SystemExit(f"Deploy trigger failed HTTP {code2}: {payload2}")
    print("Deploy triggered.")


def fetch_health(timeout: float = 55.0) -> tuple[bool, dict]:
    code, payload = _http_json("GET", API_HEALTH, timeout=timeout)
    if code == 200 and isinstance(payload, dict):
        return True, payload
    return False, payload if isinstance(payload, dict) else {"error": payload, "http": code}


def wake_and_report(*, attempts: int = 12, pause_sec: float = 5.0) -> dict:
    print(f"Waking / polling {API_HEALTH} …")
    last: dict = {}
    for i in range(1, attempts + 1):
        ok, data = fetch_health()
        last = data if isinstance(data, dict) else {"raw": data}
        if ok:
            mongo = "✓" if last.get("mongodb") else "✗"
            comfy = "✓" if last.get("comfyui") else "✗"
            print(
                f"[{i}/{attempts}] API up  mongo {mongo}  comfy {comfy}  "
                f"url={last.get('comfyui_url')}"
            )
            return last
        print(f"[{i}/{attempts}] not ready yet: {last}")
        time.sleep(pause_sec)
    raise SystemExit(f"API did not become healthy. Last: {last}")


def gpu_restart(agent_url: str, secret: str | None) -> None:
    base = agent_url.rstrip("/")
    print(f"Asking GPU agent to restart Comfy: {base}/restart")
    if not secret:
        raise SystemExit(
            "tokens&cmd missing gpu_agent_secret=… "
            "(must match GPU_AGENT_SECRET on the GPU PC)"
        )
    code, payload = _http_json(
        "POST",
        f"{base}/restart",
        body={"secret": secret},
        timeout=120.0,
    )
    if code not in (200, 202):
        raise SystemExit(f"GPU agent restart failed HTTP {code}: {payload}")
    print("GPU agent:", payload)


def main() -> int:
    ap = argparse.ArgumentParser(description="Restart / wake Wan Studio from any clone")
    ap.add_argument("--wake", action="store_true", help="Only wake + poll health")
    ap.add_argument("--status", action="store_true", help="One-shot health check")
    ap.add_argument(
        "--tunnel",
        metavar="URL",
        help="Set Render COMFYUI_URL to this Cloudflare tunnel, then deploy",
    )
    ap.add_argument(
        "--gpu-restart",
        action="store_true",
        help="POST restart to gpu_agent= URL from tokens&cmd",
    )
    ap.add_argument(
        "--no-restart",
        action="store_true",
        help="Skip Render restart (still can update tunnel / wake)",
    )
    args = ap.parse_args()

    if args.status:
        ok, data = fetch_health()
        print(json.dumps(data, indent=2, default=str))
        return 0 if ok else 2

    tokens = _load_tokens()

    if args.gpu_restart:
        agent = tokens.get("gpu_agent") or tokens.get("gpu_agent_url")
        if not agent:
            raise SystemExit(
                "tokens&cmd missing gpu_agent=https://… "
                "(run scripts/gpu_agent.py on the GPU PC and tunnel it)"
            )
        gpu_restart(agent, tokens.get("gpu_agent_secret") or tokens.get("gpu_secret"))

    render = tokens.get("render")
    if not render and not args.wake and not args.gpu_restart:
        raise SystemExit("tokens&cmd missing render=<Render API key>")

    if args.tunnel:
        if not render:
            raise SystemExit("tokens&cmd missing render= (needed for --tunnel)")
        set_comfy_url(render, args.tunnel)
        # Deploy already triggered; skip separate restart unless asked
        wake_and_report(attempts=20, pause_sec=8.0)
        return 0

    if args.wake:
        wake_and_report()
        return 0

    if not args.no_restart:
        if not render:
            raise SystemExit("tokens&cmd missing render=<Render API key>")
        restart_render(render)
        time.sleep(3)

    health = wake_and_report()
    if not health.get("comfyui"):
        print(
            "\nAPI is up but Comfy is ✗.\n"
            "On the GPU PC: start ComfyUI :8188 + cloudflared tunnel,\n"
            "then from this clone:\n"
            "  python scripts/restart_wan.py --tunnel https://YOUR-TUNNEL.trycloudflare.com\n"
            "Or if gpu_agent is running:\n"
            "  python scripts/restart_wan.py --gpu-restart"
        )
        return 3
    print("\nStack looks ready — try Generate again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
