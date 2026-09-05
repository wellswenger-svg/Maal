"""Download Flux wet/sheer clothing LoRAs into Comfy shared loras.

Pins:
  - See through clothes FLUX v2 — civitai.com/models/1028424
  - Wet Clothes/Hair (FLUX) by Lurulf — civitai.com/models/1459149

Does not commit weights. Prefers HuggingFace CivitAI-Archive, then Civitai API.
"""
from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

from huggingface_hub import hf_hub_download

OUT = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")
HF_REPO = "Chroma111/CivitAI-Archive"

# local_name -> (min_bytes, hf_remote_or_None, civitai_url)
TARGETS: dict[str, tuple[int, str | None, str]] = {
    "See_through_clothes_FLUX.safetensors": (
        10 * 1024 * 1024,
        "1028424/1392314/See_through_clothes_FLUX.safetensors",
        "https://civitai.com/api/download/models/1392314?fileId=1294759",
    ),
    # Lurulf Wet Clothes/Hair V1 (replaces WetshirtForFlux for wet_shirt slot)
    "Wet_ClothesHair_FLUX.safetensors": (
        100 * 1024 * 1024,
        "1459149/1650048/Wet_ClothesHair_FLUX.safetensors",
        "https://civitai.com/api/download/models/1650048?fileId=1566446",
    ),
}


def _download_url(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "wan-studio/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for local_name, (min_bytes, hf_remote, civitai_url) in TARGETS.items():
        dest = OUT / local_name
        if dest.is_file() and dest.stat().st_size >= min_bytes:
            print(f"HAVE {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
            ok += 1
            continue
        got = False
        if hf_remote:
            print(f"GET  {HF_REPO} :: {hf_remote} -> {local_name}")
            try:
                cached = hf_hub_download(repo_id=HF_REPO, filename=hf_remote)
                shutil.copy2(cached, dest)
                if dest.stat().st_size >= min_bytes:
                    print(f"OK   {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
                    ok += 1
                    got = True
                else:
                    dest.unlink(missing_ok=True)
                    print(f"FAIL {local_name}: too small from HF")
            except Exception as exc:
                print(f"FAIL {local_name} via HF: {exc}")
        if not got:
            print(f"GET  {civitai_url} -> {local_name}")
            try:
                _download_url(civitai_url, dest)
                if dest.stat().st_size < min_bytes:
                    dest.unlink(missing_ok=True)
                    print(f"FAIL {local_name}: too small (auth/HTML?)")
                else:
                    print(f"OK   {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
                    ok += 1
                    got = True
            except Exception as exc:
                print(f"FAIL {local_name} via Civitai: {exc}")
        if not got:
            print(f"MISSING {local_name}")
    return 0 if ok == len(TARGETS) else 1


if __name__ == "__main__":
    sys.exit(main())
