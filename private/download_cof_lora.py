"""Download Flux COF (Cum On Flux) LoRAs into the Comfy shared loras folder.

mawedesign COF is trained on whitish translucent splat — not yogurt-white paint.
Does not commit weights.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

OUT = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")
REPO = "Chroma111/CivitAI-Archive"
FILES = (
    (
        "725999/1576616/cof6-batch6o-d16-n7-b2-lr8-512-768_1024.safetensors",
        "COF_v6.safetensors",
    ),
    (
        "725999/1213921/cof5-beta90-dim16-ln7-b2_1300.safetensors",
        "COF_v5.safetensors",
    ),
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for remote, local_name in FILES:
        dest = OUT / local_name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f"HAVE {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
            ok += 1
            continue
        print(f"GET  {REPO} :: {remote}")
        try:
            cached = hf_hub_download(repo_id=REPO, filename=remote)
            shutil.copy2(cached, dest)
            print(f"OK   {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
            ok += 1
        except Exception as exc:
            print(f"FAIL {local_name}: {exc}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
