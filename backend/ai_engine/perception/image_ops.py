"""Image helpers for perception (Pillow only)."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw


def load_rgb(image_bytes: bytes) -> Image.Image:
    return Image.open(BytesIO(image_bytes)).convert("RGB")


def image_to_png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def full_frame_mask(width: int, height: int, *, invert: bool = False) -> bytes:
    """White = selected. Full white = entire image."""
    val = 0 if invert else 255
    m = Image.new("L", (width, height), color=val)
    return image_to_png_bytes(m)


def boxes_to_mask(
    width: int,
    height: int,
    boxes: list,
    *,
    feather: int = 8,
) -> bytes:
    """Rasterize absolute/normalized boxes to an L mask (heuristic stand-in for SAM)."""
    from backend.ai_engine.perception.types import BBox

    m = Image.new("L", (width, height), color=0)
    draw = ImageDraw.Draw(m)
    for b in boxes:
        if isinstance(b, BBox):
            x1, y1, x2, y2 = b.as_absolute(width, height)
        else:
            x1, y1, x2, y2 = map(int, b[:4])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
        if x2 > x1 and y2 > y1:
            draw.rectangle([x1, y1, x2, y2], fill=255)
    if feather > 0:
        from PIL import ImageFilter

        m = m.filter(ImageFilter.GaussianBlur(radius=feather))
    return image_to_png_bytes(m)


def dilate_mask_png(mask_png: bytes, pixels: int = 6) -> bytes:
    if pixels <= 0:
        return mask_png
    from PIL import ImageFilter

    m = Image.open(BytesIO(mask_png)).convert("L")
    for _ in range(max(1, pixels // 2)):
        m = m.filter(ImageFilter.MaxFilter(3))
    return image_to_png_bytes(m)
