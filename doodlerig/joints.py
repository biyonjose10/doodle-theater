"""The skeleton, a model-free joint guess, and joint validation.

Joint names and hierarchy match Meta AnimatedDrawings' `char_cfg.yaml`, so
annotations move freely between the two projects. As there, `right_*` is the
character's right, which is on the LEFT of the image when it faces the viewer.
The `neck` joint sits inside the head; the torso->neck bone carries the head.
"""
from __future__ import annotations

import cv2
import numpy as np

SKELETON: list[tuple[str, str | None]] = [
    ("root", None),
    ("hip", "root"),
    ("torso", "hip"),
    ("neck", "torso"),
    ("right_shoulder", "torso"),
    ("right_elbow", "right_shoulder"),
    ("right_hand", "right_elbow"),
    ("left_shoulder", "torso"),
    ("left_elbow", "left_shoulder"),
    ("left_hand", "left_elbow"),
    ("right_hip", "root"),
    ("right_knee", "right_hip"),
    ("right_foot", "right_knee"),
    ("left_hip", "root"),
    ("left_knee", "left_hip"),
    ("left_foot", "left_knee"),
]
NAMES = [n for n, _ in SKELETON]
INDEX = {n: i for i, n in enumerate(NAMES)}
PARENT = [None if p is None else INDEX[p] for _, p in SKELETON]

Joints = dict[str, tuple[float, float]]


def _runs(row: np.ndarray) -> list[tuple[int, int]]:
    """Start/end (inclusive) of each run of True in a 1-D boolean row."""
    d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1))


def snap_inside(mask: np.ndarray, joints: Joints) -> Joints:
    """Move any joint that fell outside the mask to the nearest pixel inside it."""
    inside = mask > 0
    _, labels = cv2.distanceTransformWithLabels(
        (~inside).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(inside)
    lut = np.zeros(labels.max() + 1, dtype=np.int64)
    lut[labels[ys, xs]] = np.arange(len(xs))
    h, w = mask.shape
    out: Joints = {}
    for name, (x, y) in joints.items():
        xi, yi = int(np.clip(round(x), 0, w - 1)), int(np.clip(round(y), 0, h - 1))
        if inside[yi, xi]:
            out[name] = (float(x), float(y))
        else:
            k = lut[labels[yi, xi]]
            out[name] = (float(xs[k]), float(ys[k]))
    return out


def _legs(inside: np.ndarray, y0: int, y1: int, H: int):
    """Follow the two legs up from the feet to where they join: (crotch_y, crotch_x, foot, foot).

    The feet are the two lowest-reaching pieces of the silhouette once the bottom is cut off;
    the crotch is the highest cut that still keeps them apart. Unlike splitting at a centre
    line, this survives one foot reaching lower and across the middle, a tail, or a centre
    line that runs down one leg. None when the legs never separate (a dress, a blob).
    """
    min_area = 0.002 * inside.sum()
    stop = int(y0 + 0.35 * H)

    def pieces(y):
        _, lab, stats, _ = cv2.connectedComponentsWithStats(inside[y:].astype(np.uint8), connectivity=8)
        big = [i for i in range(1, len(stats)) if stats[i, cv2.CC_STAT_AREA] >= min_area]
        return lab, stats, big

    feet = anchors = None
    for y in range(int(y1 - 0.08 * H), stop, -2):
        lab, stats, big = pieces(y)
        if len(big) >= 2:
            low = sorted(big, key=lambda i: stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT])[-2:]
            feet, anchors = [], []
            for i in low:
                py, px = np.nonzero(lab == i)
                bottom = py.max()
                feet.append((float(np.median(px[py >= bottom - 2])), float(bottom + y)))
                k = int(np.argmin(py))  # a pixel of this leg that every higher cut still contains
                anchors.append((int(py[k]) + y, int(px[k])))
            break
    if feet is None:
        return None

    crotch = None
    for y in range(max(a[0] for a in anchors), stop, -2):
        lab, stats, _ = pieces(y)
        a, b = (lab[ay - y, ax] for ay, ax in anchors)
        if a == 0 or b == 0 or a == b:
            break
        # The gap between the legs on the top row of this cut.
        xa, xb = np.nonzero(lab[0] == a)[0], np.nonzero(lab[0] == b)[0]
        if len(xa) and len(xb):
            left, right = (xa, xb) if xa.mean() < xb.mean() else (xb, xa)
            crotch = (y, (left.max() + right.min()) / 2)
    if crotch is None:
        return None
    feet.sort()
    return crotch[0], crotch[1], feet[0], feet[1]


