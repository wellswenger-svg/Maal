"""video_i2v.v1 — profiled Wan 2.2 I2V with motion scaffolds + post hooks."""

from __future__ import annotations

from typing import Any, Optional

from backend.ai_engine.registry.workflows import QualityProfile, WorkflowRecord, registry
from backend.ai_engine.workflows.video_i2v.motion import (
    extract_motion_hints,
    frames_for_seconds,
    profile_video_params,
    scaffold_i2v_prompt,
    snap_wan_length,
)
from backend.ai_engine.workflows.video_i2v.lora_stack import resolve_video_lora_stack
from backend.comfy_client import ComfyClient
from backend.config import Settings


async def run_i2v_v1(
    *,
    image_bytes: bytes,
    prompt: str,
    negative: Optional[str],
    seed: Optional[int],
    settings: Settings,
    plan: Any = None,
    backbone: Any = None,
    profile: Any = None,
    workflow: Any = None,
    **_: Any,
) -> tuple[bytes, str, str, str]:
    pname = "balanced"
    if isinstance(profile, str) and profile:
        pname = profile
    elif plan is not None and getattr(plan, "profile", None):
        pname = str(plan.profile)

    params = profile_video_params(pname)
    hints = {}
    if plan is not None:
        hints = dict(getattr(plan, "params_hints", None) or {})

    motion = hints.get("motion") or extract_motion_hints(
        (plan.prompts.get("positive") if plan and plan.prompts else None) or prompt
    )
    user_prompt = prompt
    if plan and getattr(plan, "prompts", None):
        user_prompt = (plan.prompts.get("positive") or prompt or "").strip()
        if bool(getattr(settings, "raw_prompt", True)) and plan.prompts.get("user"):
            user_prompt = (plan.prompts.get("user") or user_prompt).strip()

    final_prompt = scaffold_i2v_prompt(
        user_prompt,
        motion,
        raw_prompt=bool(getattr(settings, "raw_prompt", True)),
    )

    steps = int(hints.get("steps") or params["steps"])
    fps = int(hints.get("fps") or params["fps"])
    cfg = float(hints.get("cfg") or params["cfg"])
    shift = float(hints.get("shift") or params["shift"])
    max_side = int(hints.get("max_side") or params["max_side"])

    video_seconds = hints.get("video_seconds")
    if video_seconds is not None:
        length = frames_for_seconds(float(video_seconds), fps)
    elif hints.get("length") is not None:
        length = snap_wan_length(int(hints["length"]))
    else:
        length = snap_wan_length(int(params["length"]))

    client = ComfyClient(settings)
    # Render has no E:\ models — resolve LoRAs against Comfy's live list.
    available_loras = await client.list_lora_filenames()
    nsfw = bool(motion.get("nsfw"))
    lora_stack = resolve_video_lora_stack(
        settings,
        include_optional=True,
        available_names=available_loras,
        trust_remote=True,
        nsfw=nsfw,
        motion_kinds=list(motion.get("motion_kinds") or []),
    )
    # Keep just enough high-noise to invent a partner/anatomy. Higher fractions
    # (0.42–0.60) rewrite the start face into soft mush — bias low-noise refine.
    kinds_l = [str(k) for k in (motion.get("motion_kinds") or [])]
    oralish = nsfw and ("oral" in kinds_l or "deepthroat" in kinds_l)
    if oralish:
        # Oral LoRAs already rewrite composition — lean harder on low-noise face lock.
        high_noise_fraction = 0.30
    elif nsfw:
        high_noise_fraction = 0.34
    else:
        high_noise_fraction = 0.4
    if nsfw:
        # Mild CFG — high CFG fights the start image and softens the face.
        cfg = min(max(cfg, 3.5), 3.7)
        steps = max(steps, 42)
        # Prefer sharper native resolution for NSFW quality runs.
        if pname in ("quality", "ultra"):
            max_side = max(max_side, 832)
        # Skip deferred RIFE annotation — interpolation softens detail if wired later.
        if plan is not None and params.get("post"):
            params = {**params, "post": [p for p in (params.get("post") or []) if "rife" not in str(p)]}
    # LightX2V is an uncensored nudge only. Draft may use distill step count;
    # quality/balanced/ultra keep full steps so anatomy LoRAs can resolve.
    if lora_stack.lightx2v_active and pname == "draft" and not nsfw:
        from backend.ai_engine.workflows.video_i2v.lora_stack import LIGHTX2V_STEPS

        steps = int(LIGHTX2V_STEPS)

    # Stamp post expectations onto plan for post processor
    if plan is not None:
        plan.params_hints = {
            **hints,
            "motion": motion,
            "i2v_profile": pname,
            "gen_fps": fps,
            "length": length,
            "video_seconds": (
                float(video_seconds) if video_seconds is not None else round(length / fps, 2)
            ),
            "steps": steps,
            "post_video": list(params.get("post") or []),
            "lightx2v_requested": bool(params.get("lightx2v")),
            "comfy_lora_catalog": (
                len(available_loras) if available_loras is not None else None
            ),
            **lora_stack.to_meta(),
        }
        for stage in params.get("post") or []:
            if stage not in plan.post_hints:
                plan.post_hints.append(stage)

    unet_high = settings.wan_unet_high
    unet_low = settings.wan_unet_low
    model_label = f"{unet_high}+{unet_low}"
    if backbone is not None:
        mid = getattr(backbone, "model_id", "") or ""
        fn = getattr(backbone, "filename", None)
        if mid == "video.wan22_ti2v_5b":
            model_label = f"ti2v5b_bind|{unet_high}+{unet_low}"
        elif fn and "high" in str(fn).lower():
            unet_high = str(fn)
            model_label = f"{unet_high}+{unet_low}"
    if params.get("lightx2v") and not lora_stack.lightx2v_active:
        model_label = f"{model_label}|lightx2v_draft_hint"
    suffix = lora_stack.label_suffix()
    if suffix:
        model_label = f"{model_label}|{suffix}"

    data, content_type = await client.generate_video(
        image_bytes,
        final_prompt,
        negative=negative,
        seed=seed,
        width=max_side,
        height=max_side,
        length=length,
        steps=steps,
        cfg=cfg,
        fps=fps,
        shift=shift,
        unet_high=unet_high,
        unet_low=unet_low,
        loras_high=lora_stack.high,
        loras_low=lora_stack.low,
        high_noise_fraction=high_noise_fraction,
    )
    return data, content_type, "vid", model_label


