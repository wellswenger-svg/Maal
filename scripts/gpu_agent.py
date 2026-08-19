#!/usr/bin/env python3
"""Tiny control agent for the GPU PC — restart local Comfy from another machine.

Run this ON the machine that hosts ComfyUI (same PC as the tunnel), then expose
it with a second cloudflared quick tunnel (or Tailscale). Put in tokens&cmd on
every clone:

  gpu_agent=https://….trycloudflare.com
  gpu_agent_secret=some-long-random-string

Usage on GPU PC:
  set GPU_AGENT_SECRET=some-long-random-string
  python scripts/gpu_agent.py

  # optional override how Comfy is launched (default: start if port 8188 down)
  set GPU_COMFY_CMD=…your start command…
  set GPU_COMFY_URL=http://127.0.0.1:8188

From any other PC with the repo clone:
  python scripts/restart_wan.py --gpu-restart
  python scripts/restart_wan.py --restart   # also bounce Render API
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("GPU_AGENT_HOST", "0.0.0.0")
PORT = int(os.environ.get("GPU_AGENT_PORT", "8799"))
COMFY_URL = os.environ.get("GPU_COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
SECRET = (
    os.environ.get("GPU_AGENT_SECRET")
    or os.environ.get("GPU_SECRET")
    or ""
).strip()
COMFY_CMD = os.environ.get("GPU_COMFY_CMD", "").strip()
# Default Windows launcher hint when GPU_COMFY_CMD unset — edit to match your setup.
DEFAULT_COMFY_HINT = (
    r"E:\Comfy-Desktop\ComfyUI-Installs\Khelukhiladi\ComfyUI"
)


def _comfy_up() -> bool:
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=3) as r:
            return int(r.status) == 200
    except Exception:
        return False


def _auth_ok(handler: BaseHTTPRequestHandler, body: dict) -> bool:
    if not SECRET:
        # Refuse if no secret configured — do not leave an open restart endpoint.
        return False
    hdr = handler.headers.get("X-Gpu-Secret") or handler.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        hdr = hdr[7:].strip()
    if hdr == SECRET:
        return True
    if str(body.get("secret") or "") == SECRET:
        return True
    return False


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _kill_listeners_on_8188() -> list[str]:
    """Best-effort: stop whatever is bound to Comfy's port (Windows)."""
    notes: list[str] = []
    if sys.platform != "win32":
        notes.append("non-Windows: set GPU_COMFY_CMD to a full restart script")
        return notes
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        notes.append(f"netstat failed: {exc}")
        return notes
    pids: set[str] = set()
    for line in out.splitlines():
        if ":8188" in line and "LISTENING" in line.upper():
            parts = line.split()
            if parts:
                pids.add(parts[-1])
    for pid in pids:
        if not pid.isdigit() or pid == "0":
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", pid, "/F"],
                check=False,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            notes.append(f"killed pid {pid}")
        except Exception as exc:
            notes.append(f"kill {pid} failed: {exc}")
    return notes


def _start_comfy() -> tuple[bool, str]:
    if COMFY_CMD:
        try:
            subprocess.Popen(
                COMFY_CMD,
                shell=True,
                cwd=str(Path(DEFAULT_COMFY_HINT) if Path(DEFAULT_COMFY_HINT).is_dir() else Path.cwd()),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            return True, "started via GPU_COMFY_CMD"
        except Exception as exc:
            return False, f"GPU_COMFY_CMD failed: {exc}"

    root = Path(DEFAULT_COMFY_HINT)
    cand = root / "main.py"
    if cand.is_file():
        try:
            subprocess.Popen(
                [sys.executable, str(cand), "--listen", "127.0.0.1", "--port", "8188"],
                cwd=str(root),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            return True, f"started {cand}"
        except Exception as exc:
            return False, str(exc)
    return (
        False,
        "Set GPU_COMFY_CMD to your Comfy launch command "
        f"(looked under {DEFAULT_COMFY_HINT})",
    )


def restart_comfy() -> dict:
    before = _comfy_up()
    notes = _kill_listeners_on_8188()
    time.sleep(2)
    started, start_msg = _start_comfy()
    notes.append(start_msg)
    # Wait briefly for port
    up = False
    for _ in range(30):
        time.sleep(1)
        if _comfy_up():
            up = True
            break
    return {
        "ok": up,
        "was_up": before,
        "started": started,
        "comfy_up": up,
        "comfy_url": COMFY_URL,
        "notes": notes,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[gpu_agent] " + (fmt % args) + "\n")

    def _send(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("", "/status", "/health"):
            self._send(
                200,
                {
                    "ok": True,
                    "comfy_up": _comfy_up(),
                    "comfy_url": COMFY_URL,
                    "secret_configured": bool(SECRET),
                },
            )
            return
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        body = _read_json(self)
        if self.path.rstrip("/") != "/restart":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not SECRET:
            self._send(
                503,
                {
                    "ok": False,
                    "error": "Set GPU_AGENT_SECRET before exposing this agent",
                },
            )
            return
        if not _auth_ok(self, body):
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        # Run restart off the request thread's critical path but wait for result
        result: dict = {}

        def work() -> None:
            result.update(restart_comfy())

        t = threading.Thread(target=work, daemon=True)
        t.start()
        t.join(timeout=90)
        if t.is_alive():
            self._send(202, {"ok": True, "status": "restart still running"})
            return
        self._send(200 if result.get("ok") else 500, result)


def main() -> int:
    if not SECRET:
        print(
            "WARNING: GPU_AGENT_SECRET is empty — /restart will refuse requests.\n"
            "  set GPU_AGENT_SECRET=… before exposing via cloudflared.",
            file=sys.stderr,
        )
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"GPU agent on http://{HOST}:{PORT}  (Comfy {COMFY_URL})")
    print("Expose with: cloudflared tunnel --url http://127.0.0.1:8799")
    print("Then set tokens&cmd: gpu_agent=<that https url>")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
