"""Legacy Flux img2img — same behavior as pre-engine ComfyClient.generate_image."""

from __future__ import annotations

from typing import Any, Optional

from backend.ai_engine.registry.workflows import QualityProfile, WorkflowRecord, registry
from backend.comfy_client import ComfyClient
from backend.config import Settings


async def run_legacy_img2img(
    *,
    image_bytes: bytes,
    prompt: str,
    negative: Optional[str],
    seed: Optional[int],
    settings: Settings,
    **_: Any,
) -> tuple[bytes, str, str, str]:
    client = ComfyClient(settings)
    data, content_type = await client.generate_image(
        image_bytes, prompt, negative=negative, seed=seed
    )
    return data, content_type, "img", settings.flux_unet


def register() -> None:
    profiles = {
        "draft": QualityProfile(
            resolution="<=1024",
            steps=settings_steps_placeholder(20),
            cfg=1.0,
            sampler="euler",
            scheduler="simple",
            expected_runtime_sec=60,
            vram_mb_estimate=12000,
        ),
        "balanced": QualityProfile(
            resolution="<=1024",
            steps=28,
            cfg=1.0,
            sampler="euler",
            scheduler="simple",
            expected_runtime_sec=120,
            vram_mb_estimate=12000,
        ),
        "quality": QualityProfile(
            resolution="<=1024",
            steps=32,
            cfg=1.0,
            sampler="euler",
            scheduler="simple",
            post_processing=[],
            expected_runtime_sec=180,
            vram_mb_estimate=12000,
        ),
        "ultra": QualityProfile(
            resolution="<=1024",
            steps=40,
            cfg=1.0,
            sampler="euler",
            scheduler="simple",
            expected_runtime_sec=300,
            vram_mb_estimate=14000,
        ),
    }
    registry.register(
        WorkflowRecord(
            id="image_img2img",
            version="v0_legacy",
            task_types=["image.img2img"],
            channel="stable",
            enabled=True,
            beta=False,
            experimental=False,
            preferred_models=["backbone.flux_dev_fp8"],
            compatible_models=["backbone.flux_kontext_dev_fp8"],
            minimum_models=["backbone.flux_dev_fp8"],
            optional_models=["identity.pulid_flux"],
            vram_mb_estimate=12000,
            estimated_runtime_sec={
                "draft": 60,
                "balanced": 120,
                "quality": 180,
                "ultra": 300,
            },
            quality_profiles=profiles,
            dependencies={"perception": [], "post_default": []},
            fallback_workflow_ref=None,
            inputs={"image": "required"},
            runner=run_legacy_img2img,
        )
    )


def settings_steps_placeholder(n: int) -> int:
    return n
