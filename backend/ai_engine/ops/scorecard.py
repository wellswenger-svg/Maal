"""
Phase 7 scorecards — estimated until GPU fixtures promote to measured.

Rubric (MODELS.md §2): task fitness 30 + 16GB stability 25 + speed 15
+ license 10 + ecosystem 10 + quality delta 10 = 100.
"""

from __future__ import annotations

from typing import Any

from backend.ai_engine.models.manager import manager as model_manager
from backend.ai_engine.registry.workflows import registry

# model_id -> (score, disk_mb, vram_mb, license)
MODEL_SCORES: dict[str, dict[str, Any]] = {
    "backbone.flux_dev_fp8": {
        "benchmark_score": 74,
        "disk_mb": 12000,
        "vram_mb": 11000,
        "license": "FLUX.1 Non-Commercial (verify)",
        "quantization": "fp8",
    },
    "backbone.flux_kontext_dev_fp8": {
        "benchmark_score": 78,
        "disk_mb": 12000,
        "vram_mb": 12000,
        "license": "FLUX.1 Non-Commercial",
        "quantization": "fp8",
    },
    "backbone.flux_fill": {
        "benchmark_score": 76,
        "disk_mb": 12000,
        "vram_mb": 12000,
        "license": "FLUX.1 (verify Fill terms)",
        "quantization": "fp8",
    },
    "video.wan22_i2v_high_fp8": {
        "benchmark_score": 80,
        "disk_mb": 14000,
        "vram_mb": 13000,
        "license": "Apache-2.0",
        "quantization": "fp8",
    },
    "video.wan22_i2v_low_fp8": {
        "benchmark_score": 80,
        "disk_mb": 14000,
        "vram_mb": 13000,
        "license": "Apache-2.0",
        "quantization": "fp8",
    },
    "video.wan22_ti2v_5b": {
        "benchmark_score": 68,
        "disk_mb": 10000,
        "vram_mb": 9000,
        "license": "Apache-2.0",
        "quantization": "fp16",
    },
    "identity.pulid_flux": {
        "benchmark_score": 72,
        "disk_mb": 1200,
        "vram_mb": 1500,
        "license": "Apache-2.0 / PuLID terms",
    },
    "upscale.ultrasharp_4x": {
        "benchmark_score": 70,
        "disk_mb": 70,
        "vram_mb": 500,
        "license": "community",
    },
    "video.rife": {
        "benchmark_score": 65,
        "disk_mb": 200,
        "vram_mb": 800,
        "license": "open",
    },
    "video.lightx2v_lora": {
        "benchmark_score": 60,
        "disk_mb": 500,
        "vram_mb": 400,
        "license": "verify",
    },
    "grounding.dino": {
        "benchmark_score": 70,
        "disk_mb": 700,
        "vram_mb": 1500,
        "license": "Apache-2.0",
    },
    "grounding.florence2": {
        "benchmark_score": 66,
        "disk_mb": 1500,
        "vram_mb": 3000,
        "license": "Microsoft Florence",
    },
    "seg.sam2": {
        "benchmark_score": 75,
        "disk_mb": 900,
        "vram_mb": 2000,
        "license": "Apache-2.0",
    },
    "seg.sam": {
        "benchmark_score": 68,
        "disk_mb": 400,
        "vram_mb": 1500,
        "license": "Apache-2.0",
    },
    "matting.birefnet": {
        "benchmark_score": 78,
        "disk_mb": 1000,
        "vram_mb": 2500,
        "license": "MIT",
    },
    "matting.rmbg2": {
        "benchmark_score": 72,
        "disk_mb": 800,
        "vram_mb": 2000,
        "license": "verify",
    },
    "matting.rembg": {
        "benchmark_score": 62,
        "disk_mb": 200,
        "vram_mb": 1500,
        "license": "MIT",
    },
    "matting.heuristic": {
        "benchmark_score": 25,
        "disk_mb": 0,
        "vram_mb": 0,
        "license": "builtin",
    },
    "vlm.qwen25_vl_7b": {
        "benchmark_score": 82,
        "disk_mb": 8000,
        "vram_mb": 10000,
        "license": "Qwen / Tongyi",
        "quantization": "bf16/awq",
    },
    "vlm.qwen25_vl_3b": {
        "benchmark_score": 70,
        "disk_mb": 4000,
        "vram_mb": 5000,
        "license": "Qwen / Tongyi",
        "quantization": "bf16/awq",
    },
}

