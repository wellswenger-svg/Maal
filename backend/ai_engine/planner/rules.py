"""Rule engine. Extra intent overlays load from gitignored private/ at runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from backend.ai_engine.runtime_overlay import bind_module

if TYPE_CHECKING:
    from backend.ai_engine.schema import GenerateRequest

RULE_CONFIDENCE_THRESHOLD = 0.75


@dataclass
class RuleResult:
    task_type: str
    confidence: float
    bypass_vlm: bool
    warnings: list[str] = field(default_factory=list)
    targets: list[dict[str, Any]] = field(default_factory=list)
    perception: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    post_hints: list[str] = field(default_factory=list)
    params_hints: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


def classify(req: "GenerateRequest") -> RuleResult:
    text = f"{getattr(req, 'prompt_english', '') or ''} {getattr(req, 'prompt', '') or ''}"
    low = text.lower()
    if any(k in low for k in ("upscale", "4k", "8k", "super-res", "super res")):
        return RuleResult("image.upscale", 0.9, True, reason="upscale_pattern")
    if "background" in low and any(k in low for k in ("remove", "cut out", "transparent")):
        return RuleResult("image.bg_remove", 0.85, True, reason="bg_remove_pattern")
    if any(k in low for k in ("animate", "img2vid", "image to video", "i2v", "make a video")):
        return RuleResult("video.i2v", 0.85, True, reason="i2v_pattern")
    return RuleResult("image.img2img", 0.45, False, reason="generic")


def classify_task_type(req: "GenerateRequest") -> tuple[str, float, list[str]]:
    result = classify(req)
    return result.task_type, result.confidence, list(result.warnings)


bind_module("planner_rules", globals())
