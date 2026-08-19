"""
Experimental expansion stubs — design-only registrations (Phase 7).

video_v2v / video_extend ship as experimental so the add-workflow checklist
can be dry-run without affecting stable channel resolution.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.ai_engine.registry.workflows import QualityProfile, WorkflowRecord, registry
from backend.comfy_client import ComfyUIError
from backend.config import Settings


async def _stub_runner(
    *,
    image_bytes: bytes,
    prompt: str,
    negative: Optional[str],
    seed: Optional[int],
    settings: Settings,
    workflow: Any = None,
    **_: Any,
) -> tuple[bytes, str, str, str]:
    ref = getattr(workflow, "workflow_ref", "experimental.stub")
    raise ComfyUIError(
        f"EXPERIMENTAL_STUB: {ref} is registered for channel=experimental only; "
        "graph not implemented. Enable after fixtures pass (WORKFLOWS.md §7)."
    )


def _profiles() -> dict[str, QualityProfile]:
    return {
        name: QualityProfile(
            resolution="<=640",
            steps=steps,
            cfg=3.5,
            sampler="euler",
            scheduler="simple",
            expected_runtime_sec=runtime,
            vram_mb_estimate=14000,
        )
        for name, steps, runtime in (
            ("draft", 12, 300),
            ("balanced", 20, 600),
            ("quality", 28, 1200),
            ("ultra", 36, 2400),
        )
    }


def register() -> None:
    """Checklist dry-run: experimental workflows with full metadata, kill-switch ready."""
    profiles = _profiles()
    runtime = {k: v.expected_runtime_sec for k, v in profiles.items()}

    registry.register(
        WorkflowRecord(
            id="video_v2v",
            version="experimental",
            task_types=["video.v2v"],
            channel="experimental",
            enabled=True,
            beta=False,
            experimental=True,
            preferred_models=["video.wan22_i2v_high_fp8"],
            compatible_models=["video.wan22_ti2v_5b"],
            minimum_models=["video.wan22_ti2v_5b"],
            optional_models=["video.wan22_i2v_low_fp8"],
            vram_mb_estimate=14000,
            estimated_runtime_sec=runtime,
            quality_profiles=profiles,
            dependencies={"perception": [], "post_default": []},
            fallback_workflow_ref="video_i2v.v1",
            inputs={"image": "required", "video": "future"},
            runner=_stub_runner,
            benchmark_score=0,
            benchmark_estimated=True,
        )
    )

    registry.register(
        WorkflowRecord(
            id="video_extend",
            version="experimental",
            task_types=["video.extend"],
            channel="experimental",
            enabled=True,
            beta=False,
            experimental=True,
            preferred_models=["video.wan22_i2v_high_fp8"],
            compatible_models=["video.wan22_ti2v_5b"],
            minimum_models=["video.wan22_ti2v_5b"],
            optional_models=["video.wan22_i2v_low_fp8"],
            vram_mb_estimate=14000,
            estimated_runtime_sec=runtime,
            quality_profiles=profiles,
            dependencies={"perception": [], "post_default": ["rife_16_to_24"]},
            fallback_workflow_ref="video_i2v.v1",
            inputs={"image": "optional", "video": "future"},
            runner=_stub_runner,
            benchmark_score=0,
            benchmark_estimated=True,
        )
    )
