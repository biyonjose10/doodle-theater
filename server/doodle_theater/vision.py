"""Ask a Bedrock vision model where the drawing's joints are, and what it is.

The model only *proposes*: every point is checked against the cut-out mask, swapped
sides are corrected, and anything implausible falls back to doodlerig's silhouette
guess. The parent can still drag any dot on the phone.
"""
from __future__ import annotations

import io
import json
import logging
import re

import cv2
import numpy as np
from PIL import Image

from doodlerig import NAMES, heuristic_joints
from doodlerig.joints import snap_inside

from .config import AWS_REGION, VISION_MODEL

log = logging.getLogger(__name__)

PROMPT = """This is a child's drawing of a character, cut out onto a white background.
The image is {w} x {h} pixels. Give coordinates on a 0-1000 scale for x (left to right) and y (top to bottom).

1. Describe the character in one short, warm sentence a narrator could read aloud
   (colours, what it is, one fun detail). No names.
2. Locate these joints. "right_*" means the CHARACTER's right, which is on the LEFT side of the image.
   - root: centre of the hips, where the legs meet the body
   - torso: centre of the chest
   - neck: centre of the head
   - right_shoulder, right_elbow, right_hand (image-left arm; the hand is the far end)
   - left_shoulder, left_elbow, left_hand (image-right arm)
   - right_hip, right_knee, right_foot (image-left leg; the foot is the bottom end)
   - left_hip, left_knee, left_foot (image-right leg)
   If a part is missing (no arms, say), give your best guess inside the body.

Reply with JSON only:
{{"description": "...", "joints": {{"root": [x, y], "torso": [x, y], ...}}}}"""


def has_aws() -> bool:
    """True when boto3 can find credentials (env, ~/.aws, SSO). Checked once, cheaply."""
    global _HAS_AWS
    if _HAS_AWS is None:
        import boto3
        _HAS_AWS = boto3.Session().get_credentials() is not None
    return _HAS_AWS


_HAS_AWS: bool | None = None


def _bedrock():
    import boto3
    from botocore.config import Config
    return boto3.client("bedrock-runtime", region_name=AWS_REGION,
                        config=Config(read_timeout=40, retries={"max_attempts": 2}))


def _png(crop: np.ndarray, mask: np.ndarray) -> tuple[bytes, int, int]:
    """The character on white, at most 768 px: what the model sees."""
    img = crop.copy()
    img[mask == 0] = 255
    h, w = img.shape[:2]
    s = min(1.0, 768 / max(h, w))
    if s < 1:
        img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, "PNG")
    return buf.getvalue(), w, h


def ask(crop: np.ndarray, mask: np.ndarray) -> dict | None:
    """Raw model answer {description, joints (crop pixels)}, or None if unavailable."""
    if VISION_MODEL.lower() == "off" or not has_aws():
        return None
    png, w, h = _png(crop, mask)
    try:
        resp = _bedrock().converse(
            modelId=VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"image": {"format": "png", "source": {"bytes": png}}},
                {"text": PROMPT.format(w=w, h=h)},
            ]}],
            inferenceConfig={"maxTokens": 900, "temperature": 0},
        )
    except Exception as e:  # no credentials, no model access, throttled: all fall back
        log.warning("vision model unavailable: %s", e)
        return None
    text = "".join(c.get("text", "") for c in resp["output"]["message"]["content"])
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        joints = {k: (float(v[0]) / 1000 * w, float(v[1]) / 1000 * h) for k, v in data["joints"].items()}
    except (ValueError, KeyError, TypeError, IndexError):
        return None
    return {"description": str(data.get("description", ""))[:200], "joints": joints}


def merge(proposed: dict[str, tuple[float, float]], mask: np.ndarray) -> dict[str, tuple[float, float]]:
    """Model joints where they are plausible, the silhouette guess everywhere else."""
    guess = heuristic_joints(mask)
    size = float(max(mask.shape))
    out = dict(guess)
    for n in NAMES:
        p = proposed.get(n)
        if p is None or n == "hip":
            continue
        x, y = p
        xi, yi = int(np.clip(x, 0, mask.shape[1] - 1)), int(np.clip(y, 0, mask.shape[0] - 1))
        if mask[yi, xi] > 0:
            out[n] = (x, y)
        else:  # just outside the outline: accept if close, snapping inside below
            if np.hypot(x - guess[n][0], y - guess[n][1]) < 0.15 * size:
                out[n] = (x, y)
    out["hip"] = out["root"]
    # The commonest model slip: mirrored sides. Fix by swapping whole limbs.
    for limb in (("shoulder", "elbow", "hand"), ("hip", "knee", "foot")):
        r, l = f"right_{limb[-1]}", f"left_{limb[-1]}"
        if out[r][0] > out[l][0]:
            for part in limb:
                out[f"right_{part}"], out[f"left_{part}"] = out[f"left_{part}"], out[f"right_{part}"]
    return snap_inside(mask, out)


def provider(crop: np.ndarray, mask: np.ndarray, sink: dict | None = None):
    """doodlerig JointProvider. Puts the description in `sink` when given."""
    ans = ask(crop, mask)
    if ans is None:
        return None
    if sink is not None:
        sink["description"] = ans["description"]
    return merge(ans["joints"], mask)
