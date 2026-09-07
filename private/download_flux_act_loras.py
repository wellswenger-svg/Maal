"""Download Flux img act LoRAs into Comfy shared loras (generic local names).

Pins:
  - oral_pov -> flux_pov_a_v1.safetensors (getphat POV Blowjob FLUX / bl0j0, 584MB)
  - male_anatomy / hands unchanged

Does not commit weights. See datasets/keep_outfit/GPU_LORA_SWAP_WET_ACT.md
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

OUT = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")

# local_name -> (min_bytes, [(repo, remote), ...])
TARGETS: dict[str, tuple[int, list[tuple[str, str]]]] = {
    # getphat POV Blowjob FLUX — 584MB; HF dump mirror (same SHA as Civitai 678730).
    "flux_pov_a_v1.safetensors": (
        400 * 1024 * 1024,
        [
            ("Muntadher-Saleh/kmk", "bl0j0.safetensors"),
        ],
    ),
    "flux_anatomy_m_v1.safetensors": (
        100 * 1024 * 1024,
        [
            (
                "Chroma111/CivitAI-Archive",
                "824972/922531/DynamicPenisV2_Flux.safetensors",
            ),
            ("wsj1995/LORA", "824972/922531/DynamicPenisV2_Flux.safetensors"),
        ],
    ),
    "flux_hands_detail_v1.safetensors": (
        20 * 1024 * 1024,
        [
            ("FFApartners/Detailed_Hands-000001", "Detailed_Hands-000001.safetensors"),
            ("wsj1995/LORA", "891074/997134/Detailed_Hands-000001.safetensors"),
            ("Weiii722/DetailedHands", "Detailed_Hands-000001.safetensors"),
        ],
    ),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for local_name, (min_bytes, sources) in TARGETS.items():
        dest = OUT / local_name
        if dest.is_file() and dest.stat().st_size >= min_bytes:
            print(f"HAVE {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
            ok += 1
            continue
        got = False
        for repo, remote in sources:
            print(f"GET  {repo} :: {remote} -> {local_name}")
            try:
                cached = hf_hub_download(repo_id=repo, filename=remote)
                shutil.copy2(cached, dest)
                if dest.stat().st_size < min_bytes:
                    dest.unlink(missing_ok=True)
                    print(f"FAIL {local_name}: too small from {repo}")
                    continue
                print(f"OK   {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
                ok += 1
                got = True
                break
            except Exception as exc:
                print(f"FAIL {local_name} via {repo}: {exc}")
        if not got:
            print(f"MISSING {local_name} — download manually and rename (see GPU_LORA_SWAP_WET_ACT.md)")
    return 0 if ok == len(TARGETS) else 1


if __name__ == "__main__":
    sys.exit(main())
