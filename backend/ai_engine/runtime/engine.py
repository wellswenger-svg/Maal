"""Execution Engine — resolve workflow, bind models, run with recovery."""

from __future__ import annotations

from typing import Any, Optional

from backend.ai_engine import planner as planner_mod
from backend.ai_engine.models import manager as model_manager
from backend.ai_engine.models.catalog import bootstrap_models, refresh_installed_from_comfy
from backend.ai_engine.perception.pipeline import run_perception
from backend.ai_engine.perception.types import PerceptionArtifacts
from backend.ai_engine.post.pipeline import run_post
from backend.ai_engine.registry.catalog import bootstrap_workflows
from backend.ai_engine.registry.workflows import WorkflowRecord, registry
from backend.ai_engine.runtime import recovery, vram
from backend.ai_engine.schema import EngineResult, ExecutionPlan, GenerateRequest
from backend.comfy_client import ComfyUIError
from backend.config import Settings, get_settings


_booted = False


def _ensure_bootstrapped() -> None:
    global _booted
    if _booted:
        return
    bootstrap_models()
    bootstrap_workflows()
    _booted = True


def _perception_stages(plan: ExecutionPlan, workflow: WorkflowRecord) -> list[str]:
    """Use the planner's detector list only.

    Do not merge workflow defaults. Clothing-replace workflows list SAM2 as a
    dependency, which used to override jobs that set perception=[] and
    then heuristic masks collapsed the edit into LoRA-less img2img.
    """
    del workflow  # planner owns detector selection
    return [s for s in (plan.perception or []) if s]


async def run(req: GenerateRequest, settings: Settings | None = None) -> EngineResult:
    """
    Planner → WorkflowRegistry → ModelManager → runner (with recovery) → PostProcessor
    """
    _ensure_bootstrapped()
    settings = settings or get_settings()
    recovery_events: list[dict[str, Any]] = []
    # Prod has no local COMFYUI_DIR — sync catalog from the tunnel before bind.
    await refresh_installed_from_comfy(settings)

    force_dev = bool(getattr(settings, "ai_engine_dev_mode", False))
    allow_experimental = force_dev or req.channel == "experimental"
    allow_beta = req.allow_beta or req.channel in ("beta", "experimental") or force_dev

    available = registry.available_task_types(
        channel=req.channel,
        allow_beta=allow_beta,
        allow_experimental=allow_experimental,
    )
    plan = planner_mod.plan(req, available_task_types=available)

    try:
        workflow = registry.resolve(
            plan.task_type,
            channel=req.channel,
            allow_beta=allow_beta,
            allow_experimental=allow_experimental,
            dev_workflow_id=plan.dev_workflow_id if force_dev else None,
            force_dev=force_dev,
        )
    except KeyError as exc:
        recovery.record(
            recovery_events,
            kind="resolve_failed",
            detail=str(exc),
            action="abort",
        )
        raise

    result = await _execute_with_recovery(
        req=req,
        plan=plan,
        workflow=workflow,
        settings=settings,
        recovery_events=recovery_events,
        allow_beta=allow_beta,
        allow_experimental=allow_experimental,
    )
    return result


