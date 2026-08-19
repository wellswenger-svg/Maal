"""Background matting / subject cutout (BiRefNet preferred, rembg fallback)."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, Optional

from PIL import Image

from backend.ai_engine.perception.image_ops import image_to_png_bytes, load_rgb
from backend.ai_engine.perception.types import MaskResult
from backend.ai_engine.models.manager import manager as model_manager

log = logging.getLogger(__name__)


def matting_available() -> bool:
    if model_manager.is_available("matting.birefnet"):
        return True
    if model_manager.is_available("matting.rmbg2"):
        return True
    try:
        import rembg  # noqa: F401

        return True
    except ImportError:
        return False


def matte_subject(
    image_bytes: bytes,
    *,
    settings: Any = None,
) -> tuple[MaskResult, Optional[bytes], list[str]]:
    """
    Returns (alpha_mask, rgba_png_or_none, warnings).
    Mask: white = subject.
    """
    warnings: list[str] = []
    img = load_rgb(image_bytes)
    w, h = img.size

    if model_manager.is_available("matting.birefnet"):
        try:
            return _matte_via_comfy_birefnet(image_bytes, settings=settings)
        except Exception as exc:
            log.warning("BiRefNet path failed: %s", exc)
            warnings.append(f"birefnet_failed:{exc}")

    # rembg local fallback (no Comfy required)
    try:
        from rembg import remove

        rgba_bytes = remove(image_bytes)
        rgba = Image.open(BytesIO(rgba_bytes)).convert("RGBA")
        alpha = rgba.split()[-1]
        mask = MaskResult(
            mask_png=image_to_png_bytes(alpha),
            width=rgba.width,
            height=rgba.height,
            source="rembg",
            labels=["subject"],
            warnings=list(warnings),
        )
        return mask, image_to_png_bytes(rgba), warnings
    except ImportError:
        warnings.append("rembg_not_installed")
    except Exception as exc:
        log.warning("rembg failed: %s", exc)
        warnings.append(f"rembg_failed:{exc}")

    # Last resort: full-frame subject (no real matte)
    from backend.ai_engine.perception.image_ops import full_frame_mask

    warnings.append("matting_unavailable_full_frame")
    mask = MaskResult(
        mask_png=full_frame_mask(w, h),
        width=w,
        height=h,
        source="full_frame",
        labels=["subject"],
        warnings=list(warnings),
    )
    return mask, None, warnings


def _matte_via_comfy_birefnet(
    image_bytes: bytes,
    *,
    settings: Any,
) -> tuple[MaskResult, Optional[bytes], list[str]]:
    raise NotImplementedError(
        "Comfy BiRefNet runner not configured (install RMBG/BiRefNet nodes + weights)"
    )


def apply_alpha_cutout(image_bytes: bytes, mask_png: bytes) -> bytes:
    """Compose RGB + mask → RGBA PNG."""
    rgb = load_rgb(image_bytes)
    alpha = Image.open(BytesIO(mask_png)).convert("L").resize(rgb.size, Image.Resampling.BILINEAR)
    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    return image_to_png_bytes(rgba)