def heuristic_joints(mask: np.ndarray) -> Joints:
    """Guess the 16 joints from the silhouette alone.

    Tuned for what children draw: a standing figure, facing forward, arms out
    and legs apart. It is a starting point; a vision model or the parent's
    drag-to-fix refines it.
    """
    inside = mask > 0
    ys, xs = np.nonzero(inside)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    H = y1 - y0 + 1

    band = (ys > y0 + 0.3 * H) & (ys < y0 + 0.6 * H)
    cx = float(np.median(xs[band])) if band.any() else float((x0 + x1) / 2)
    cxi = int(round(cx))

    # Crotch: the highest row in the lower body where the mask splits around the centre line.
    root_y = None
    for y in range(int(y1), int(y0 + 0.35 * H), -1):
        runs = _runs(inside[y])
        left = any(e < cxi for _, e in runs)
        right = any(s > cxi for s, _ in runs)
        if left and right and not inside[y, cxi]:
            root_y = y
        elif root_y is not None and inside[y, cxi]:
            break
    if root_y is None:
        root_y = int(y0 + 0.62 * H)
    root = (cx, float(root_y))
    legs = _legs(inside, int(y0), int(y1), int(H))
    if legs is not None:
        root = (float(legs[1]), float(legs[0]))

    # Top of head: highest mask pixel near the centre line.
    near = np.abs(xs - cx) < 0.15 * (x1 - x0 + 1)
    head_top = float(ys[near].min()) if near.any() else float(y0)
    span = root[1] - head_top
    neck = (cx, head_top + 0.2 * span)
    torso = (cx, head_top + 0.55 * span)

    # Hands live above the crotch; weight sideways reach over height so a knee never wins.
    upper = ys < root[1] - 0.04 * H
    tx, ty = torso

    def farthest(sel):
        if not sel.any():
            return None
        d = (xs[sel] - tx) ** 2 + (0.6 * (ys[sel] - ty)) ** 2
        i = int(np.argmax(d))
        return float(xs[sel][i]), float(ys[sel][i])

    right_hand = farthest(upper & (xs < cx)) or (float(x0), ty)
    left_hand = farthest(upper & (xs > cx)) or (float(x1), ty)

    def lowest(sel, fallback):
        if not sel.any():
            return fallback
        yy = ys[sel].max()
        xx = xs[sel][ys[sel] >= yy - 2]
        return float(np.median(xx)), float(yy)

    if legs is not None:
        right_foot, left_foot = legs[2], legs[3]
    else:
        lower = ys > root[1]
        right_foot = lowest(lower & (xs < cx), (cx - 0.15 * H, float(y1)))
        left_foot = lowest(lower & (xs > cx), (cx + 0.15 * H, float(y1)))

    # Shoulders: where the arm leaves the body, on the torso row.
    row = inside[int(round(ty))]
    run = next(((s, e) for s, e in _runs(row) if s <= cxi <= e), (cxi - 1, cxi + 1))
    body_half = max(4.0, min(cx - run[0], run[1] - cx, 0.25 * H))
    sy = ty - 0.25 * (ty - neck[1])
    right_shoulder = (cx - 0.8 * body_half, sy)
    left_shoulder = (cx + 0.8 * body_half, sy)

    def mid(a, b, t=0.5):
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t

    right_hip = (root[0] + 0.35 * (right_foot[0] - root[0]), root[1] + 0.03 * H)
    left_hip = (root[0] + 0.35 * (left_foot[0] - root[0]), root[1] + 0.03 * H)

    joints: Joints = {
        "root": root,
        "hip": root,
        "torso": torso,
        "neck": neck,
        "right_shoulder": right_shoulder,
        "right_elbow": mid(right_shoulder, right_hand),
        "right_hand": right_hand,
        "left_shoulder": left_shoulder,
        "left_elbow": mid(left_shoulder, left_hand),
        "left_hand": left_hand,
        "right_hip": right_hip,
        "right_knee": mid(right_hip, right_foot),
        "right_foot": right_foot,
        "left_hip": left_hip,
        "left_knee": mid(left_hip, left_foot),
        "left_foot": left_foot,
    }
    return snap_inside(mask, joints)


def validate(joints: Joints, mask: np.ndarray) -> list[str]:
    """Problems that would make the rig misbehave. Empty list = fine."""
    problems = [f"missing joint: {n}" for n in NAMES if n not in joints]
    if problems:
        return problems
    h, w = mask.shape
    for n in NAMES:
        x, y = joints[n]
        if not (0 <= x < w and 0 <= y < h):
            problems.append(f"{n} is outside the image")
    if joints["neck"][1] >= joints["root"][1]:
        problems.append("neck is below the root (upside down?)")
    if joints["right_hand"][0] > joints["left_hand"][0]:
        problems.append("hands are swapped: right_hand should be on the image's left")
    return problems


def from_animated_drawings(cfg: dict) -> Joints:
    """Read joints from an AnimatedDrawings char_cfg (already parsed from YAML)."""
    return {j["name"]: (float(j["loc"][0]), float(j["loc"][1])) for j in cfg["skeleton"]}


def to_animated_drawings(joints: Joints, width: int, height: int) -> dict:
    """The inverse: a char_cfg dict that AnimatedDrawings can load."""
    return {
        "width": int(width),
        "height": int(height),
        "skeleton": [
            {"name": n, "parent": p, "loc": [int(round(joints[n][0])), int(round(joints[n][1]))]}
            for n, p in SKELETON
        ],
    }
