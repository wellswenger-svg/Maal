"""background_remove.v1 — subject matting via perception (rembg / BiRefNet)."""

from __future__ import annotations

from typing import Any, Optional

from backend.ai_engine.perception import matting
from backend.ai_engine.perception.image_ops import image_to_png_bytes, load_rgb
from backend.ai_engine.registry.workflows import QualityProfile, WorkflowRecord, registry
from backend.config import Settings


async def run_background_remove(
    *,
    image_bytes: bytes,
    prompt: str,
    negative: Optional[str],
    seed: Optional[int],
    settings: Settings,
    plan: Any = None,
    perception: Any = None,
    **_: Any,
) -> tuple[bytes, str, str, str]:
    """
    Return cutout PNG.
    Prefer perception.subject_rgba if already computed; else run matting.
    """
    if perception is not None and getattr(perception, "subject_rgba_png", None):
        return perception.subject_rgba_png, "image/png", "img", "matting.rembg"

    mask, rgba, warnings = matting.matte_subject(image_bytes, settings=settings)
    if rgba is not None:
        model = mask.source if mask.source != "full_frame" else "matting.unavailable"
        return rgba, "image/png", "img", model

    # No alpha available — composite on transparent using mask if present
    if mask and mask.source != "full_frame":
        rgba2 = matting.apply_alpha_cutout(image_bytes, mask.mask_png)
        return rgba2, "image/png", "img", mask.source

    # Absolute last resort: return original RGB (with warning via empty alpha path)
    rgb = load_rgb(image_bytes)
    return image_to_png_bytes(rgb), "image/png", "img", "matting.unavailable"


def register() -> None:
    profiles = {
        "draft": QualityProfile(
            resolution="source",
            steps=0,
            cfg=0.0,
            sampler="none",
            scheduler="none",
            expected_runtime_sec=15,
            vram_mb_estimate=2000,
        ),
        "balanced": QualityProfile(
            resolution="source",
            steps=0,
            cfg=0.0,
            sampler="none",
            scheduler="none",
            post_processing=["edge_refine"],
            expected_runtime_sec=30,
            vram_mb_estimate=3000,
        ),
        "quality": QualityProfile(
            resolution="source",
            steps=0,
            cfg=0.0,
            sampler="none",
            scheduler="none",
            post_processing=["edge_refine"],
            expected_runtime_sec=60,
            vram_mb_estimate=4000,
        ),
        "ultra": QualityProfile(
            resolution="source",
            steps=0,
            cfg=0.0,
            sampler="none",
            scheduler="none",
            post_processing=["edge_refine", "hair_polish"],
            expected_runtime_sec=120,
            vram_mb_estimate=5000,
        ),
    }
    registry.register(
        WorkflowRecord(
            id="background_remove",
            version="v1",
            task_types=["image.background_remove"],
            channel="stable",
            enabled=True,
            beta=False,
            experimental=False,
            preferred_models=["matting.birefnet"],
            compatible_models=["matting.rmbg2", "matting.rembg"],
            minimum_models=["matting.heuristic"],
            optional_models=["matting.rembg"],
            vram_mb_estimate=3000,
            estimated_runtime_sec={
                "draft": 15,
                "balanced": 30,
                "quality": 60,
                "ultra": 120,
            },
            quality_profiles=profiles,
            dependencies={"perception": ["matting"], "post_default": []},
            fallback_workflow_ref="image_img2img.v0_legacy",
            inputs={"image": "required"},
            runner=run_background_remove,
        )
    )