def register() -> None:
    def qp(name: str) -> QualityProfile:
        p = profile_video_params(name)
        return QualityProfile(
            resolution=f"<={p['max_side']}",
            steps=int(p["steps"]),
            cfg=float(p["cfg"]),
            sampler="euler",
            scheduler="simple",
            post_processing=list(p.get("post") or []),
            expected_runtime_sec=int(p["expected_runtime_sec"]),
            vram_mb_estimate=int(p["vram_mb"]),
        )

    profiles = {k: qp(k) for k in ("draft", "balanced", "quality", "ultra")}
    registry.register(
        WorkflowRecord(
            id="video_i2v",
            version="v1",
            task_types=["video.i2v"],
            channel="stable",
            enabled=True,
            beta=False,
            experimental=False,
            preferred_models=["video.wan22_i2v_high_fp8"],
            compatible_models=["video.wan22_ti2v_5b"],
            minimum_models=["video.wan22_ti2v_5b"],
            optional_models=[
                "video.wan22_i2v_low_fp8",
                "video.rife",
                "video.lightx2v_lora",
                "lora.video_lightx2v_unc_high",
                "lora.video_lightx2v_unc_low",
                "lora.video_penislora_high",
                "lora.video_deepthroat_high",
                "lora.video_deepthroat_low",
                "lora.video_dr34ml4y_high",
                "lora.video_dr34ml4y_low",
                "lora.video_cumshot_low",
                "upscale.ultrasharp_4x",
            ],
            vram_mb_estimate=14000,
            estimated_runtime_sec={
                k: profiles[k].expected_runtime_sec for k in profiles
            },
            quality_profiles=profiles,
            dependencies={
                "perception": [],
                "post_default": [],
            },
            fallback_workflow_ref=None,  # never drop to LoRA-less legacy on tunnel blips
            inputs={"image": "required"},
            runner=run_i2v_v1,
        )
    )
