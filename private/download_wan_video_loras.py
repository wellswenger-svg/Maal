#!/usr/bin/env python3
"""Download Wan 2.2 I2V dual-stage LoRAs into the Comfy shared loras folder.

Does not commit weights. Soft-skips anything unavailable on Hugging Face.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

DEFAULT_DIR = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")

# (repo_id, remote_filename_or_path, local_filename)
DOWNLOADS: list[tuple[str, str, str]] = [
    (
        "rzgar/Wan2.2_LightX2V_4Step_Uncensored",
        "Wan2.2_LightX2V_high_n54vv.safetensors",
        "Wan2.2_LightX2V_high_n54vv.safetensors",
    ),
    (
        "rzgar/Wan2.2_LightX2V_4Step_Uncensored",
        "Wan2.2_LightX2V_low_n54vv.safetensors",
        "Wan2.2_LightX2V_low_n54vv.safetensors",
    ),
    (
        "liangwc25/wan-penislora-22-i2v",
        "PENISLORA_22_i2v_HIGH_e320.safetensors",
        "PENISLORA_22_i2v_HIGH_e320.safetensors",
    ),
    (
        "lopi999/Wan2.2-DR34ML4Y-AIO_NSFW-LoRA",
        "DR34ML4Y_I2V_14B_HIGH.safetensors",
        "DR34ML4Y_I2V_14B_HIGH.safetensors",
    ),
    (
        "lopi999/Wan2.2-DR34ML4Y-AIO_NSFW-LoRA",
        "DR34ML4Y_I2V_14B_LOW.safetensors",
        "DR34ML4Y_I2V_14B_LOW.safetensors",
    ),
    (
        "Daxxx3D/Deepthroat_Blowjob_Wan2.2_I2V",
        "jfj-deepthroat-W22-I2V-HN.safetensors",
        "Wan2.2_I2V_Deepthroat_Blowjob_High.safetensors",
    ),
    (
        "Daxxx3D/Deepthroat_Blowjob_Wan2.2_I2V",
        "jfj-deepthroat-W22-I2V-LN.safetensors",
        "Wan2.2_I2V_Deepthroat_Blowjob_Low.safetensors",
    ),
    (
        "onamissiononamission/F4C3SPL4SH-Cumshot-I2V-Wan2.2-Video-LoRa-K3NK",
        "wan22-f4c3spl4sh-154epoc-low-k3nk.safetensors",
        "Cumshot_LoRA.safetensors",
    ),
    # Pose pack (also scripts/download_pose_loras.py)
    # Blink Missionary crashes LoraLoaderModelOnly — use Missionary Sex 14B instead
    (
        "profpeng/wanmissionsex",
        "Wan2.2 - I2V - Missionary Sex - HIGH 14B.safetensors",
        "Wan2.2_I2V_Missionary_HIGH.safetensors",
    ),
    (
        "profpeng/wanmissionsex",
        "Wan2.2 - I2V - Missionary Sex - LOW 14B.safetensors",
        "Wan2.2_I2V_Missionary_LOW.safetensors",
    ),
    (
        "KeyOpening8063587/AssertiveCowgirl",
        "Wan22-I2V-HIGH-Hip_Slammin_Assertive_Cowgirl.safetensors",
        "Wan2.2_I2V_Cowgirl_HIGH.safetensors",
    ),
    (
        "KeyOpening8063587/AssertiveCowgirl",
        "Wan22-I2V-LOW-Hip_Slammin_Assertive_Cowgirl.safetensors",
        "Wan2.2_I2V_Cowgirl_LOW.safetensors",
    ),
    (
        "mega281/lora",
        "Wan2.2 - I2V - Doggy Style - 14B_high_noise.safetensors",
        "Wan2.2_I2V_Doggy_HIGH.safetensors",
    ),
    (
        "mega281/lora",
        "Wan2.2 - I2V - Doggy Style - 14B_low_noise.safetensors",
        "Wan2.2_I2V_Doggy_LOW.safetensors",
    ),
    (
        "Melonhead123/WAN2.2-I2V-Handjob-One-Two-handed",
        "WAN-2.2-I2V-Handjob-HIGH-v1.safetensors",
        "Wan2.2_I2V_Handjob_HIGH.safetensors",
    ),
    (
        "Melonhead123/WAN2.2-I2V-Handjob-One-Two-handed",
        "WAN-2.2-I2V-Handjob-LOW-v1.safetensors",
        "Wan2.2_I2V_Handjob_LOW.safetensors",
    ),
    # Male-partner oral (trigger: "A man appears and she sucks his penis")
    (
        "monkeyhan10/wan-oral",
        "wan2.2-i2v-high-oral-insertion-v1.0.safetensors",
        "Wan2.2_I2V_Oral_Insertion_HIGH.safetensors",
    ),
    (
        "monkeyhan10/wan-oral",
        "wan2.2-i2v-low-oral-insertion-v1.0.safetensors",
        "Wan2.2_I2V_Oral_Insertion_LOW.safetensors",
    ),
    (
        "TenStrip/Wan2.2-I2V_Reveal_Penis",
        "2.2-I2V Reveal Penis_000003000_high_noise.safetensors",
        "Wan2.2_I2V_Reveal_Penis_HIGH.safetensors",
    ),
    (
        "TenStrip/Wan2.2-I2V_Reveal_Penis",
        "2.2-I2V Reveal Penis_000003000_low_noise.safetensors",
        "Wan2.2_I2V_Reveal_Penis_LOW.safetensors",
    ),
]

# Appearance enhancers (rzgar Bernini pack) + optional extras without mirrors.
DOWNLOADS_EXTRA: list[tuple[str, str, str]] = [
    (
        "rzgar/Wan2.2-Bernini-R-Motion-Enhancer-n4w-i2v",
        "female_genitalia_enhancer_high.safetensors",
        "female_genitalia_enhancer_high.safetensors",
    ),
    (
        "rzgar/Wan2.2-Bernini-R-Motion-Enhancer-n4w-i2v",
        "female_genitalia_enhancer_low.safetensors",
        "female_genitalia_enhancer_low.safetensors",
    ),
    (
        "rzgar/Wan2.2-Bernini-R-Motion-Enhancer-n4w-i2v",
        "male_genitalia_enhancer_high.safetensors",
        "male_genitalia_enhancer_high.safetensors",
    ),
    (
        "rzgar/Wan2.2-Bernini-R-Motion-Enhancer-n4w-i2v",
        "male_genitalia_enhancer_low.safetensors",
        "male_genitalia_enhancer_low.safetensors",
    ),
]

MANUAL: list[str] = [
    "CoachBate_PENIS_LoRA.safetensors",
    "SmoothMix_Males.safetensors",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out: Path = args.dir
    out.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Install huggingface_hub: pip install huggingface_hub", file=sys.stderr)
        return 1

    ok, fail = [], []
    for repo, remote, local_name in list(DOWNLOADS) + list(DOWNLOADS_EXTRA):
        dest = out / local_name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            # Re-validate known corrupt truncations (Sex crash: incomplete header).
            try:
                from safetensors import safe_open

                with safe_open(str(dest), framework="pt", device="cpu") as handle:
                    if list(handle.keys()):
                        print(f"HAVE {local_name}")
                        ok.append(local_name)
                        continue
            except Exception:
                print(f"CORRUPT {local_name} — re-download")
        print(f"GET  {repo} :: {remote} -> {local_name}")
        if args.dry_run:
            continue
        try:
            cached = hf_hub_download(repo_id=repo, filename=remote, local_dir=None)
            shutil.copy2(cached, dest)
            print(f"OK   {local_name} ({dest.stat().st_size} bytes)")
            ok.append(local_name)
        except Exception as exc:
            print(f"FAIL {local_name}: {exc}")
            fail.append(local_name)

    print("\n--- checklist ---")
    for name in ok:
        print(f"  [x] {name}")
    for name in fail:
        print(f"  [!] download failed: {name}")
    for name in MANUAL:
        present = (out / name).exists()
        mark = "x" if present else " "
        note = "" if present else " (manual / Civitai — no HF mirror)"
        print(f"  [{mark}] {name}{note}")
    return 0 if not fail else 2


if __name__ == "__main__":
    raise SystemExit(main())
