"""Legacy Wan I2V — same behavior as pre-engine ComfyClient.generate_video."""

from __future__ import annotations

from typing import Any, Optional

from backend.ai_engine.registry.workflows import QualityProfile, WorkflowRecord, registry
from backend.comfy_client import ComfyClient
from backend.config import Settings


async def run_legacy_i2v(
    *,
    image_bytes: bytes,
    prompt: str,
    negative: Optional[str],
    seed: Optional[int],
    settings: Settings,
    **_: Any,
) -> tuple[bytes, str, str, str]:
    client = ComfyClient(settings)
    data, content_type = await client.generate_video(
        image_bytes, prompt, negative=negative, seed=seed
    )
    label = f"{settings.wan_unet_high}+{settings.wan_unet_low}"
    return data, content_type, "vid", label


def register() -> None:
    profiles = {
        "draft": QualityProfile(
            resolution="<=640",
            steps=12,
            cfg=3.5,
            sampler="euler",
            scheduler="simple",
            expected_runtime_sec=240,
            vram_mb_estimate=14000,
        ),
        "balanced": QualityProfile(
            resolution="<=640",
            steps=20,
            cfg=3.5,
            sampler="euler",
            scheduler="simple",
            expected_runtime_sec=600,
            vram_mb_estimate=14000,
        ),
        "quality": QualityProfile(
            resolution="<=640",
            steps=30,
            cfg=3.5,
            sampler="euler",
            scheduler="simple",
            post_processing=[],
            expected_runtime_sec=1200,
            vram_mb_estimate=14000,
        ),
        "ultra": QualityProfile(
            resolution="<=640",
            steps=40,
            cfg=3.5,
            sampler="euler",
            scheduler="simple",
            expected_runtime_sec=2400,
            vram_mb_estimate=14000,
        ),
    }
    registry.register(
        WorkflowRecord(
            id="video_i2v",
            version="v0_legacy",
            task_types=["video.i2v"],
            channel="stable",
            enabled=True,
            beta=False,
            experimental=False,
            preferred_models=["video.wan22_i2v_high_fp8"],
            compatible_models=["video.wan22_ti2v_5b"],
            minimum_models=["video.wan22_ti2v_5b"],
            optional_models=["video.wan22_i2v_low_fp8"],
            vram_mb_estimate=14000,
            estimated_runtime_sec={
                "draft": 240,
                "balanced": 600,
                "quality": 1200,
                "ultra": 2400,
            },
            quality_profiles=profiles,
            dependencies={"perception": [], "post_default": []},
            fallback_workflow_ref=None,
            inputs={"image": "required"},
            runner=run_legacy_i2v,
        )
    )
