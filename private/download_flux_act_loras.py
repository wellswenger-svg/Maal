"""Download Flux img act LoRAs into Comfy shared loras (generic local names).

Does not commit weights. Remote filenames stay as published; on-disk names are sanitized.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

OUT = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")

# local_name -> (min_bytes, [(repo, remote), ...])
TARGETS: dict[str, tuple[int, list[tuple[str, str]]]] = {
    "flux_pov_a_v1.safetensors": (
        200 * 1024 * 1024,
        [
            ("Chroma111/CivitAI-Archive", "678730/759748/bl0j0.safetensors"),
            ("wsj1995/LORA", "678730/759748/bl0j0.safetensors"),
            ("minaiosu/getphat", "bl0j0.safetensors"),
            ("yoadster/lorasv2", "body/poses/bl0j0.safetensors"),
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
            print(f"MISSING {local_name}")
    return 0 if ok == len(TARGETS) else 1


if __name__ == "__main__":
    sys.exit(main())
