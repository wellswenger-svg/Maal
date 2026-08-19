"""Cheap start-image face scan: full/frontal vs side/partial profile."""

from __future__ import annotations

from io import BytesIO
from typing import Literal

from PIL import Image

FaceView = Literal["full", "profile"]


def classify_face_view(image_bytes: bytes | None) -> FaceView:
    """
    Scan the start photo.

    full    — a sizable, roughly square face region (typical frontal / selfie)
    profile — narrow or off-center face, or little face area (side / partial)
    """
    if not image_bytes:
        return "full"
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return "full"

    haar = _haar_face(img)
    if haar is not None:
        return haar
    return _skin_blob_view(img)


def _haar_face(img: Image.Image) -> FaceView | None:
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    cascade = None
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
        path = getattr(cv2.data, "haarcascades", "") + name
        try:
            c = cv2.CascadeClassifier(path)
            if not c.empty():
                cascade = c
                break
        except Exception:
            continue
    if cascade is None:
        return None
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(32, 32))
    if faces is None or len(faces) == 0:
        # Try profile cascade explicitly
        try:
            ppath = cv2.data.haarcascades + "haarcascade_profileface.xml"
            pc = cv2.CascadeClassifier(ppath)
            if not pc.empty():
                pfaces = pc.detectMultiScale(gray, 1.1, 4, minSize=(24, 24))
                if pfaces is not None and len(pfaces) > 0:
                    return "profile"
        except Exception:
            pass
        return None
    W, H = img.size
    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))
    area = (w * h) / float(max(W * H, 1))
    aspect = w / float(max(h, 1))
    cx = (x + w / 2.0) / float(max(W, 1))
    if aspect < 0.68 or cx < 0.22 or cx > 0.78:
        return "profile"
    if area < 0.03:
        return "profile"
    return "full"


def _skin_blob_view(img: Image.Image) -> FaceView:
    """YCbCr skin blob in the upper frame — no extra models."""
    w, h = img.size
    if w < 8 or h < 8:
        return "full"
    # Scan the top 58% — faces live there in portraits
    crop = img.crop((0, 0, w, max(1, int(h * 0.58)))).resize(
        (max(32, w // 8), max(24, int(h * 0.58) // 8)),
        Image.Resampling.BILINEAR,
    )
    ycbcr = crop.convert("YCbCr")
    pix = ycbcr.load()
    cw, ch = crop.size
    mask = [[False] * cw for _ in range(ch)]
    for yy in range(ch):
        for xx in range(cw):
            _y, cb, cr = pix[xx, yy]
            if 77 <= cb <= 127 and 133 <= cr <= 173 and 40 <= _y <= 230:
                mask[yy][xx] = True
    visited = [[False] * cw for _ in range(ch)]
    best = 0
    best_box = None
    for yy in range(ch):
        for xx in range(cw):
            if not mask[yy][xx] or visited[yy][xx]:
                continue
            area, box = _flood(mask, visited, xx, yy, cw, ch)
            if area > best:
                best = area
                best_box = box
    if not best_box or best < max(12, (cw * ch) // 40):
        return "profile"
    x1, y1, x2, y2 = best_box
    bw = max(1, x2 - x1 + 1)
    bh = max(1, y2 - y1 + 1)
    aspect = bw / float(bh)
    cx = ((x1 + x2) / 2.0) / float(max(cw, 1))
    frac = best / float(max(cw * ch, 1))
    if aspect < 0.62 or cx < 0.22 or cx > 0.78:
        return "profile"
    if frac < 0.06:
        return "profile"
    return "full"


def _flood(
    mask: list[list[bool]],
    visited: list[list[bool]],
    sx: int,
    sy: int,
    w: int,
    h: int,
) -> tuple[int, tuple[int, int, int, int]]:
    stack = [(sx, sy)]
    visited[sy][sx] = True
    n = 0
    x1 = x2 = sx
    y1 = y2 = sy
    while stack:
        x, y = stack.pop()
        n += 1
        if x < x1:
            x1 = x
        if x > x2:
            x2 = x
        if y < y1:
            y1 = y
        if y > y2:
            y2 = y
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not visited[ny][nx]:
                visited[ny][nx] = True
                stack.append((nx, ny))
    return n, (x1, y1, x2, y2)
