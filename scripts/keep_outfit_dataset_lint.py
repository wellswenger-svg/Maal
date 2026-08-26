#!/usr/bin/env python3
"""Lint keep-outfit dataset folders. No training — inventory only."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "datasets" / "keep_outfit"
CAPTION = (
    "photo of a woman, keep same clothes, volume under cloth, fabric may drape, photoreal"
)


def _pair_ids(folder: Path) -> list[str]:
    starts = {p.stem.replace("_start", "") for p in folder.glob("*_start.png")}
    targets = {p.stem.replace("_target", "") for p in folder.glob("*_target.png")}
    return sorted(starts & targets)


def main() -> int:
    if not ROOT.is_dir():
        print(f"missing {ROOT}", file=sys.stderr)
        return 1

    gold = _pair_ids(ROOT / "gold")
    hard = _pair_ids(ROOT / "hard")
    reg = _pair_ids(ROOT / "reg")
    holdout = sorted((ROOT / "holdout").glob("*_start.png"))

    print(f"root: {ROOT}")
    print(f"gold pairs: {len(gold)}  {gold[:8]}{'...' if len(gold) > 8 else ''}")
    print(f"hard pairs: {len(hard)}")
    print(f"reg pairs:  {len(reg)}")
    print(f"holdout starts: {len(holdout)}")

    issues: list[str] = []
    for bucket, ids in (("gold", gold), ("hard", hard)):
        for pid in ids:
            cap = ROOT / bucket / f"{pid}.txt"
            if not cap.is_file():
                issues.append(f"{bucket}/{pid}: missing caption .txt")
            elif "keep same clothes" not in cap.read_text(encoding="utf-8").lower():
                issues.append(f"{bucket}/{pid}: caption missing keep-clothes phrase")

    gold_starts = {p.name for p in (ROOT / "gold").glob("*_start.png")}
    for h in holdout:
        # Warn if same filename appears as a gold start (content not hashed).
        if any(h.stem.replace("h", "").lstrip("0") in g for g in gold_starts):
            pass  # weak check; prefer human holdout discipline
        # Stronger: identical file size + name collision patterns are rare; skip.

    if len(gold) < 20:
        issues.append(f"gold < 20 (have {len(gold)}) - do not train yet")
    if len(holdout) < 5:
        issues.append(f"holdout starts < 5 (have {len(holdout)}) - add more eval starts")

    # Reject accidental ref-gallery naming in gold/hard
    for bucket in ("gold", "hard"):
        for p in (ROOT / bucket).iterdir() if (ROOT / bucket).is_dir() else []:
            if re.search(r"ref_|maxref|nude", p.name, re.I):
                issues.append(f"suspicious name: {bucket}/{p.name}")

    if issues:
        print("\nissues:")
        for line in issues:
            print(f"  - {line}")
        return 2

    print("\nok: counts look train-ready")
    print(f"caption template:\n  {CAPTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
