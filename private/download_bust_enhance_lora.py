"""Download Flux Kontext clothed bust reshape LoRA into Comfy shared loras.

Civitai 1802814 — bigger breasts and butts (Flux Kontext).
Does not commit weights.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

OUT = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")
LOCAL = "flux_kontext_figure_reshape_v1.safetensors"
# Primary Model file on version 2040209 (not the training-data zip)
URL = "https://civitai.com/api/download/models/2040209?fileId=1937100"
MIN_BYTES = 50 * 1024 * 1024


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / LOCAL
    if dest.exists() and dest.stat().st_size >= MIN_BYTES:
        print(f"HAVE {LOCAL} ({dest.stat().st_size // (1024 * 1024)} MB)")
        return 0
    print(f"GET  {URL}")
    try:
        req = urllib.request.Request(
            URL,
            headers={"User-Agent": "wan-studio/1.0"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        if dest.stat().st_size < MIN_BYTES:
            dest.unlink(missing_ok=True)
            print(f"FAIL {LOCAL}: file too small (auth/HTML?)")
            return 1
        print(f"OK   {LOCAL} ({dest.stat().st_size // (1024 * 1024)} MB)")
        return 0
    except Exception as exc:
        print(f"FAIL {LOCAL}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
