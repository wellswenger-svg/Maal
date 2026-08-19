#!/usr/bin/env python3
"""Keep Wan GPU stack alive so you can recover from another PC.

Run ON the GPU PC (leave it on / awake). This watchdog:

1. Ensures ComfyUI is up on :8188
2. Ensures a Cloudflare quick tunnel to Comfy; if the URL changes, updates
   Render ``COMFYUI_URL`` automatically
3. Ensures ``gpu_agent`` on :8799 (Restart GPU from Controls / phone)
4. Ensures a second tunnel for the agent; updates Render ``GPU_AGENT_URL``

Requires gitignored ``tokens&cmd`` with at least ``render=<api key>``.
Optional keys (auto-filled on first run if missing):
  gpu_agent_secret=…
  GPU_COMFY_CMD=…   (Windows launch command for Comfy)

Usage:
  python scripts/wan_stack_watchdog.py
  python scripts/wan_stack_watchdog.py --once   # single heal pass

Install at login (PowerShell as user):
  powershell -ExecutionPolicy Bypass -File scripts/install_wan_watchdog_task.ps1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOKENS = REPO / "tokens&cmd"
COMFY_ROOT = Path(r"E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI")
CLOUDFLARED = Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe")
RENDER_API = "https://api.render.com/v1"
SERVICE_ID = "srv-d9ot8spt0dsc73bqjv0g"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)

DEFAULT_COMFY_CMD = (
    f'set TQDM_DISABLE=1&& "{COMFY_ROOT / ".venv" / "Scripts" / "python.exe"}" '
    f'main.py --listen 0.0.0.0 --port 8188'
)


def log(msg: str) -> None:
    print(f"[watchdog] {msg}", flush=True)


def load_tokens() -> dict[str, str]:
    out: dict[str, str] = {}
    if not TOKENS.is_file():
        raise SystemExit(f"Missing {TOKENS}")
    for line in TOKENS.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def upsert_token(key: str, value: str) -> None:
    lines: list[str] = []
    found = False
    if TOKENS.is_file():
        for line in TOKENS.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{key}={value}")
    TOKENS.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def ensure_secrets(tokens: dict[str, str]) -> dict[str, str]:
    if not (tokens.get("gpu_agent_secret") or "").strip():
        secret = secrets.token_urlsafe(24)
        upsert_token("gpu_agent_secret", secret)
        tokens["gpu_agent_secret"] = secret
        log("wrote gpu_agent_secret=… into tokens&cmd")
    if not (tokens.get("GPU_COMFY_CMD") or tokens.get("gpu_comfy_cmd") or "").strip():
        upsert_token("GPU_COMFY_CMD", DEFAULT_COMFY_CMD)
        tokens["GPU_COMFY_CMD"] = DEFAULT_COMFY_CMD
        log("wrote GPU_COMFY_CMD default into tokens&cmd")
    return tokens


def port_open(port: int) -> bool:
    import socket

    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def http_ok(url: str, timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return int(r.status) == 200
    except Exception:
        return False


def _no_window_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _new_console_flags() -> int:
    return int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0))


def ensure_comfy(tokens: dict[str, str]) -> None:
    if http_ok("http://127.0.0.1:8188/system_stats"):
        return
    log("Comfy down — starting…")
    cmd = (
        tokens.get("GPU_COMFY_CMD")
        or tokens.get("gpu_comfy_cmd")
        or DEFAULT_COMFY_CMD
    )
    env = os.environ.copy()
    env["TQDM_DISABLE"] = "1"
    subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(COMFY_ROOT if COMFY_ROOT.is_dir() else REPO),
        env=env,
        creationflags=_new_console_flags(),
    )
    for _ in range(60):
        time.sleep(2)
        if http_ok("http://127.0.0.1:8188/system_stats"):
            log("Comfy is up")
            return
    log("WARNING: Comfy did not become healthy in time")


def _cloudflared_pids_for(target_port: int) -> list[int]:
    """PIDs of cloudflared quick tunnels pointed at 127.0.0.1:port.

    Prefer PowerShell CIM — ``wmic`` is missing/broken on many Win11 installs,
    which made the watchdog think no tunnel existed and spawn duplicates.
    """
    if sys.platform != "win32":
        return []
    needle = f"127.0.0.1:{int(target_port)}"
    # ProcessId|CommandLine per line (CommandLine may contain commas)
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='cloudflared.exe'\" "
        "| ForEach-Object { '{0}|{1}' -f $_.ProcessId, $_.CommandLine }"
    )
    out = ""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            text=True,
            errors="replace",
            creationflags=_no_window_flags(),
        )
    except Exception:
        out = ""
    if not out.strip():
        # Last-resort fallback for older boxes that still have wmic
        try:
            out = subprocess.check_output(
                [
                    "wmic",
                    "process",
                    "where",
                    "name='cloudflared.exe'",
                    "get",
                    "ProcessId,CommandLine",
                    "/FORMAT:LIST",
                ],
                text=True,
                errors="replace",
                creationflags=_no_window_flags(),
            )
        except Exception:
            return []
        pids: list[int] = []
        cur_cmd = ""
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("CommandLine="):
                cur_cmd = line.split("=", 1)[1]
            elif line.startswith("ProcessId="):
                raw = line.split("=", 1)[1].strip()
                if raw.isdigit() and needle in cur_cmd:
                    pids.append(int(raw))
                cur_cmd = ""
        return pids

    pids = []
    for line in out.splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        raw_pid, cmd = line.split("|", 1)
        if raw_pid.isdigit() and needle in cmd:
            pids.append(int(raw_pid))
    return pids


def _kill_cloudflared_for(target_port: int, *, keep_pid: int | None = None) -> None:
    """Kill cloudflared processes for a local port (optionally keep one)."""
    if sys.platform != "win32":
        return
    for cur_pid in _cloudflared_pids_for(target_port):
        if keep_pid is not None and cur_pid == keep_pid:
            continue
        subprocess.run(
            ["taskkill", "/PID", str(cur_pid), "/F"],
            check=False,
            capture_output=True,
            creationflags=_no_window_flags(),
        )
        log(f"killed stale cloudflared pid {cur_pid} (→:{target_port})")


def _dedupe_cloudflared(target_port: int) -> int | None:
    """Ensure at most one tunnel per port. Returns surviving PID (or None)."""
    pids = _cloudflared_pids_for(target_port)
    if not pids:
        return None
    if len(pids) == 1:
        return pids[0]
    # Keep oldest PID — usually the URL already stored on Render.
    keep = min(pids)
    _kill_cloudflared_for(target_port, keep_pid=keep)
    log(f"deduped cloudflared :{target_port} — kept pid {keep}, removed {len(pids) - 1}")
    return keep


def start_quick_tunnel(local_port: int, log_path: Path) -> subprocess.Popen:
    if not CLOUDFLARED.is_file():
        raise SystemExit(f"cloudflared not found at {CLOUDFLARED}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "ab", buffering=0)
    proc = subprocess.Popen(
        [
            str(CLOUDFLARED),
            "tunnel",
            "--url",
            f"http://127.0.0.1:{local_port}",
        ],
        stdout=log_f,
        stderr=subprocess.STDOUT,
        creationflags=_no_window_flags(),
    )
    log(f"started cloudflared -> :{local_port} (pid {proc.pid})")
    return proc


def wait_tunnel_url(log_path: Path, timeout: float = 45.0) -> str | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if log_path.is_file():
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                text = ""
            m = URL_RE.findall(text)
            if m:
                return m[-1].rstrip("/")
        time.sleep(1)
    return None


def render_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def list_env(token: str) -> list[dict]:
    req = urllib.request.Request(
        f"{RENDER_API}/services/{SERVICE_ID}/env-vars?limit=100",
        headers=render_headers(token),
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        rows = json.load(r)
    out: list[dict] = []
    for row in rows if isinstance(rows, list) else []:
        ev = row.get("envVar") if isinstance(row, dict) else None
        if not isinstance(ev, dict) or "key" not in ev:
            continue
        item: dict = {"key": str(ev["key"])}
        if ev.get("generateValue"):
            item["generateValue"] = True
        else:
            item["value"] = "" if ev.get("value") is None else str(ev["value"])
        out.append(item)
    return out


def set_env_and_deploy(token: str, updates: dict[str, str]) -> None:
    """Update only the given keys (safe single-var PUTs) then deploy.

    Never bulk-replace all env vars — Render often returns blank secret values
    on list, and a full PUT would wipe Mongo/Cloudinary/etc.
    """
    changed = False
    for key, value in updates.items():
        value = (value or "").strip()
        if not value:
            continue
        # Skip no-op when we can read the current public value
        try:
            current = {str(i["key"]): i for i in list_env(token)}
            prev = (current.get(key) or {}).get("value")
            if prev == value:
                continue
        except Exception:
            pass
        req = urllib.request.Request(
            f"{RENDER_API}/services/{SERVICE_ID}/env-vars/{key}",
            data=json.dumps({"value": value}).encode(),
            headers=render_headers(token),
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            if int(r.status) not in (200, 201):
                raise RuntimeError(f"env update {key} HTTP {r.status}")
        changed = True
        if key in ("GPU_AGENT_SECRET", "RENDER_API_KEY") or "SECRET" in key.upper() or "TOKEN" in key.upper():
            log(f"Render env {key} -> (set)")
        else:
            log(f"Render env {key} -> {value}")
    if not changed:
        return
    dep = urllib.request.Request(
        f"{RENDER_API}/services/{SERVICE_ID}/deploys",
        data=json.dumps({"clearCache": "do_not_clear"}).encode(),
        headers=render_headers(token),
        method="POST",
    )
    try:
        with urllib.request.urlopen(dep, timeout=90) as r:
            log(f"Render deploy triggered HTTP {r.status}")
    except Exception as exc:
        # Private GitHub repo → Render deploy 404; restart still reloads env vars.
        log(f"Render deploy failed ({exc}); trying service restart…")
        restart = urllib.request.Request(
            f"{RENDER_API}/services/{SERVICE_ID}/restart",
            data=b"",
            headers=render_headers(token),
            method="POST",
        )
        with urllib.request.urlopen(restart, timeout=90) as r:
            log(f"Render restart triggered HTTP {r.status}")


def ensure_tunnel(
    *,
    local_port: int,
    state_key: str,
    render_env_key: str,
    tokens: dict[str, str],
    procs: dict[str, subprocess.Popen],
) -> None:
    log_path = REPO / "tmp_test" / f"tunnel_{local_port}.log"
    state_path = REPO / "tmp_test" / f"tunnel_{local_port}.url"

    known = ""
    if state_path.is_file():
        known = state_path.read_text(encoding="utf-8").strip().rstrip("/")

    api_url = ""
    api_comfy_ok = False
    if local_port == 8188 and http_ok("https://wan-studio-api.onrender.com/api/health", timeout=20):
        try:
            with urllib.request.urlopen(
                "https://wan-studio-api.onrender.com/api/health", timeout=20
            ) as r:
                health = json.load(r)
            api_comfy_ok = bool(health.get("comfyui"))
            api_url = str(health.get("comfyui_url") or "").rstrip("/")
        except Exception:
            pass

    # Only trust the API URL when Comfy is actually reachable through it
    if local_port == 8188 and api_comfy_ok and api_url and http_ok(f"{api_url}/system_stats", timeout=15):
        known = api_url
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(known + "\n", encoding="utf-8")
        log(f"comfy tunnel healthy via API ({known})")
        _dedupe_cloudflared(local_port)
        return

    # Stale quick-tunnel hostname (common after PC sleep / cloudflared restart)
    if known and not http_ok(f"{known}/system_stats" if local_port == 8188 else f"{known}/status", timeout=12):
        log(f"stale tunnel URL for :{local_port} ({known}) — recycling")
        known = ""
        _kill_cloudflared_for(local_port)
        time.sleep(1)

    # Always collapse duplicate quick tunnels for this port
    surviving = _dedupe_cloudflared(local_port)

    proc = procs.get(state_key)
    alive = proc is not None and proc.poll() is None
    unmanaged = surviving is not None

    if (alive or unmanaged) and known:
        # Keep existing healthy tunnel
        pass
    else:
        _kill_cloudflared_for(local_port)
        time.sleep(1)
        if log_path.is_file():
            try:
                log_path.unlink()
            except OSError:
                pass
        procs[state_key] = start_quick_tunnel(local_port, log_path)
        url = wait_tunnel_url(log_path)
        if not url:
            log(f"WARNING: no trycloudflare URL yet for :{local_port}")
            return
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(url + "\n", encoding="utf-8")
        known = url
        log(f"tunnel :{local_port} -> {url}")

    # Refresh known from log if process exists but state file empty
    if not known:
        known = (wait_tunnel_url(log_path, timeout=5.0) or "").rstrip("/")
        if known:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(known + "\n", encoding="utf-8")

    render_tok = (tokens.get("render") or "").strip()
    if not render_tok or not known:
        return
    # Push to Render when API still points at a dead/different hostname
    if local_port == 8188 and api_url == known and api_comfy_ok:
        return
    try:
        updates = {render_env_key: known}
        if render_env_key == "GPU_AGENT_URL":
            updates["GPU_AGENT_SECRET"] = tokens["gpu_agent_secret"]
        set_env_and_deploy(render_tok, updates)
        if render_env_key == "GPU_AGENT_URL":
            upsert_token("gpu_agent", known)
            tokens["gpu_agent"] = known
    except Exception as exc:
        log(f"Render update failed ({render_env_key}): {exc}")


def ensure_gpu_agent(tokens: dict[str, str]) -> None:
    if port_open(8799) and http_ok("http://127.0.0.1:8799/status"):
        return
    log("gpu_agent down — starting…")
    env = os.environ.copy()
    env["GPU_AGENT_SECRET"] = tokens["gpu_agent_secret"]
    env["GPU_COMFY_CMD"] = (
        tokens.get("GPU_COMFY_CMD")
        or tokens.get("gpu_comfy_cmd")
        or DEFAULT_COMFY_CMD
    )
    env["GPU_COMFY_URL"] = "http://127.0.0.1:8188"
    subprocess.Popen(
        [sys.executable, str(REPO / "scripts" / "gpu_agent.py")],
        cwd=str(REPO),
        env=env,
        creationflags=_no_window_flags(),
    )
    for _ in range(20):
        time.sleep(1)
        if http_ok("http://127.0.0.1:8799/status"):
            log("gpu_agent is up")
            return
    log("WARNING: gpu_agent did not become healthy")


def heal_once(tokens: dict[str, str], procs: dict[str, subprocess.Popen]) -> None:
    ensure_comfy(tokens)
    ensure_tunnel(
        local_port=8188,
        state_key="comfy_tunnel",
        render_env_key="COMFYUI_URL",
        tokens=tokens,
        procs=procs,
    )
    ensure_gpu_agent(tokens)
    ensure_tunnel(
        local_port=8799,
        state_key="agent_tunnel",
        render_env_key="GPU_AGENT_URL",
        tokens=tokens,
        procs=procs,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=45)
    args = ap.parse_args()

    tokens = ensure_secrets(load_tokens())
    if not (tokens.get("render") or "").strip():
        raise SystemExit("tokens&cmd needs render=<Render API key>")

    procs: dict[str, subprocess.Popen] = {}
    log("starting heal loop (leave this PC on / awake)")
    while True:
        try:
            heal_once(tokens, procs)
        except Exception as exc:
            log(f"heal error: {exc}")
        if args.once:
            return 0
        time.sleep(max(15, int(args.interval)))


if __name__ == "__main__":
    raise SystemExit(main())