# Stable P1/P2 workflow_ref -> estimated score (fixture promotion flips estimated→False)
WORKFLOW_SCORES: dict[str, int] = {
    "image_img2img.v0_legacy": 70,
    "background_remove.v1": 68,
    "instruction_edit.v1": 72,
    "clothing_replace.v1": 74,
    "object_replace.v1": 73,
    "object_remove.v1": 72,
    "object_add.v1": 70,
    "inpaint.v1": 73,
    "outpaint.v1": 68,
    "face_edit.v1": 71,
    "hair_edit.v1": 70,
    "face_swap.v1": 55,  # beta / incomplete graph
    "background_replace.v1": 72,
    "product_edit.v1": 70,
    "style_transfer.v1": 69,
    "character_consistency.v1": 71,
    "image_restore.v1": 66,
    "image_upscale.v1": 67,
    "video_i2v.v0_legacy": 65,
    "video_i2v.v1": 76,
    "video_v2v.experimental": 0,
    "video_extend.experimental": 0,
}


def apply_scorecards() -> None:
    """Stamp estimated scores onto registered models + workflows."""
    for mid, meta in MODEL_SCORES.items():
        rec = model_manager.get(mid)
        if rec is None:
            continue
        rec.benchmark_score = int(meta["benchmark_score"])
        rec.benchmark_estimated = True
        if meta.get("disk_mb"):
            rec.disk_mb = int(meta["disk_mb"])
        if meta.get("vram_mb"):
            rec.vram_mb = int(meta["vram_mb"])
        if meta.get("license"):
            rec.license = str(meta["license"])
        if meta.get("quantization"):
            rec.quantization = str(meta["quantization"])

    for ref, score in WORKFLOW_SCORES.items():
        wf = registry.get(ref)
        if wf is None:
            continue
        wf.benchmark_score = int(score)
        wf.benchmark_estimated = True


def disk_footprint_report() -> dict[str, Any]:
    """Documented disk planning from registry (installed + missing)."""
    installed = 0
    missing = 0
    by_role: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for rec in model_manager.all_models():
        mb = int(rec.disk_mb or 0)
        if rec.status in ("installed", "outdated"):
            installed += mb
        else:
            missing += mb
        by_role[rec.role] = by_role.get(rec.role, 0) + mb
        rows.append(
            {
                "model_id": rec.model_id,
                "status": rec.status,
                "disk_mb": mb,
                "vram_mb": rec.vram_mb,
                "benchmark_score": rec.benchmark_score,
                "benchmark_estimated": rec.benchmark_estimated,
            }
        )
    return {
        "installed_disk_mb_est": installed,
        "missing_download_disk_mb_est": missing,
        "total_catalog_disk_mb_est": installed + missing,
        "recommended_free_gb": 100,
        "by_role_disk_mb": by_role,
        "models": rows,
        "note": "Estimates from MODELS.md / Phase 7 scorecard; not measured on disk.",
    }


def workflow_scorecard(
    *,
    channel: str = "stable",
    allow_beta: bool = False,
    allow_experimental: bool = False,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for wf in registry.all():
        if not wf.enabled and not allow_experimental:
            continue
        if wf.experimental and not allow_experimental and channel != "experimental":
            continue
        if wf.beta and not allow_beta and channel not in ("beta", "experimental"):
            continue
        out.append(
            {
                "workflow_ref": wf.workflow_ref,
                "task_types": wf.task_types,
                "benchmark_score": wf.benchmark_score,
                "benchmark_estimated": wf.benchmark_estimated,
                "channel": wf.channel,
                "beta": wf.beta,
                "experimental": wf.experimental,
                "vram_mb_estimate": wf.vram_mb_estimate,
            }
        )
    out.sort(key=lambda r: (-r["benchmark_score"], r["workflow_ref"]))
    return out
