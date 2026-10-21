"""Find the drawn character in a photo and cut it out.

The flood-fill segmentation follows Meta's AnimatedDrawings (MIT): adaptive
threshold, close the strokes, flood the background in from the crop border, and
keep the largest enclosed region. AnimatedDrawings needs a trained detector to
find the character first; here a cheap two-step crop replaces it (find the
sheet of paper, then the cluster of ink on it), so no model is required.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 1024


def load_image(src: str | Path | np.ndarray | Image.Image, max_side: int = MAX_SIDE) -> np.ndarray:
    """Load as RGB uint8, honouring EXIF orientation (phone photos) and flattening alpha onto white."""
    if isinstance(src, np.ndarray):
        img = src
        if img.ndim == 2:
            img = np.stack([img] * 3, axis=-1)
    else:
        im = src if isinstance(src, Image.Image) else Image.open(src)
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
        img = np.asarray(im)
    if img.shape[2] == 4:
        alpha = img[..., 3:4].astype(np.float32) / 255.0
        img = (img[..., :3].astype(np.float32) * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    img = np.ascontiguousarray(img[..., :3])
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if scale < 1.0:
        img = cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def _ink(gray: np.ndarray) -> np.ndarray:
    """Binary map of pen strokes (255 = ink). Window scales with image size."""
    block = max(15, (min(gray.shape) // 8) | 1)
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, block, 8)
    return cv2.bitwise_not(th)


def find_paper(img: np.ndarray) -> tuple[int, int, int, int] | None:
    """Bounding box (x0, y0, x1, y1) of the sheet of paper, shrunk so its edges are excluded.

    Returns None when the paper fills the frame or no clear sheet is found.
    """
    h, w = img.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), (5, 5), 0)
    _, bright = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if not (0.15 * h * w < area < 0.92 * h * w):
        return None
    hull = cv2.convexHull(c)
    if area / max(cv2.contourArea(hull), 1.0) < 0.85:  # not a clean sheet
        return None
    x, y, bw, bh = cv2.boundingRect(hull)
    m = int(0.03 * max(bw, bh))
    return x + m, y + m, x + bw - m, y + bh - m


def find_character_box(img: np.ndarray) -> tuple[int, int, int, int]:
    """Bounding box of the main cluster of ink, ignoring anything touching the frame edge."""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    ink = _ink(gray)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    keep = np.zeros_like(ink)
    min_area = 0.0005 * h * w
    total = kept = 0
    for i in range(1, n):
        x, y, bw, bh, a = stats[i]
        if a < min_area:
            continue
        total += a
        if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
            continue  # table edges, fingers, paper borders
        keep[labels == i] = 255
        kept += a
    # If most of the ink touches the frame, the drawing itself fills the photo (a tight scan or
    # crop): dropping border strokes would leave only an eye or a button. Use the whole image.
    if kept < 0.35 * total or not keep.any():
        return 0, 0, w, h
    # Merge nearby strokes (eyes, buttons, detached hands) into one cluster.
    k = max(5, int(0.04 * max(h, w)))
    grouped = cv2.dilate(keep, np.ones((k, k), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(grouped, 8)
    best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    ys, xs = np.nonzero((labels == best) & (keep > 0))
    pad = int(0.06 * max(xs.max() - xs.min(), ys.max() - ys.min())) + 4
    return (max(0, xs.min() - pad), max(0, ys.min() - pad),
            min(w, xs.max() + pad + 1), min(h, ys.max() + pad + 1))


def segment_crop(crop: np.ndarray) -> np.ndarray:
    """Character mask (uint8 0/255) for a crop that contains one drawing on paper."""
    gray = np.min(crop, axis=2)  # min channel keeps light-coloured marker strokes
    ink = _ink(gray)
    kernel = np.ones((3, 3), np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel, iterations=2)
    ink = cv2.morphologyEx(ink, cv2.MORPH_DILATE, kernel, iterations=2)

    h, w = ink.shape
    barrier = np.zeros((h + 2, w + 2), np.uint8)
    barrier[1:-1, 1:-1] = ink
    filled = np.full((h, w), 255, np.uint8)
    step = 10
    for x in range(0, w, step):
        cv2.floodFill(filled, barrier, (x, 0), 0)
        cv2.floodFill(filled, barrier, (x, h - 1), 0)
    for y in range(0, h, step):
        cv2.floodFill(filled, barrier, (0, y), 0)
        cv2.floodFill(filled, barrier, (w - 1, y), 0)
    filled[0, :] = filled[-1, :] = 0
    filled[:, 0] = filled[:, -1] = 0

    contours, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    mask = np.zeros((h, w), np.uint8)
    if contours:
        cv2.drawContours(mask, [max(contours, key=cv2.contourArea)], -1, 255, thickness=cv2.FILLED)
    return mask


def whiten(crop: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Make the paper inside the character read as white and lift faded colours."""
    bg = cv2.dilate(mask, np.ones((9, 9), np.uint8)) == 0
    paper = np.median(crop[bg], axis=0) if bg.sum() > 50 else np.percentile(crop.reshape(-1, 3), 90, axis=0)
    gain = 245.0 / np.maximum(paper.astype(np.float32), 1.0)
    out = np.clip(crop.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(out, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.25, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def extract_character(src, max_side: int = MAX_SIDE, already_cropped: bool = False):
    """Photo -> (rgb crop, mask). The crop is the region the character was found in."""
    img = load_image(src, max_side)
    if already_cropped:
        crop = img
    else:
        x0, y0, x1, y1 = find_paper(img) or (0, 0, img.shape[1], img.shape[0])
        page = img[y0:y1, x0:x1]
        cx0, cy0, cx1, cy1 = find_character_box(page)
        crop = page[cy0:cy1, cx0:cx1]
    mask = segment_crop(crop)
    return crop, mask
