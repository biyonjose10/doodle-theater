"""Photo from the phone -> draft puppet the parent can check, fix and send to the TV."""
from __future__ import annotations

import base64
import io
import json
import logging
import math
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from doodlerig import Rig, heuristic_joints, rig_from_mask
from doodlerig.joints import snap_inside, validate
from doodlerig.segment import Box, extract_character, find_characters, prepare_image

from . import vision

log = logging.getLogger(__name__)

THUMB = 240  # px, longest side of a picker thumbnail
# A few hundred KB of PNG can decode into gigabytes, so the pixel count is checked before decoding.
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow's own guard, for any decode that skips _open
NOT_A_PHOTO = "That doesn't look like a photo. Try taking it again."
NO_DRAWING = "I couldn't find a drawing. Try plain white paper, a dark outline, and good light."


def _open(photo: bytes, expect: tuple[int, int] | None = None) -> Image.Image:
    """Decode an uploaded picture, refusing a huge one (or one not `expect` = (w, h)) before decoding it."""
    try:
        im = Image.open(io.BytesIO(photo))  # reads the header only
    except (OSError, Image.DecompressionBombError):
        raise ValueError(NOT_A_PHOTO)
    # Checking here rather than via DecompressionBombWarning: warning filters aren't thread-safe.
    if im.width * im.height > MAX_PIXELS:
        raise ValueError("That picture is too big. Try a smaller photo.")
    if expect is not None and im.size != expect:
        raise ValueError(f"The painted cut-out is {im.size[0]}x{im.size[1]}, expected {expect[0]}x{expect[1]}.")
    try:
        im.load()
    except OSError:
        raise ValueError(NOT_A_PHOTO)
    return im


def _segmented(step, *args, **kwargs):
    """Run a segmentation step; a photo it can't cope with is a retake for the child, not a 500."""
    try:
        return step(*args, **kwargs)
    except ValueError:
        raise
    except Exception:
        log.exception("segmentation failed")
        raise ValueError(NO_DRAWING)


def _save_draft(rig: Rig, crop: np.ndarray, mask: np.ndarray, folder: Path) -> None:
    rig.save(folder)
    Image.fromarray(crop).save(folder / "crop.png")
    Image.fromarray(mask).save(folder / "mask.png")


def describe(rig: Rig, draft_id: str, seconds: float) -> dict:
    return {
        "id": draft_id,
        "width": int(rig.texture.shape[1]),
        "height": int(rig.texture.shape[0]),
        "joints": {k: [round(v[0], 1), round(v[1], 1)] for k, v in rig.joints.items()},
        "description": rig.description,
        "joints_from": rig.meta.get("joints_from", "heuristic"),
        "seconds": round(seconds, 2),
    }


