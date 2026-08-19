"""Download Flux ControlNet Union Pro (fp8) into the Comfy shared controlnet folder.

Does not commit weights. Prefer Kijai fp8 (~3.1GB) over full bf16 (~6.2GB).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

OUT = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\controlnet")

# (repo_id, remote_filename, local_name)
DOWNLOADS: list[tuple[str, str, str]] = [
    (
        "Kijai/flux-fp8",
        "flux_shakker_labs_union_pro-fp8_e4m3fn.safetensors",
        "flux_shakker_labs_union_pro-fp8_e4m3fn.safetensors",
    ),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for repo, remote, local_name in DOWNLOADS:
        dest = OUT / local_name
        if dest.exists() and dest.stat().st_size > 100_000_000:
            print(f"HAVE {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
            ok += 1
            continue
        print(f"GET  {repo} :: {remote}")
        print(f"  -> {dest}")
        try:
            cached = hf_hub_download(repo_id=repo, filename=remote)
            shutil.copy2(cached, dest)
            print(f"OK   {local_name} ({dest.stat().st_size // (1024 * 1024)} MB)")
            ok += 1
        except Exception as exc:
            print(f"FAIL {local_name}: {exc}")
            # Fallback: full Shakker bf16 (~6.2GB)
            if repo.startswith("Kijai"):
                alt_repo = "Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro"
                alt_remote = "diffusion_pytorch_model.safetensors"
                alt_name = "flux_controlnet_union_pro.safetensors"
                alt_dest = OUT / alt_name
                print(f"FALLBACK {alt_repo} :: {alt_remote}")
                try:
                    cached = hf_hub_download(repo_id=alt_repo, filename=alt_remote)
                    shutil.copy2(cached, alt_dest)
                    print(f"OK   {alt_name} ({alt_dest.stat().st_size // (1024 * 1024)} MB)")
                    ok += 1
                except Exception as exc2:
                    print(f"FAIL {alt_name}: {exc2}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
