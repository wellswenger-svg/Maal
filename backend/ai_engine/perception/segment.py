"""Boxes → pixel masks (SAM2). Heuristic rasterize when SAM weights missing."""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.ai_engine.perception.image_ops import boxes_to_mask, dilate_mask_png, load_rgb
from backend.ai_engine.perception.types import BBox, MaskResult
from backend.ai_engine.models.manager import manager as model_manager

log = logging.getLogger(__name__)


def sam_available() -> bool:
    return model_manager.is_available("seg.sam2") or model_manager.is_available("seg.sam")


def segment_boxes(
    image_bytes: bytes,
    boxes: list[BBox],
    *,
    grow_px: int = 6,
    settings: Any = None,
) -> MaskResult:
    img = load_rgb(image_bytes)
    w, h = img.size
    warnings: list[str] = []

    if not boxes:
        from backend.ai_engine.perception.image_ops import full_frame_mask

        warnings.append("segment_no_boxes_full_frame")
        return MaskResult(
            mask_png=full_frame_mask(w, h),
            width=w,
            height=h,
            source="full_frame",
            warnings=warnings,
        )

    if sam_available():
        try:
            return _segment_via_comfy(image_bytes, boxes, settings=settings)
        except Exception as exc:
            log.warning("SAM Comfy path failed: %s", exc)
            warnings.append(f"sam_comfy_failed:{exc}")

    mask_png = boxes_to_mask(w, h, boxes, feather=8)
    if grow_px:
        mask_png = dilate_mask_png(mask_png, grow_px)
    warnings.append("segment_heuristic_boxes")
    return MaskResult(
        mask_png=mask_png,
        width=w,
        height=h,
        source="heuristic",
        labels=[b.label for b in boxes if b.label],
        boxes=boxes,
        warnings=warnings,
    )


def _segment_via_comfy(
    image_bytes: bytes,
    boxes: list[BBox],
    *,
    settings: Any,
) -> MaskResult:
    raise NotImplementedError(
        "Comfy SAM2 runner not configured (install segment-anything-2 + weights)"
    )


def build_sam2_graph_stub(*, image_name: str) -> dict[str, Any]:
    """Documentation stub for SAM2 node wiring once pack is installed."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {
            "class_type": "DownloadAndLoadSAM2Model",
            "inputs": {
                "model": "sam2_hiera_base_plus.safetensors",
                "segmentor": "single_image",
                "device": "cuda",
                "precision": "fp16",
            },
        },
    }
