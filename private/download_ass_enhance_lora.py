"""Download Flux clothed hip/seat reshape LoRA into Comfy shared loras.

Felldude Skinny Waist & Huge Butt (FLUX) — lower-body volume concept.
Does not commit weights.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

OUT = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")
REPO = "75dhsx/Felldude"
REMOTE = "FLUX_FD-LargeButt-SkinnyWaist-FP8.safetensors"
LOCAL = "FLUX_FD-LargeButt-SkinnyWaist-FP8.safetensors"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / LOCAL
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"HAVE {LOCAL} ({dest.stat().st_size // (1024 * 1024)} MB)")
        return 0
    print(f"GET  {REPO} :: {REMOTE}")
    try:
        cached = hf_hub_download(repo_id=REPO, filename=REMOTE)
        shutil.copy2(cached, dest)
        print(f"OK   {LOCAL} ({dest.stat().st_size // (1024 * 1024)} MB)")
        return 0
    except Exception as exc:
        print(f"FAIL {LOCAL}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
