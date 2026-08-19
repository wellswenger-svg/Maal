"""Video LoRA stack. Weight filenames load from gitignored private/."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from backend.ai_engine.runtime_overlay import bind_module
from backend.config import Settings

LIGHTX2V_STEPS = 8


@dataclass
class ResolvedLoraStack:
    high: list[tuple[str, float]] = field(default_factory=list)
    low: list[tuple[str, float]] = field(default_factory=list)
    applied_ids: list[str] = field(default_factory=list)
    missing_ids: list[str] = field(default_factory=list)
    lightx2v_active: bool = False


def resolve_video_lora_stack(
    settings: Settings | None = None,
    *,
    include_optional: bool = True,
    available_names: set[str] | list[str] | None = None,
    trust_remote: bool = False,
    extra: bool = False,
    motion_kinds: list[str] | None = None,
    **kwargs: Any,
) -> ResolvedLoraStack:
    return ResolvedLoraStack()


def find_lora_file(
    spec_or_name: Any,
    settings: Settings | None = None,
    available: set[str] | None = None,
) -> Optional[Path]:
    return None


bind_module("lora_stack", globals())
