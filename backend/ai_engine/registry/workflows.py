"""Workflow Registry — versioned workflows, feature flags, model compatibility tiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from backend.ai_engine.schema import ChannelName, ProfileName


@dataclass
class QualityProfile:
    resolution: str
    steps: int
    cfg: float
    sampler: str
    scheduler: str
    post_processing: list[str] = field(default_factory=list)
    expected_runtime_sec: int = 0
    vram_mb_estimate: int = 0


@dataclass
class WorkflowRecord:
    id: str
    version: str
    task_types: list[str]
    channel: ChannelName = "stable"
    enabled: bool = True
    beta: bool = False
    experimental: bool = False
    preferred_models: list[str] = field(default_factory=list)
    compatible_models: list[str] = field(default_factory=list)
    minimum_models: list[str] = field(default_factory=list)
    optional_models: list[str] = field(default_factory=list)
    vram_mb_estimate: int = 0
    estimated_runtime_sec: dict[str, int] = field(default_factory=dict)
    quality_profiles: dict[str, QualityProfile] = field(default_factory=dict)
    dependencies: dict[str, Any] = field(default_factory=dict)
    fallback_workflow_ref: Optional[str] = None
    inputs: dict[str, Any] = field(default_factory=dict)
    # async (request, plan, bindings, settings) -> (bytes, content_type, kind, model_label)
    runner: Optional[Callable[..., Any]] = None
    benchmark_score: int = 0
    benchmark_estimated: bool = True

    @property
    def workflow_ref(self) -> str:
        return f"{self.id}.{self.version}"


class WorkflowRegistry:
    def __init__(self) -> None:
        self._by_ref: dict[str, WorkflowRecord] = {}

    def register(self, record: WorkflowRecord) -> None:
        self._by_ref[record.workflow_ref] = record

    def get(self, workflow_ref: str) -> Optional[WorkflowRecord]:
        return self._by_ref.get(workflow_ref)

    def all(self) -> list[WorkflowRecord]:
        return list(self._by_ref.values())

    def available_task_types(
        self,
        *,
        channel: ChannelName = "stable",
        allow_beta: bool = False,
        allow_experimental: bool = False,
        include_disabled: bool = False,
    ) -> set[str]:
        types: set[str] = set()
        for rec in self._by_ref.values():
            if not self._visible(
                rec,
                channel=channel,
                allow_beta=allow_beta,
                allow_experimental=allow_experimental,
                include_disabled=include_disabled,
            ):
                continue
            types.update(rec.task_types)
        return types

    def resolve(
        self,
        task_type: str,
        *,
        channel: ChannelName = "stable",
        allow_beta: bool = False,
        allow_experimental: bool = False,
        version_pin: Optional[str] = None,
        dev_workflow_id: Optional[str] = None,
        force_dev: bool = False,
    ) -> WorkflowRecord:
        if dev_workflow_id:
            rec = self._by_ref.get(dev_workflow_id)
            if rec is None:
                raise KeyError(f"NO_WORKFLOW: unknown dev_workflow_id={dev_workflow_id}")
            if not rec.enabled and not force_dev:
                raise KeyError(f"NO_WORKFLOW: {dev_workflow_id} is disabled")
            return rec

        candidates = [
            r
            for r in self._by_ref.values()
            if task_type in r.task_types
            and self._visible(
                r,
                channel=channel,
                allow_beta=allow_beta,
                allow_experimental=allow_experimental,
                include_disabled=False,
            )
        ]
        if version_pin:
            pinned = [r for r in candidates if r.version == version_pin]
            candidates = pinned

        if not candidates:
            raise KeyError(f"NO_WORKFLOW: no enabled workflow for task_type={task_type}")

        def sort_key(r: WorkflowRecord) -> tuple:
            # Prefer non-experimental, then highest numeric-ish version, then ref
            exp = 1 if r.experimental or r.version == "experimental" else 0
            ver_num = _version_rank(r.version)
            return (exp, -ver_num, r.workflow_ref)

        candidates.sort(key=sort_key)
        return candidates[0]

    @staticmethod
    def _visible(
        rec: WorkflowRecord,
        *,
        channel: ChannelName,
        allow_beta: bool,
        allow_experimental: bool,
        include_disabled: bool,
    ) -> bool:
        if not include_disabled and not rec.enabled:
            return False
        if rec.experimental and not allow_experimental and channel != "experimental":
            return False
        if rec.beta and not allow_beta and channel not in ("beta", "experimental"):
            return False
        if channel == "stable" and rec.channel == "experimental" and not allow_experimental:
            return False
        return True


def _version_rank(version: str) -> int:
    if version == "experimental":
        return -1
    # v0_legacy -> 0, v1 -> 1, v2 -> 2
    if version.startswith("v") and version[1:2].isdigit():
        digits = ""
        for ch in version[1:]:
            if ch.isdigit():
                digits += ch
            else:
                break
        return int(digits) if digits else 0
    return 0


# Process-wide registry (populated by catalog bootstrap).
registry = WorkflowRegistry()
