"""Find the drawn character in a photo and cut it out.

The flood-fill segmentation follows Meta's AnimatedDrawings (MIT): adaptive
threshold, close the strokes, flood the background in from the crop border, and
keep the largest enclosed region. AnimatedDrawings needs a trained detector to
find the character first; here a cheap two-step crop replaces it (find the
sheet of paper, then the cluster of ink on it), so no model is required.

Phone photos add four problems this module handles without a model, all deterministic:
uneven light (the paper is estimated and divided out before thresholding), crayon with no
dark outline (ink is "far from the paper colour", in darkness or in chroma), a sheet shot
at an angle (straightened when it is clearly a skewed quadrilateral), and outlines with a
small gap (the leak is detected and sealed with a stronger closing, only at the gap).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 1024
Box = tuple[int, int, int, int]  # x0, y0, x1, y1 (exclusive)


def load_image(src: str | Path | np.ndarray | Image.Image, max_side: int = MAX_SIDE) -> np.ndarray:
    """Load as RGB uint8, honouring EXIF orientation (phone photos) and flattening alpha onto white."""
    if isinstance(src, np.ndarray):
        img = src
        if img.ndim == 2:
            img = np.stack([img] * 3, axis=-1)
    else:
        im = src if isinstance(src, Image.Image) else Image.open(src)
        im = ImageOps.exif_transpose(im)
        if im.mode == "F" or im.mode.startswith("I"):
            # 16-bit and float grey: convert() would clip anything over 255 to white.
            a = np.asarray(im, np.float64)
            im = Image.fromarray((a * (255 / 65535 if a.max() > 255 else 1)).clip(0, 255).astype(np.uint8))
        alpha = im.mode in ("RGBA", "RGBa", "LA", "PA") or "transparency" in im.info
        im = im.convert("RGBA" if alpha else "RGB")  # CMYK's 4th channel is K, not alpha
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


# --- Lighting and ink ---------------------------------------------------------------------------

def _paper_colour(img: np.ndarray) -> np.ndarray:
    """RGB of well-lit paper: the median of the brightest 15% of pixels."""
    gray = img.mean(axis=2)
    return np.median(img[gray >= np.percentile(gray, 85)].reshape(-1, 3), axis=0).astype(np.float32) + 1.0


def paper_background(img: np.ndarray) -> np.ndarray:
    """Per-pixel RGB estimate of the bare paper under the photo's lighting (float32, H x W x 3).

    Work at 256 px: pixels that look like plain paper (near-neutral relative to the paper's
    colour, not darker than their surroundings, not near-black) are kept; strokes, crayon and
    the table are cut out and filled in from the paper around them (inpainting), then smoothed.
    Unlike a large blur or morphological closing, this follows a soft shadow edge closely
    without swallowing a big coloured-in area into the "background".
    """
    h, w = img.shape[:2]
    s = min(1.0, 256 / max(h, w))
    small = cv2.resize(img, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
    paper = _paper_colour(small)
    if min(small.shape[:2]) < 16:
        return np.broadcast_to(paper, img.shape).astype(np.float32)
    wb = small.astype(np.float32) / paper                         # paper -> (1, 1, 1)
    hi, lo = wb.max(axis=2), wb.min(axis=2)
    chroma = (hi - lo) / np.maximum(hi, 1e-3)
    gray = wb.mean(axis=2)
    envelope = cv2.dilate(gray, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    not_paper = (chroma > 0.12) | (gray < 0.85 * envelope) | (gray < 0.25)
    not_paper = cv2.dilate(not_paper.astype(np.uint8), np.ones((3, 3), np.uint8))
    if not_paper.mean() > 0.97:
        return np.broadcast_to(paper, img.shape).astype(np.float32)
    bg = cv2.inpaint(small, not_paper * 255, 3, cv2.INPAINT_TELEA)
    bg = cv2.GaussianBlur(bg.astype(np.float32), (0, 0), 1.5)
    return cv2.resize(bg, (w, h), interpolation=cv2.INTER_LINEAR)


def flatten(img: np.ndarray) -> np.ndarray:
    """The photo divided by its paper background: paper reads ~1.0 everywhere, shadows removed."""
    return img.astype(np.float32) / np.maximum(paper_background(img), 1.0)


def ink_signal(img: np.ndarray) -> np.ndarray:
    """uint8 map of how far each pixel is from the paper colour (0 = paper, 255 = far).

    The larger of darkness (1 - mean of the flattened RGB) and chroma (max - min channel), so
    a light-yellow crayon line counts as much as a grey pencil one, while the paper's own tint,
    its grain and shadows on it (all divided out) do not.
    """
    n = np.clip(flatten(img), 0.0, 1.0)
    sig = np.maximum(1.0 - n.mean(axis=2), n.max(axis=2) - n.min(axis=2))
    return np.clip(sig * 255.0, 0, 255).astype(np.uint8)


def _ink(img: np.ndarray) -> np.ndarray:
    """Binary map of strokes (255 = ink), colour-aware and shadow-free. Window scales with size."""
    sig = ink_signal(img)
    block = max(15, (min(sig.shape) // 8) | 1)
    return cv2.adaptiveThreshold(sig, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, block, -8)


# --- The sheet of paper -------------------------------------------------------------------------

def _sheet(bright: np.ndarray) -> np.ndarray | None:
    """Largest bright region if it looks like a clean sheet (not the whole frame), else None."""
    h, w = bright.shape
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if not (0.15 * h * w < area < 0.92 * h * w):
        return None
    if area / max(cv2.contourArea(cv2.convexHull(c)), 1.0) < 0.85:  # not a clean sheet
        return None
    return c


def _bright_otsu(img: np.ndarray) -> np.ndarray:
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), (5, 5), 0)
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def _bright_flat(img: np.ndarray) -> np.ndarray:
    """Paper-like pixels after dividing out the lighting: catches the shadowed part of a sheet."""
    n = cv2.GaussianBlur(flatten(img), (5, 5), 0)
    chroma = n.max(axis=2) - n.min(axis=2)
    return ((n.mean(axis=2) > 0.8) & (chroma < 0.15)).astype(np.uint8) * 255


def find_paper(img: np.ndarray) -> Box | None:
    """Bounding box (x0, y0, x1, y1) of the sheet of paper, shrunk so its edges are excluded.

    Returns None when the paper fills the frame or no clear sheet is found. Plain brightness
    (Otsu) finds a well-lit sheet; when a shadow makes part of the sheet darker than the table,
    the lighting-flattened view finds a bigger sheet that contains it, and that one wins.
    """
    c = _sheet(_bright_otsu(img))
    flat = _sheet(_bright_flat(img))
    if flat is not None:
        fx, fy, fw, fh = cv2.boundingRect(flat)
        if c is None:
            c = flat if cv2.contourArea(flat) < 0.8 * img.shape[0] * img.shape[1] else None
        else:
            x, y, bw, bh = cv2.boundingRect(c)
            tol = 0.02 * max(img.shape[:2])
            inside = x >= fx - tol and y >= fy - tol and x + bw <= fx + fw + tol and y + bh <= fy + fh + tol
            if inside and cv2.contourArea(flat) > 1.1 * cv2.contourArea(c):
                c = flat
    if c is None:
        return None
    x, y, bw, bh = cv2.boundingRect(cv2.convexHull(c))
    m = int(0.03 * min(bw, bh))  # max() would trim a narrow sheet inside out
    if bw <= 2 * m or bh <= 2 * m:
        return None
    return x + m, y + m, x + bw - m, y + bh - m


def _order_corners(q: np.ndarray) -> np.ndarray:
    """Top-left, top-right, bottom-right, bottom-left."""
    c = q.mean(axis=0)
    ang = np.arctan2(q[:, 1] - c[1], q[:, 0] - c[0])
    q = q[np.argsort(ang)]                          # clockwise in image coords, starting near -pi
    start = int(np.argmin(q.sum(axis=1)))           # smallest x + y is the top-left
    return np.roll(q, -start, axis=0)


def _page_aspect(q: np.ndarray, shape: tuple[int, int]) -> float:
    """Width / height of the real sheet behind quad q (TL, TR, BR, BL), via a pinhole camera.

    Zhang & He, "Whiteboard scanning and image enhancement" (2007): the quad's vanishing
    geometry gives the focal length, which undoes the foreshortening. Falls back to the mean
    side lengths when the quad is (nearly) a parallelogram and the focal length is undefined.
    """
    h, w = shape
    u0, v0 = w / 2.0, h / 2.0
    m1, m2, m4, m3 = (np.array([p[0], p[1], 1.0]) for p in q)    # paper: m1 TL, m2 TR, m3 BL, m4 BR
    k2 = np.dot(np.cross(m1, m4), m3) / np.dot(np.cross(m2, m4), m3)
    k3 = np.dot(np.cross(m1, m4), m2) / np.dot(np.cross(m3, m4), m2)
    n2, n3 = k2 * m2 - m1, k3 * m3 - m1
    fallback = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / \
               (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1]))
    if abs(n2[2] * n3[2]) < 1e-9:
        return float(fallback)
    f2 = -((n2[0] * n3[0] - (n2[0] * n3[2] + n2[2] * n3[0]) * u0 + n2[2] * n3[2] * u0 * u0)
           + (n2[1] * n3[1] - (n2[1] * n3[2] + n2[2] * n3[1]) * v0 + n2[2] * n3[2] * v0 * v0)) / (n2[2] * n3[2])
    if not np.isfinite(f2) or f2 <= 0:
        return float(fallback)
    a = np.array([[np.sqrt(f2), 0, u0], [0, np.sqrt(f2), v0], [0, 0, 1]])
    ai = np.linalg.inv(a)
    b = ai.T @ ai
    ratio = np.sqrt((n2 @ b @ n2) / (n3 @ b @ n3))
    # A wildly different answer from the side lengths means the camera model does not fit.
    return float(ratio) if 0.6 < ratio / fallback < 1.6 else float(fallback)


def straighten(img: np.ndarray, max_side: int = MAX_SIDE) -> np.ndarray:
    """Warp a sheet shot at an angle back to a flat rectangle; return `img` itself otherwise.

    Only acts when the paper is clearly a quadrilateral fully inside the frame and noticeably
    skewed (a corner off square by more than 4 degrees, or an edge tilted more than 4 degrees).
    The result is the sheet alone, so every later coordinate (crops, crop_offset) is in this
    straightened space.
    """
    h, w = img.shape[:2]
    c = _sheet(_bright_otsu(img))
    if c is None:
        return img
    quad = cv2.approxPolyDP(cv2.convexHull(c), 0.02 * cv2.arcLength(c, True), True)
    if len(quad) != 4:
        return img
    q = _order_corners(quad[:, 0, :].astype(np.float64))
    if cv2.contourArea(c) < 0.93 * cv2.contourArea(q.astype(np.float32)):
        return img                                               # not really a quad
    if (q[:, 0] < 3).any() or (q[:, 1] < 3).any() or (q[:, 0] > w - 4).any() or (q[:, 1] > h - 4).any():
        return img                                               # a corner is cut off by the frame
    edges = np.roll(q, -1, axis=0) - q
    angles = []
    for i in range(4):
        a, b = -edges[i - 1], edges[i]
        cos = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        angles.append(np.degrees(np.arccos(np.clip(cos, -1, 1))))
    tilt = np.degrees(np.arctan2(edges[0][1], edges[0][0]))
    if max(abs(a - 90) for a in angles) <= 4 and abs(tilt) <= 4:
        return img                                               # square-on enough already
    if abs(tilt) > 30:
        return img                                               # which way is up is unclear
    tall = max(np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1]))
    wide = tall * _page_aspect(q, (h, w))
    scale = min(1.0, max_side / max(tall, wide))
    ow, oh = max(8, round(wide * scale)), max(8, round(tall * scale))
    dst = np.array([[0, 0], [ow - 1, 0], [ow - 1, oh - 1], [0, oh - 1]], np.float32)
    out = cv2.warpPerspective(img, cv2.getPerspectiveTransform(q.astype(np.float32), dst), (ow, oh),
                              flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    m = max(2, round(0.01 * max(ow, oh)))                        # drop the table fringe at the edge
    return np.ascontiguousarray(out[m:oh - m, m:ow - m])


def prepare_image(src, max_side: int = MAX_SIDE) -> np.ndarray:
    """load_image + straighten: the image every box from find_characters refers to."""
    return straighten(load_image(src, max_side), max_side)


# --- Where the characters are -------------------------------------------------------------------

def _clusters(img: np.ndarray) -> tuple[list[Box], list[int], bool]:
    """Boxes of ink clusters (largest first), their ink pixel counts, and whether ink fills the frame.

    Strokes touching the frame edge (table, fingers, paper borders) are ignored; nearby strokes
    (eyes, buttons, detached hands) are merged into one cluster.
    """
    h, w = img.shape[:2]
    ink = cv2.morphologyEx(_ink(img), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    keep = np.zeros_like(ink)
    edge = np.zeros_like(ink)
    min_area = 0.0005 * h * w
    total = kept = 0
    for i in range(1, n):
        x, y, bw, bh, a = stats[i]
        if a < min_area:
            continue
        total += a
        if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
            edge[labels == i] = 255
            continue
        keep[labels == i] = 255
        kept += a
    # If most of the ink touches the frame, the drawing itself fills the photo (a tight scan or
    # crop): dropping border strokes would leave only an eye or a button.
    if kept < 0.35 * total or not keep.any():
        return [], [], True
    k = max(5, int(0.04 * max(h, w)))
    grouped = cv2.dilate(keep, np.ones((k, k), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(grouped, 8)
    # The same when the biggest cluster runs into more frame-touching ink than it has itself:
    # its outline continues off the frame (coloured-in crops have lots of interior ink).
    main = labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    mys, mxs = np.nonzero(main)
    reaches = mxs.min() <= 1 or mys.min() <= 1 or mxs.max() >= w - 2 or mys.max() >= h - 2
    if edge.any() and reaches:
        ne, elabels = cv2.connectedComponents(edge, connectivity=8)
        hit = np.unique(elabels[main & (edge > 0)])
        if (np.isin(elabels, hit[hit > 0]) & (edge > 0)).sum() > (main & (keep > 0)).sum():
            return [], [], True
    boxes, counts = [], []
    for i in sorted(range(1, n), key=lambda i: -stats[i, cv2.CC_STAT_AREA]):
        ys, xs = np.nonzero((labels == i) & (keep > 0))
        if len(xs) == 0:
            continue
        pad = int(0.06 * max(xs.max() - xs.min(), ys.max() - ys.min())) + 4
        boxes.append((max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
                      min(w, int(xs.max()) + pad + 1), min(h, int(ys.max()) + pad + 1)))
        counts.append(len(xs))
    return boxes, counts, False


def find_character_box(img: np.ndarray) -> Box:
    """Bounding box of the main cluster of ink, ignoring anything touching the frame edge."""
    boxes, _, fills = _clusters(img)
    return (0, 0, img.shape[1], img.shape[0]) if fills else boxes[0]


def _page(img: np.ndarray) -> Box:
    return find_paper(img) or (0, 0, img.shape[1], img.shape[0])


def find_characters(src, max_side: int = MAX_SIDE) -> list[Box]:
    """Every separate drawing on the sheet, as boxes (x0, y0, x1, y1), biggest first.

    Boxes are in the coordinates of `prepare_image(src)` (loaded, resized, straightened), which
    is what `extract_character(src, box=...)` crops from. Specks (less than 8% of the biggest
    drawing's ink, or smaller than 4% of the sheet) are left out.
    """
    img = prepare_image(src, max_side)
    px0, py0, px1, py1 = _page(img)
    page = img[py0:py1, px0:px1]
    boxes, counts, fills = _clusters(page)
    if fills:
        return [(px0, py0, px1, py1)]
    side = max(page.shape[:2])
    out = []
    for (x0, y0, x1, y1), n in zip(boxes, counts):
        if n < 0.08 * counts[0] or max(x1 - x0, y1 - y0) < 0.04 * side:
            continue
        out.append((x0 + px0, y0 + py0, x1 + px0, y1 + py0))
    return out


# --- Cutting out --------------------------------------------------------------------------------

def _barrier(ink: np.ndarray, k: int = 0) -> np.ndarray:
    """Strokes closed into walls for the flood fill; k > 0 first closes gaps up to ~k px wide."""
    if k > 0:
        ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    kernel = np.ones((3, 3), np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel, iterations=2)
    return cv2.morphologyEx(ink, cv2.MORPH_DILATE, kernel, iterations=2)


def _outside(barrier: np.ndarray) -> np.ndarray:
    """Background flooded in from the crop border (bool)."""
    h, w = barrier.shape
    walls = np.zeros((h + 2, w + 2), np.uint8)
    walls[1:-1, 1:-1] = barrier
    filled = np.full((h, w), 255, np.uint8)
    step = 10
    for x in range(0, w, step):
        cv2.floodFill(filled, walls, (x, 0), 0)
        cv2.floodFill(filled, walls, (x, h - 1), 0)
    for y in range(0, h, step):
        cv2.floodFill(filled, walls, (0, y), 0)
        cv2.floodFill(filled, walls, (w - 1, y), 0)
    filled[0, :] = filled[-1, :] = 0
    filled[:, 0] = filled[:, -1] = 0
    return filled == 0


def _largest(inside: np.ndarray) -> np.ndarray:
    """The largest region, holes filled, as a uint8 0/255 mask."""
    contours, _ = cv2.findContours(inside.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    mask = np.zeros(inside.shape, np.uint8)
    if contours:
        cv2.drawContours(mask, [max(contours, key=cv2.contourArea)], -1, 255, thickness=cv2.FILLED)
    return mask


def _seal_leak(ink: np.ndarray, bar0: np.ndarray, out0: np.ndarray, m0: np.ndarray) -> np.ndarray | None:
    """If the flood leaked in through a gap in the outline, a sealed mask; otherwise None.

    A leak leaves just the outline ring: a mask that is nearly all wall, which grows a lot once
    its gap is closed. Stronger closings are tried smallest first; the first that seals wins.
    Only the plug in the gap is kept from that closing, so armpits and the space between the
    legs, which a big closing would also fill, stay open.
    """
    area0 = int((m0 > 0).sum())
    if area0 == 0 or (bar0[m0 > 0] > 0).mean() < 0.7:
        return None                                              # a real interior: no leak
    side = max(m0.shape)
    for frac in (0.02, 0.035, 0.05, 0.07, 0.1, 0.13, 0.16):
        k = max(5, round(frac * side)) | 1
        bar = _barrier(ink, k)
        mk = _largest(~_outside(bar))
        if (mk > 0).sum() < 1.5 * area0 or ((mk > 0) & (m0 > 0)).sum() < 0.9 * area0:
            continue
        leaked = (mk > 0) & out0                                 # outside before, inside now
        plug = leaked & (bar > 0) & (bar0 == 0)                  # what the closing added
        inner = (leaked & ~plug).astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(inner, 4)
        if n < 2:
            continue
        interior = labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        touch = cv2.dilate(interior.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        n, labels = cv2.connectedComponents(plug.astype(np.uint8), connectivity=8)
        keep = np.isin(labels, np.unique(labels[touch & plug])) & plug
        sealed = _largest(((mk > 0) & ~out0) | interior | keep)
        if (sealed > 0).sum() >= 1.5 * area0:                    # a real interior was recovered
            return sealed
    return None


def _cut(crop: np.ndarray, ink: np.ndarray) -> np.ndarray:
    bar0 = _barrier(ink)
    out0 = _outside(bar0)
    mask = _largest(~out0)
    sealed = _seal_leak(ink, bar0, out0, mask)
    return mask if sealed is None else sealed


def segment_crop(crop: np.ndarray) -> np.ndarray:
    """Character mask (uint8 0/255) for a crop that contains one drawing on paper.

    First with the min-channel ink (keeps light-coloured marker strokes); when that finds
    almost nothing, again with the colour-aware, shadow-flattened ink (pale crayon, no outline).
    """
    gray = np.min(crop, axis=2)
    block = max(15, (min(gray.shape) // 8) | 1)
    ink = cv2.bitwise_not(cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, block, 8))
    mask = _cut(crop, ink)
    if (mask > 0).mean() < 0.2:
        other = _cut(crop, _ink(crop))
        if (other > 0).sum() > (mask > 0).sum():
            mask = other
    return mask


def soft_alpha(mask: np.ndarray, ss: int = 4) -> np.ndarray:
    """Anti-aliased alpha (uint8) for a binary mask: a smooth outline with a ~1 px feathered edge.

    The mask is upsampled, smoothed and re-thresholded so the pixel staircase becomes a smooth
    curve, then averaged back down (pixel coverage) and feathered by a pixel. The binary mask
    itself is untouched; the mesh is still built from it.
    """
    h, w = mask.shape
    up = cv2.resize(mask, (w * ss, h * ss), interpolation=cv2.INTER_LINEAR)
    up = cv2.GaussianBlur(up, (0, 0), 0.5 * ss)
    up = np.where(up >= 128, 255, 0).astype(np.uint8)
    cover = cv2.resize(up, (w, h), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(cover, (3, 3), 0.6)


def whiten(crop: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Make the paper inside the character read as white and lift faded colours."""
    bg = cv2.dilate(mask, np.ones((9, 9), np.uint8)) == 0
    paper = np.median(crop[bg], axis=0) if bg.sum() > 50 else np.percentile(crop.reshape(-1, 3), 90, axis=0)
    gain = 245.0 / np.maximum(paper.astype(np.float32), 1.0)
    out = np.clip(crop.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(out, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.25, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def extract_character(src, max_side: int = MAX_SIDE, already_cropped: bool = False, box: Box | None = None):
    """Photo -> (rgb crop, mask). The crop is the region the character was found in.

    `box` (from `find_characters`) picks one drawing on a sheet with several; it is in the
    coordinates of `prepare_image(src)`. Without it the biggest drawing is used.
    """
    img = load_image(src, max_side)
    if not already_cropped:
        img = straighten(img, max_side)
    if box is None and not already_cropped:
        px0, py0, px1, py1 = _page(img)
        cx0, cy0, cx1, cy1 = find_character_box(img[py0:py1, px0:px1])
        box = (px0 + cx0, py0 + cy0, px0 + cx1, py0 + cy1)
    if box is None:
        crop = img
    else:
        h, w = img.shape[:2]
        x0, y0, x1, y1 = (int(v) for v in box)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            raise ValueError(f"box {box} is outside the {w}x{h} image")
        crop = img[y0:y1, x0:x1]
    return crop, segment_crop(crop)