async def _execute_with_recovery(
    *,
    req: GenerateRequest,
    plan: ExecutionPlan,
    workflow: WorkflowRecord,
    settings: Settings,
    recovery_events: list[dict[str, Any]],
    allow_beta: bool,
    allow_experimental: bool,
) -> EngineResult:
    profile = plan.profile
    visited_fallbacks: set[str] = set()
    warnings = list(plan.warnings)
    perception: Optional[PerceptionArtifacts] = None
    perception_meta: Optional[dict[str, Any]] = None

    while True:
        try:
            backbone = model_manager.bind_backbone(workflow)
        except KeyError as exc:
            fb_ref = workflow.fallback_workflow_ref
            if fb_ref and fb_ref not in visited_fallbacks:
                visited_fallbacks.add(fb_ref)
                recovery.record(
                    recovery_events,
                    kind="model_unavailable",
                    detail=str(exc),
                    action=f"fallback:{fb_ref}",
                )
                fb = registry.get(fb_ref)
                if fb is None or not fb.enabled:
                    raise
                workflow = fb
                continue
            recovery.record(
                recovery_events,
                kind="model_unavailable",
                detail=str(exc),
                action="abort",
            )
            raise

        if workflow.runner is None:
            raise RuntimeError(f"Workflow {workflow.workflow_ref} has no runner")

        # Mutate plan profile for this attempt (profiles are advisory in Phase 3 legacy runners)
        plan.profile = profile  # type: ignore[assignment]

        stages = _perception_stages(plan, workflow)
        if stages and perception is None:
            # Temporarily stamp stages onto plan for the perception pipeline
            prior = list(plan.perception)
            plan.perception = stages
            try:
                perception = await run_perception(
                    image_bytes=req.image_bytes,
                    plan=plan,
                    settings=settings,
                )
            finally:
                plan.perception = prior
            perception_meta = perception.to_meta()
            warnings.extend(perception.warnings)
            if "mask_failed" in perception.warnings or "perception_degraded" in perception.warnings:
                warnings.append("edit_may_use_instruction_fallback")

        data: Optional[bytes] = None
        content_type = "application/octet-stream"
        kind = "img"
        model_label = backbone.model_id
        attempt = 0
        last_exc: Optional[BaseException] = None

        while attempt < recovery.MAX_RETRIES:
            attempt += 1
            try:
                data, content_type, kind, model_label = await workflow.runner(
                    image_bytes=req.image_bytes,
                    prompt=(plan.prompts.get("positive") or req.prompt_english or req.prompt).strip(),
                    negative=plan.prompts.get("negative") or req.negative,
                    seed=req.seed,
                    settings=settings,
                    plan=plan,
                    workflow=workflow,
                    backbone=backbone,
                    profile=profile,
                    perception=perception,
                )
                if recovery.is_corrupt_output(data):
                    raise ComfyUIError(
                        f"CORRUPT_OUTPUT: empty or tiny generation result size="
                        f"{0 if not data else len(data)}"
                    )
                # success
                result = EngineResult(
                    data=data,
                    content_type=content_type,
                    kind=kind,  # type: ignore[arg-type]
                    model_label=model_label,
                    workflow_ref=workflow.workflow_ref,
                    plan=plan,
                    backbone=backbone,
                    recovery_events=recovery_events,
                    warnings=warnings,
                    perception_meta=perception_meta,
                )
                result = await run_post(
                    result,
                    workflow,
                    plan,
                    original_bytes=req.image_bytes,
                    perception=perception,
                )
                vram.release_stage("after_success")
                return result

            except BaseException as exc:
                last_exc = exc
                decision = recovery.recover_after_failure(
                    recovery_events,
                    exc,
                    profile=profile,
                    attempt=attempt,
                    fallback_workflow_ref=workflow.fallback_workflow_ref,
                )
                action = decision["action"]

                if action == "retry":
                    await recovery.backoff(attempt)
                    continue

                if action == "degrade":
                    profile = decision["profile"]
                    warnings.append(f"profile_degraded:{plan.profile}->{profile}")
                    plan.profile = profile  # type: ignore[assignment]
                    attempt = 0  # reset retries at new profile
                    vram.release_stage("before_degraded_retry")
                    continue

                if action == "fallback":
                    fb_ref = decision.get("fallback_ref")
                    if fb_ref and fb_ref not in visited_fallbacks:
                        visited_fallbacks.add(fb_ref)
                        fb = registry.get(fb_ref)
                        if fb is not None and fb.enabled and fb.runner is not None:
                            workflow = fb
                            profile = decision.get("profile") or "draft"
                            plan.profile = profile  # type: ignore[assignment]
                            warnings.append(f"workflow_fallback:{fb_ref}")
                            perception = None  # re-run for new workflow deps
                            perception_meta = None
                            break  # outer while: re-bind + run
                    # fall through to abort
                    action = "abort"

                if action == "abort":
                    vram.release_stage("after_abort")
                    if isinstance(last_exc, ComfyUIError):
                        raise last_exc
                    raise ComfyUIError(str(last_exc)) from last_exc

        else:
            # exhausted retries without break
            vram.release_stage("after_retries_exhausted")
            if last_exc:
                if isinstance(last_exc, ComfyUIError):
                    raise last_exc
                raise ComfyUIError(str(last_exc)) from last_exc
            raise ComfyUIError("Generation failed after retries")

        # continued via fallback → loop outer while
        continue


def engine_health(
    *,
    channel: str = "stable",
    allow_beta: bool = False,
    allow_experimental: bool = False,
) -> dict[str, Any]:
    _ensure_bootstrapped()
    from backend.ai_engine.ops.scorecard import disk_footprint_report, workflow_scorecard
    from backend.ai_engine.registry.workflows import registry

    models_h = model_manager.health(
        channel=channel,
        allow_beta=allow_beta,
        allow_experimental=allow_experimental,
    )
    scorecard = workflow_scorecard(
        channel=channel,
        allow_beta=allow_beta,
        allow_experimental=allow_experimental,
    )
    runnable = sum(1 for w in models_h.get("workflows") or [] if w.get("runnable"))
    total_wf = len(models_h.get("workflows") or [])
    missing = int(models_h.get("models_missing") or 0)
    experimental_count = sum(
        1 for w in registry.all() if w.experimental and w.enabled
    )
    return {
        "models": models_h,
        "recovery": {
            "max_retries": recovery.MAX_RETRIES,
            "profiles": ["draft", "balanced", "quality", "ultra"],
        },
        "scorecard": scorecard,
        "disk": disk_footprint_report(),
        "summary": {
            "channel": channel,
            "workflows_runnable": runnable,
            "workflows_listed": total_wf,
            "models_missing": missing,
            "models_installed": int(models_h.get("models_installed") or 0),
            "experimental_registered": experimental_count,
            "footer": (
                f"engine {runnable}/{total_wf} runnable · "
                f"{missing} models missing · "
                f"{experimental_count} experimental"
            ),
        },
    }
