"""Planner facade: Rule Engine first; conditional VLM via planner.default_model slot."""

from __future__ import annotations

from backend.ai_engine.planner import rules, vlm
from backend.ai_engine.schema import ExecutionPlan, GenerateRequest


# Safety net when a task_type is classified but no workflow is enabled yet.
_TASK_FALLBACK = {
    "edit.face_swap": "edit.face",  # beta swap → face edit if beta disabled
    "edit.keep_outfit_reshape": "edit.general_instruction",
}


def plan(req: GenerateRequest, *, available_task_types: set[str] | None = None) -> ExecutionPlan:
    rule = rules.classify(req)
    warnings = list(rule.warnings)
    intent_task = rule.task_type
    task_type = rule.task_type
    confidence = rule.confidence
    planner_path: str = "rules"
    targets = list(rule.targets)
    perception = list(rule.perception)
    identity = dict(rule.identity or {})
    post_hints = list(rule.post_hints)
    params_hints = dict(getattr(rule, "params_hints", None) or {})
    if req.video_seconds is not None and req.mode == "vid":
        try:
            params_hints["video_seconds"] = float(req.video_seconds)
        except (TypeError, ValueError):
            warnings.append("video_seconds_ignored")
    prompts = {
        "user": req.prompt,
        "positive": req.prompt_english or req.prompt,
        "negative": req.negative,
    }
    vlm_model_id = None
    requires_vlm = (not rule.bypass_vlm) or confidence < rules.RULE_CONFIDENCE_THRESHOLD

    if requires_vlm:
        vlm_out = vlm.plan_with_vlm(req, rule)
        if vlm_out is None:
            warnings.append("vlm_unavailable_degraded_to_rules")
            requires_vlm = False
        else:
            planner_path = "vlm"
            vlm_model_id = vlm_out.model_id
            intent_task = vlm_out.task_type
            task_type = vlm_out.task_type
            confidence = vlm_out.confidence
            targets = vlm_out.targets or targets
            perception = vlm_out.perception or perception
            identity = vlm_out.identity or identity
            post_hints = vlm_out.post_hints or post_hints
            prompts = vlm_out.prompts or prompts
            try:
                from backend.config import get_settings

                if get_settings().raw_prompt:
                    user_pos = (req.prompt_english or req.prompt or "").strip()
                    if user_pos:
                        prompts = {
                            **(prompts or {}),
                            "user": req.prompt,
                            "positive": user_pos,
                            "negative": (prompts or {}).get("negative") or req.negative,
                        }
            except Exception:
                pass
            warnings.extend(vlm_out.warnings)
            requires_vlm = False  # already ran
    else:
        requires_vlm = False

    if available_task_types is not None and task_type not in available_task_types:
        fallback = _TASK_FALLBACK.get(task_type, "image.img2img")
        if req.mode == "vid" or task_type == "video.i2v":
            fallback = "video.i2v" if "video.i2v" in available_task_types else fallback
        if fallback in available_task_types:
            warnings.append(f"task_fallback:{task_type}->{fallback}")
            task_type = fallback
        elif "edit.general_instruction" in available_task_types and req.mode == "img":
            warnings.append(f"task_fallback:{task_type}->edit.general_instruction")
            task_type = "edit.general_instruction"
        elif "image.img2img" in available_task_types and req.mode == "img":
            warnings.append(f"task_fallback:{task_type}->image.img2img")
            task_type = "image.img2img"
        elif "video.i2v" in available_task_types:
            warnings.append(f"task_fallback:{task_type}->video.i2v")
            task_type = "video.i2v"

    return ExecutionPlan(
        planner_path=planner_path,  # type: ignore[arg-type]
        task_type=task_type,
        intent_task_type=intent_task,
        confidence=confidence,
        profile=req.profile,
        channel=req.channel,
        requires_vlm=requires_vlm,
        targets=targets,
        prompts=prompts,
        perception=perception,
        identity=identity,
        params_hints=params_hints,
        post_hints=post_hints,
        dev_workflow_id=req.dev_workflow_id,
        warnings=warnings,
        vlm_model_id=vlm_model_id,
    )
