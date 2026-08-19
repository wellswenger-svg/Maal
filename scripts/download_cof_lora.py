"""Download optional Flux gel LoRA. Real script lives in gitignored private/."""

from __future__ import annotations

import runpy
from pathlib import Path

_PRIVATE = Path(__file__).resolve().parents[1] / "private" / "download_cof_lora.py"


def main() -> None:
    if not _PRIVATE.is_file():
        raise SystemExit(
            "Extra download script is not in this clone. "
            "Add private/download_cof_lora.py locally."
        )
    runpy.run_path(str(_PRIVATE), run_name="__main__")


if __name__ == "__main__":
    main()
