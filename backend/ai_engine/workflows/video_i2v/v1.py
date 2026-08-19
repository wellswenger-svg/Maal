"""video_i2v.v1 — Wan 2.2 I2V. Extra motion overlays load from private/."""

from __future__ import annotations

from typing import Any, Optional

from backend.ai_engine.runtime_overlay import bind_module
from backend.ai_engine.workflows.video_i2v.motion import (
    extract_motion_hints,
    frames_for_seconds,
    profile_video_params,
    scaffold_i2v_prompt,
    snap_wan_length,
)
from backend.ai_engine.workflows.video_i2v.lora_stack import resolve_video_lora_stack
from backend.comfy_client import ComfyClient
from backend.config import Settings


async def run_i2v_v1(
    *,
    image_bytes: bytes,
    prompt: str,
    negative: Optional[str],
    seed: Optional[int],
    settings: Settings,
    plan: Any = None,
    backbone: Any = None,
    profile: Any = None,
    workflow: Any = None,
    **_: Any,
) -> tuple[bytes, str, str, str]:
    pname = "balanced"
    if isinstance(profile, str) and profile:
        pname = profile
    elif plan is not None and getattr(plan, "profile", None):
        pname = str(plan.profile)
    params = profile_video_params(pname)
    hints = dict(getattr(plan, "params_hints", None) or {}) if plan is not None else {}
    motion = hints.get("motion") or extract_motion_hints(
        (plan.prompts.get("positive") if plan and plan.prompts else None) or prompt
    )
    user_prompt = prompt
    if plan and getattr(plan, "prompts", None):
        user_prompt = (plan.prompts.get("positive") or prompt or "").strip()
    final_prompt = scaffold_i2v_prompt(
        user_prompt,
        motion,
        raw_prompt=bool(getattr(settings, "raw_prompt", True)),
    )
    client = ComfyClient(settings)
    lora_stack = resolve_video_lora_stack(
        settings,
        include_optional=True,
        available_names=await client.list_lora_filenames(),
        extra=bool(motion.get("extra")),
        motion_kinds=list(motion.get("motion_kinds") or []),
    )
    raise RuntimeError("Private runtime overlay not installed")


def register() -> None:
    return None


bind_module("video_v1", globals())
