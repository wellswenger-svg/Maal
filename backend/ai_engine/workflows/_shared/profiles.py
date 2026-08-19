"""Quality profile presets for P1 image edit workflows."""

from __future__ import annotations

from backend.ai_engine.registry.workflows import QualityProfile


# denoise hints live outside QualityProfile (schema is Comfy-oriented); runners read these.
DENOISE_BY_PROFILE: dict[str, float] = {
    "draft": 0.45,
    "balanced": 0.55,
    "quality": 0.65,
    "ultra": 0.75,
}

MAX_SIDE_BY_PROFILE: dict[str, int] = {
    "draft": 768,
    "balanced": 1024,
    "quality": 1024,
    "ultra": 1280,
}


def standard_edit_profiles(
    *,
    post_balanced: list[str] | None = None,
    post_quality: list[str] | None = None,
    post_ultra: list[str] | None = None,
    draft_sec: int = 90,
    balanced_sec: int = 150,
    quality_sec: int = 210,
    ultra_sec: int = 360,
) -> dict[str, QualityProfile]:
    post_b = post_balanced or ["color_match"]
    post_q = post_quality or ["color_match", "face_detailer"]
    post_u = post_ultra or ["color_match", "face_detailer"]
    return {
        "draft": QualityProfile(
            resolution="<=768",
            steps=20,
            cfg=1.0,
            sampler="euler",
            scheduler="simple",
            post_processing=[],
            expected_runtime_sec=draft_sec,
            vram_mb_estimate=11000,
        ),
        "balanced": QualityProfile(
            resolution="<=1024",
            steps=28,
            cfg=1.0,
            sampler="euler",
            scheduler="simple",
            post_processing=list(post_b),
            expected_runtime_sec=balanced_sec,
            vram_mb_estimate=12000,
        ),
        "quality": QualityProfile(
            resolution="<=1024",
            steps=32,
            cfg=1.0,
            sampler="euler",
            scheduler="simple",
            post_processing=list(post_q),
            expected_runtime_sec=quality_sec,
            vram_mb_estimate=13000,
        ),
        "ultra": QualityProfile(
            resolution="<=1280",
            steps=40,
            cfg=1.0,
            sampler="euler",
            scheduler="simple",
            post_processing=list(post_u),
            expected_runtime_sec=ultra_sec,
            vram_mb_estimate=14000,
        ),
    }


def runtime_map(profiles: dict[str, QualityProfile]) -> dict[str, int]:
    return {k: v.expected_runtime_sec for k, v in profiles.items()}
