"""Motion hint extraction + I2V prompt scaffolding."""

from __future__ import annotations

from typing import Any

from backend.ai_engine.runtime_overlay import bind_module

POSE_SCAFFOLDS: dict[str, str] = {}
POSE_SEQUENCES: dict[str, str] = {}


def extract_motion_hints(text: str) -> dict[str, Any]:
    t = text or ""
    kinds: list[str] = []
    if "pan" in t.lower():
        kinds.append("pan")
    if "zoom" in t.lower():
        kinds.append("zoom")
    return {
        "extra": False,
        "motion_kinds": kinds,
        "amplitude": "medium",
        "fps": 16,
    }


def scaffold_i2v_prompt(
    user_prompt: str,
    motion: dict[str, Any] | None = None,
    *,
    raw_prompt: bool = True,
) -> str:
    return (user_prompt or "").strip()


def snap_wan_length(raw: int) -> int:
    n = max(1, int(raw))
    return n if n % 4 == 1 else n - (n % 4) + 1


def frames_for_seconds(seconds: float, fps: int = 16) -> int:
    return snap_wan_length(int(round(float(seconds) * int(fps))))


def profile_video_params(profile: str) -> dict[str, Any]:
    return {
        "steps": 20,
        "fps": 16,
        "cfg": 4.0,
        "shift": 8.0,
        "max_side": 720,
        "length": 81,
        "post": [],
        "expected_runtime_sec": 180,
        "vram_mb": 16000,
    }


bind_module("motion", globals())
