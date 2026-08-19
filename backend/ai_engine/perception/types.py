"""Perception artifacts shared across adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BBox:
    """Normalized or absolute pixel box. Absolute when x2>1 or y2>1."""

    x1: float
    y1: float
    x2: float
    y2: float
    label: str = ""
    score: float = 1.0

    def as_absolute(self, width: int, height: int) -> tuple[int, int, int, int]:
        if self.x2 <= 1.0 and self.y2 <= 1.0 and self.x1 <= 1.0 and self.y1 <= 1.0:
            return (
                int(self.x1 * width),
                int(self.y1 * height),
                int(self.x2 * width),
                int(self.y2 * height),
            )
        return int(self.x1), int(self.y1), int(self.x2), int(self.y2)


@dataclass
class MaskResult:
    """PNG bytes of an L (mask) or RGBA matte; white = edit region / subject."""

    mask_png: bytes
    width: int
    height: int
    source: str  # grounding+sam2 | birefnet | rembg | full_frame | heuristic
    labels: list[str] = field(default_factory=list)
    boxes: list[BBox] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerceptionArtifacts:
    """Collected perception outputs for a generation job."""

    mask: Optional[MaskResult] = None
    subject_rgba_png: Optional[bytes] = None  # cutout with alpha when matting
    boxes: list[BBox] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stages_run: list[str] = field(default_factory=list)

    def to_meta(self) -> dict[str, Any]:
        return {
            "stages_run": self.stages_run,
            "warnings": self.warnings,
            "has_mask": self.mask is not None,
            "mask_source": self.mask.source if self.mask else None,
            "mask_labels": self.mask.labels if self.mask else [],
            "box_count": len(self.boxes),
            "has_subject_rgba": self.subject_rgba_png is not None,
        }
