"""Shared contracts for the AI Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

PlannerPath = Literal["rules", "vlm"]
ProfileName = Literal["draft", "balanced", "quality", "ultra"]
ChannelName = Literal["stable", "beta", "experimental"]


@dataclass
class GenerateRequest:
    """Inbound request from the API adapter (not HTTP-specific)."""

    mode: Literal["img", "vid"]
    prompt: str
    prompt_english: str
    image_bytes: bytes
    negative: Optional[str] = None
    seed: Optional[int] = None
    profile: ProfileName = "balanced"
    channel: ChannelName = "stable"
    allow_beta: bool = False
    # Optional I2V duration override (seconds); mapped to Wan frame length in runner
    video_seconds: Optional[float] = None
    # Developer Mode only — versioned workflow_ref, never set by production UI
    dev_workflow_id: Optional[str] = None


@dataclass
class ExecutionPlan:
    planner_path: PlannerPath
    task_type: str
    confidence: float
    profile: ProfileName = "balanced"
    channel: ChannelName = "stable"
    requires_vlm: bool = False
    intent_task_type: Optional[str] = None  # pre-fallback classification
    targets: list[dict[str, Any]] = field(default_factory=list)
    prompts: dict[str, Any] = field(default_factory=dict)
    perception: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    params_hints: dict[str, Any] = field(default_factory=dict)
    post_hints: list[str] = field(default_factory=list)
    dev_workflow_id: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    vlm_model_id: Optional[str] = None

    def to_meta(self) -> dict[str, Any]:
        return {
            "planner_path": self.planner_path,
            "task_type": self.task_type,
            "intent_task_type": self.intent_task_type or self.task_type,
            "confidence": self.confidence,
            "profile": self.profile,
            "channel": self.channel,
            "requires_vlm": self.requires_vlm,
            "targets": self.targets,
            "prompts": self.prompts,
            "perception": self.perception,
            "identity": self.identity,
            "params_hints": self.params_hints,
            "post_hints": self.post_hints,
            "dev_workflow_id": self.dev_workflow_id,
            "warnings": self.warnings,
            "vlm_model_id": self.vlm_model_id,
        }


@dataclass
class ModelBindResult:
    model_id: str
    tier: Literal["preferred", "compatible", "minimum", "slot", "none"]
    filename: Optional[str] = None


@dataclass
class EngineResult:
    data: bytes
    content_type: str
    kind: Literal["img", "vid"]
    model_label: str
    workflow_ref: str
    plan: ExecutionPlan
    backbone: Optional[ModelBindResult] = None
    recovery_events: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    perception_meta: Optional[dict[str, Any]] = None
