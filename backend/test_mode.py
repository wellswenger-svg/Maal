"""Test-mode helpers: preset folder ids for reference mapping."""

from __future__ import annotations

import re
from typing import Optional

from backend.ai_engine.runtime_overlay import load_json

PRESET_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def review_bin_map() -> dict[str, str]:
    rows = load_json("review_bins.json") or []
    out: dict[str, str] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict) or row.get("unfiled"):
            continue
        bid = str(row.get("id") or "").strip()
        pid = str(row.get("presetId") or "").strip()
        if bid and pid:
            out[bid] = pid
    return out


# Filled from gitignored private/review_bins.json when present.
REVIEW_BINS = review_bin_map()


def normalize_preset_id(raw: Optional[str]) -> Optional[str]:
    text = str(raw or "").strip().lower()
    if not text:
        return None
    if not PRESET_ID_RE.match(text):
        raise ValueError("Invalid generation folder id")
    return text
