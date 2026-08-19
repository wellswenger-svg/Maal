"""Factory to register P1 edit workflows without duplicating boilerplate."""

from __future__ import annotations

from typing import Any, Callable, Optional

from backend.ai_engine.registry.workflows import WorkflowRecord, registry
from backend.ai_engine.workflows._shared.edit_runner import make_runner
from backend.ai_engine.workflows._shared.profiles import runtime_map, standard_edit_profiles


def register_edit_workflow(
    *,
    id: str,
    version: str = "v1",
    task_types: list[str],
    task_kind: str,
    preferred_models: list[str],
    compatible_models: list[str],
    minimum_models: list[str],
    optional_models: list[str] | None = None,
    perception: list[str] | None = None,
    post_default: list[str] | None = None,
    fallback_workflow_ref: Optional[str] = None,
    enabled: bool = True,
    beta: bool = False,
    experimental: bool = False,
    channel: str = "stable",
    preprocess: Optional[str] = None,
    denoise_override: Optional[float] = None,
    runner: Optional[Callable[..., Any]] = None,
    post_balanced: list[str] | None = None,
    post_quality: list[str] | None = None,
    post_ultra: list[str] | None = None,
) -> None:
    profiles = standard_edit_profiles(
        post_balanced=post_balanced,
        post_quality=post_quality,
        post_ultra=post_ultra,
    )
    registry.register(
        WorkflowRecord(
            id=id,
            version=version,
            task_types=task_types,
            channel=channel,  # type: ignore[arg-type]
            enabled=enabled,
            beta=beta,
            experimental=experimental,
            preferred_models=preferred_models,
            compatible_models=compatible_models,
            minimum_models=minimum_models,
            optional_models=optional_models or [],
            vram_mb_estimate=12000,
            estimated_runtime_sec=runtime_map(profiles),
            quality_profiles=profiles,
            dependencies={
                "perception": list(perception or []),
                "post_default": list(post_default or []),
            },
            fallback_workflow_ref=fallback_workflow_ref,
            inputs={"image": "required"},
            runner=runner
            or make_runner(
                task_kind,
                preprocess=preprocess,
                denoise_override=denoise_override,
            ),
        )
    )