def _thumb(img: np.ndarray, box: Box) -> str:
    """A small JPEG of one drawing, as a data URL the phone can show without another request."""
    x0, y0, x1, y1 = box
    im = Image.fromarray(img[y0:y1, x0:x1])
    im.thumbnail((THUMB, THUMB), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def candidates(photo: bytes) -> list[dict]:
    """Every drawing on the photo, biggest first: {box, thumb}. Boxes are what make_draft takes."""
    img = _segmented(prepare_image, _open(photo))
    return [{"box": [int(v) for v in b], "thumb": _thumb(img, b)}
            for b in _segmented(find_characters, _open(photo))]


def make_draft(photo: bytes, drafts: Path, box: Box | None = None) -> dict:
    """Cut out and rig one drawing: the one in `box` (from `candidates`), else the biggest."""
    t0 = time.perf_counter()
    crop, mask = _segmented(extract_character, _open(photo), box=None if box is None else tuple(box))
    if not mask.any() or mask.mean() < 255 * 0.02:
        raise ValueError(NO_DRAWING)
    info: dict = {}
    joints = vision.provider(crop, mask, info)
    rig = rig_from_mask(crop, mask, joints, info.get("description", ""),
                        {"joints_from": "vision" if joints else "heuristic"})
    draft_id = uuid.uuid4().hex[:12]
    folder = drafts / draft_id
    _save_draft(rig, crop, mask, folder)
    return describe(rig, draft_id, time.perf_counter() - t0)


def fix_joints(draft_id: str, joints: dict, drafts: Path) -> dict:
    """Rebuild a draft with joints the parent dragged (texture coordinates)."""
    if "root" not in joints or not all(len(v) == 2 and all(map(math.isfinite, v)) for v in joints.values()):
        raise ValueError("Those joints didn't come through right. Try dragging them again.")
    t0 = time.perf_counter()
    folder = drafts / draft_id
    old = Rig.load(folder)
    ox, oy = old.meta.get("crop_offset", [0, 0])
    crop = np.asarray(Image.open(folder / "crop.png").convert("RGB"))
    mask = np.asarray(Image.open(folder / "mask.png").convert("L"))
    in_crop = {k: (float(v[0]) + ox, float(v[1]) + oy) for k, v in joints.items()}
    in_crop["hip"] = in_crop["root"]
    rig = rig_from_mask(crop, mask, in_crop, old.description, {"joints_from": "parent"})
    _save_draft(rig, crop, mask, folder)
    return describe(rig, draft_id, time.perf_counter() - t0)


# --- The child's brush fixes to the cut-out -----------------------------------------------------

def _read_mask(data: bytes, shape: tuple[int, int]) -> np.ndarray:
    """A painted mask (white = keep; black or transparent = drop) as uint8 0/255 of crop size."""
    im = _open(data, expect=shape[::-1])
    keep = np.asarray(im.convert("L")) > 127
    if "A" in im.getbands():
        keep &= np.asarray(im.getchannel("A")) > 127
    return keep.astype(np.uint8) * 255


def tidy_mask(mask: np.ndarray) -> np.ndarray:
    """One piece, no pinholes: the biggest painted region, with brush-edge specks of hole filled.

    A puppet is one mesh, so a blob painted apart from the body is dropped. Holes the child
    erased on purpose (the gap between an arm and the body) are kept; only tiny ones are filled.
    """
    n, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    if n < 2:
        return np.zeros_like(mask)
    keep = labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    n, labels, stats, _ = cv2.connectedComponentsWithStats((~keep).astype(np.uint8), connectivity=4)
    h, w = mask.shape
    x, y, bw, bh, area = (stats[:, i] for i in range(5))
    inner = (x > 0) & (y > 0) & (x + bw < w) & (y + bh < h)
    small = inner & (area < 0.005 * keep.sum())
    small[0] = False
    keep |= small[labels]
    return keep.astype(np.uint8) * 255


def _reuse_joints(old: Rig, mask: np.ndarray) -> tuple[dict | None, str]:
    """The draft's joints in crop coordinates, where they still make sense on the new mask.

    Heuristic joints are guessed again from the new outline. Joints from the vision model or
    the parent are kept unless the brush took their part away (more than 5% of the drawing's
    size outside the new mask); those few are re-guessed. Anything that then fails the rig's
    sanity checks falls back to a fresh guess for all of them.
    """
    source = old.meta.get("joints_from", "heuristic")
    if source == "heuristic":
        return None, "heuristic"
    ox, oy = old.meta.get("crop_offset", [0, 0])
    inside = mask > 0
    ys, xs = np.nonzero(inside)
    size = max(xs.max() - xs.min(), ys.max() - ys.min()) + 1
    far = cv2.distanceTransform((~inside).astype(np.uint8), cv2.DIST_L2, 5)  # 0 inside the mask
    h, w = mask.shape
    joints, guess = {}, None
    for n, (x, y) in old.joints.items():
        cx, cy = float(x) + ox, float(y) + oy
        xi, yi = int(np.clip(round(cx), 0, w - 1)), int(np.clip(round(cy), 0, h - 1))
        if far[yi, xi] <= 0.05 * size:
            joints[n] = (cx, cy)
        else:
            guess = guess or heuristic_joints(mask)
            joints[n] = guess[n]
    joints["hip"] = joints["root"]
    if validate(snap_inside(mask, joints), mask):
        return None, "heuristic"
    return joints, source


def fix_mask(draft_id: str, mask_png: bytes, drafts: Path) -> dict:
    """Rebuild a draft from its crop and a cut-out mask the child painted (crop size PNG)."""
    t0 = time.perf_counter()
    folder = drafts / draft_id
    old = Rig.load(folder)
    crop = np.asarray(Image.open(folder / "crop.png").convert("RGB"))
    mask = tidy_mask(_read_mask(mask_png, crop.shape[:2]))
    if mask.mean() < 255 * 0.02:
        raise ValueError("There's hardly any drawing left. Tap Undo, or add some back.")
    joints, source = _reuse_joints(old, mask)
    rig = rig_from_mask(crop, mask, joints, old.description, {"joints_from": source, "mask_from": "parent"})
    _save_draft(rig, crop, mask, folder)
    return describe(rig, draft_id, time.perf_counter() - t0)


def draft_summary(draft_id: str, drafts: Path) -> dict:
    return json.loads((drafts / draft_id / "rig.json").read_text(encoding="utf-8"))
