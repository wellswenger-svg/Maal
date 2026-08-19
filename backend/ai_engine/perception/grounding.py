"""
Text → bounding boxes (GroundingDINO / Florence-style).

Phase 4: Comfy graph builder reserved for when nodes+weights exist;
heuristic phrase boxes used as degrade path so pipelines keep flowing.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from backend.ai_engine.perception.image_ops import load_rgb
from backend.ai_engine.perception.types import BBox
from backend.ai_engine.models.manager import manager as model_manager

log = logging.getLogger(__name__)


def grounding_available() -> bool:
    return model_manager.is_available("grounding.dino") or model_manager.is_available(
        "grounding.florence2"
    )


def ground_phrases(
    image_bytes: bytes,
    phrases: list[str],
    *,
    settings: Any = None,
) -> tuple[list[BBox], list[str]]:
    """
    Return (boxes, warnings).
    Prefers Comfy GroundingDINO when installed; else heuristic center priors.
    """
    warnings: list[str] = []
    phrases = [p.strip() for p in phrases if p and str(p).strip()]
    if not phrases:
        warnings.append("grounding_no_phrases")
        return [], warnings

    if grounding_available():
        try:
            boxes = _ground_via_comfy(image_bytes, phrases, settings=settings)
            if boxes:
                return boxes, warnings
            warnings.append("grounding_comfy_empty")
        except Exception as exc:
            log.warning("Comfy grounding failed: %s", exc)
            warnings.append(f"grounding_comfy_failed:{exc}")

    # Heuristic degrade — rough region priors so masked workflows can still run
    img = load_rgb(image_bytes)
    w, h = img.size
    boxes = [_heuristic_box(p, w, h) for p in phrases]
    warnings.append("grounding_heuristic")
    return boxes, warnings


def _heuristic_box(phrase: str, width: int, height: int) -> BBox:
    p = phrase.lower()
    # Face / head — upper center
    if re.search(r"\b(face|head|hair|eyes?|smile)\b", p):
        return BBox(0.25 * width, 0.05 * height, 0.75 * width, 0.55 * height, label=phrase, score=0.4)
    # Clothing / torso — mid frame
    if re.search(
        r"\b(shirt|jersey|jacket|hoodie|dress|clothes|clothing|outfit|pants|jeans)\b",
        p,
    ):
        return BBox(0.2 * width, 0.25 * height, 0.8 * width, 0.85 * height, label=phrase, score=0.4)
    # Background — full frame (caller may invert)
    if re.search(r"\b(background|sky|wall|scene)\b", p):
        return BBox(0, 0, width, height, label=phrase, score=0.3)
    # Default: center box
    return BBox(0.15 * width, 0.15 * height, 0.85 * width, 0.85 * height, label=phrase, score=0.35)


def _ground_via_comfy(
    image_bytes: bytes,
    phrases: list[str],
    *,
    settings: Any,
) -> list[BBox]:
    """
    Placeholder for GroundingDINO Comfy execution.
    Raises if not wired — callers fall back to heuristic.
    """
    # Full Comfy submit lands when custom nodes + weights are confirmed present.
    # Keeping the hook explicit avoids silent fake "success".
    raise NotImplementedError(
        "Comfy GroundingDINO runner not configured (install node pack + weights)"
    )


def build_grounding_dino_graph(
    *,
    image_name: str,
    prompt: str,
    model_name: str = "GroundingDINO_SwinT_OGC",
) -> dict[str, Any]:
    """
    API-format graph sketch for GroundingDINO (Impact / Grounding packs vary).
    Operators may adapt class_type names to their installed pack.
    """
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {
            "class_type": "GroundingDinoModelLoader (segment anything)",
            "inputs": {"model_name": model_name},
        },
        "3": {
            "class_type": "GroundingDinoSAMSegment (segment anything)",
            "inputs": {
                "sam_model": ["4", 0],
                "grounding_dino_model": ["2", 0],
                "image": ["1", 0],
                "prompt": prompt,
                "threshold": 0.3,
            },
        },
        "4": {
            "class_type": "SAMModelLoader (segment anything)",
            "inputs": {"model_name": "sam_vit_b (38MB)"},
        },
    }
