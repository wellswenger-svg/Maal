"""
Perception pipeline — runs stages requested by ExecutionPlan.perception.

Stages:
  grounding | sam2 | matting | face_detect (stub)

On detector miss: attach warnings (mask_failed / perception_degraded) so
edit workflows can fall back to instruction_edit behavior.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.ai_engine.perception import grounding, matting, segment
from backend.ai_engine.perception.types import BBox, PerceptionArtifacts
from backend.ai_engine.runtime import vram
from backend.ai_engine.schema import ExecutionPlan

log = logging.getLogger(__name__)


async def run_perception(
    *,
    image_bytes: bytes,
    plan: ExecutionPlan,
    settings: Any = None,
) -> PerceptionArtifacts:
    stages = [s.lower() for s in (plan.perception or [])]
    art = PerceptionArtifacts()

    if not stages:
        return art

    # Normalize aliases
    want_ground = any(s in ("grounding", "groundingdino", "florence2") for s in stages)
    want_sam = any(s in ("sam2", "sam", "segment") for s in stages)
    want_matte = any(s in ("matting", "birefnet", "rembg", "bg_remove") for s in stages)
    want_face = any(s in ("face_detect", "face") for s in stages)
    want_garment = any(s in ("garment", "cloth", "clothing", "clipseg") for s in stages)

    phrases = [
        str(t.get("label") or t.get("phrase") or "").strip()
        for t in (plan.targets or [])
        if isinstance(t, dict)
    ]
    phrases = [p for p in phrases if p]
    if not phrases and want_ground:
        # Derive from positive prompt nouns lightly
        pos = (plan.prompts or {}).get("positive") or ""
        phrases = _guess_phrases(pos)

    try:
        if want_garment and not want_ground and not want_sam and not want_matte:
            from backend.ai_engine.perception import garment_mask as gm

            art.mask = gm.detect_garment_mask(image_bytes, settings=settings)
            art.warnings.extend(art.mask.warnings)
            art.stages_run.append("garment")
            if art.mask.source in ("local_fabric", "heuristic"):
                art.warnings.append("perception_degraded")
            return art

        if want_matte and not want_ground and not want_sam:
            mask, rgba, warnings = matting.matte_subject(image_bytes, settings=settings)
            art.mask = mask
            art.subject_rgba_png = rgba
            art.warnings.extend(warnings)
            art.warnings.extend(mask.warnings)
            art.stages_run.append("matting")
            if mask.source == "full_frame":
                art.warnings.append("mask_failed")
            return art

        if want_ground or want_sam:
            boxes: list[BBox] = []
            if want_ground or phrases:
                boxes, gw = grounding.ground_phrases(
                    image_bytes, phrases or ["subject"], settings=settings
                )
                art.warnings.extend(gw)
                art.boxes = boxes
                art.stages_run.append("grounding")

            if want_face and not boxes:
                # Face prior without detector weights
                from backend.ai_engine.perception.image_ops import load_rgb

                img = load_rgb(image_bytes)
                w, h = img.size
                boxes = [
                    BBox(0.25 * w, 0.05 * h, 0.75 * w, 0.55 * h, label="face", score=0.35)
                ]
                art.boxes = boxes
                art.warnings.append("face_detect_heuristic")
                art.stages_run.append("face_detect")

            if want_sam or want_ground:
                mask = segment.segment_boxes(image_bytes, boxes or art.boxes, settings=settings)
                art.mask = mask
                art.warnings.extend(mask.warnings)
                art.stages_run.append("sam2" if "heuristic" not in mask.source else "segment_heuristic")
                if "heuristic" in mask.source or mask.source == "full_frame":
                    art.warnings.append("perception_degraded")
                if not boxes:
                    art.warnings.append("mask_failed")

            if want_matte:
                # Refine subject with matting when requested alongside
                mask2, rgba, mw = matting.matte_subject(image_bytes, settings=settings)
                art.warnings.extend(mw)
                if rgba is not None:
                    art.subject_rgba_png = rgba
                # Prefer intersection-quality: if we already have a region mask, keep it;
                # store matte as alternate in meta.
                if art.mask:
                    art.mask.meta["matte_source"] = mask2.source
                else:
                    art.mask = mask2
                art.stages_run.append("matting")

        elif want_face:
            from backend.ai_engine.perception.image_ops import load_rgb

            img = load_rgb(image_bytes)
            w, h = img.size
            boxes = [
                BBox(0.25 * w, 0.05 * h, 0.75 * w, 0.55 * h, label="face", score=0.35)
            ]
            mask = segment.segment_boxes(image_bytes, boxes, settings=settings)
            art.boxes = boxes
            art.mask = mask
            art.warnings.append("face_detect_heuristic")
            art.stages_run.append("face_detect")

    except Exception as exc:
        log.exception("perception pipeline failed")
        art.warnings.append(f"perception_error:{exc}")
        art.warnings.append("mask_failed")
    finally:
        vram.release_stage("after_perception")

    return art


def _guess_phrases(text: str) -> list[str]:
    import re

    candidates = re.findall(
        r"\b(shirt|jersey|jacket|hoodie|dress|pants|jeans|top|blouse|hair|face|"
        r"background|person|man|woman|car|logo|sky|shoes|hat|bust|chest)\b",
        text,
        flags=re.I,
    )
    # unique preserve order
    out: list[str] = []
    for c in candidates:
        cl = c.lower()
        if cl not in out:
            out.append(cl)
    return out[:4] or ["subject"]
