"""Download Flux Kontext fluid LoRA into the Comfy shared loras folder.

Primary: Cumifier Kontext v1 (Civitai 1750558) → flux_kontext_fluid_v1.safetensors
  Base: Flux.1 Kontext (instruction edit / img2img) — matches fluid edit_graph=kontext.
Rollback kept on disk:
  - flux_facial_fluid_v1.safetensors (old Flux.1 D Non-Face Altering v2)
  - COF_v6_rollback.safetensors (mawedesign COF v6)

Does not commit weights. Does not generate.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

OUT = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\loras")
LOCAL = "flux_kontext_fluid_v1.safetensors"
EXPECTED_SHA = "e3687deea8cb4b3c034534a9d9c773e16603182d63dd4cf29ff526afe5ee7cac"
MIN_BYTES = 500 * 1024 * 1024

SOURCES = (
    ("Chroma111/CivitAI-Archive", "1750558/1981186/add_cum_000010400.safetensors"),
)

# Keep previous Flux.1 D facial LoRA available as rollback (do not re-download if present).
LEGACY_FACIAL = "flux_facial_fluid_v1.safetensors"
LEGACY_SHA = "e16db828c4c621f12937ef92504e713508f7cf60d792229c03b51795bc1037bb"
LEGACY_SOURCES = (
    ("Keltezaa/cumonfacelorav2", "cumonfacelorav2.safetensors"),
    ("Chroma111/CivitAI-Archive-2", "858262/1032060/cumonfacelorav2.safetensors"),
)

ROLLBACK_SOURCES = (
    (
        "Chroma111/CivitAI-Archive",
        "725999/1576616/cof6-batch6o-d16-n7-b2-lr8-512-768_1024.safetensors",
        "COF_v6_rollback.safetensors",
    ),
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(8 * 1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest().lower()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / LOCAL
    ok = 0

    if dest.exists() and dest.stat().st_size >= MIN_BYTES and _sha256(dest) == EXPECTED_SHA:
        print(f"HAVE {LOCAL} ({dest.stat().st_size // (1024 * 1024)} MB)")
        ok += 1
    else:
        for repo, remote in SOURCES:
            print(f"GET  {repo} :: {remote}")
            try:
                cached = hf_hub_download(repo_id=repo, filename=remote)
                if _sha256(Path(cached)) != EXPECTED_SHA:
                    print("SKIP sha mismatch")
                    continue
                shutil.copy2(cached, dest)
                print(f"OK   {LOCAL} ({dest.stat().st_size // (1024 * 1024)} MB)")
                ok += 1
                break
            except Exception as exc:
                print(f"FAIL {repo}: {exc}")
        else:
            print(f"FAIL {LOCAL}: no source worked")

    # Park legacy Flux.1 D facial if missing (rollback only).
    legacy = OUT / LEGACY_FACIAL
    if legacy.exists() and legacy.stat().st_size > 100_000_000:
        print(f"HAVE {LEGACY_FACIAL} rollback ({legacy.stat().st_size // (1024 * 1024)} MB)")
    else:
        for repo, remote in LEGACY_SOURCES:
            print(f"GET  legacy {repo} :: {remote}")
            try:
                cached = hf_hub_download(repo_id=repo, filename=remote)
                if _sha256(Path(cached)) != LEGACY_SHA:
                    print("SKIP legacy sha mismatch")
                    continue
                shutil.copy2(cached, legacy)
                print(f"OK   {LEGACY_FACIAL} rollback")
                break
            except Exception as exc:
                print(f"FAIL legacy {repo}: {exc}")

    for repo, remote, local_name in ROLLBACK_SOURCES:
        rdest = OUT / local_name
        if rdest.exists() and rdest.stat().st_size > 1_000_000:
            print(f"HAVE {local_name} ({rdest.stat().st_size // (1024 * 1024)} MB)")
            continue
        old = OUT / "COF_v6.safetensors"
        if old.is_file() and old.stat().st_size > 1_000_000:
            shutil.copy2(old, rdest)
            print(f"PARK COF_v6.safetensors -> {local_name}")
            continue
        print(f"GET  {repo} :: {remote}")
        try:
            cached = hf_hub_download(repo_id=repo, filename=remote)
            shutil.copy2(cached, rdest)
            print(f"OK   {local_name} ({rdest.stat().st_size // (1024 * 1024)} MB)")
        except Exception as exc:
            print(f"FAIL {local_name}: {exc}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
