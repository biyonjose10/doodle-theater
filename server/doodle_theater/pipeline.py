"""Photo from the phone -> draft puppet the parent can check, fix and send to the TV."""
from __future__ import annotations

import io
import json
import time
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from doodlerig import Rig, rig_from_mask
from doodlerig.segment import extract_character

from . import vision


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


def make_draft(photo: bytes, drafts: Path) -> dict:
    t0 = time.perf_counter()
    crop, mask = extract_character(Image.open(io.BytesIO(photo)))
    if not mask.any() or mask.mean() < 255 * 0.02:
        raise ValueError("I couldn't find a drawing. Try plain white paper, a dark outline, and good light.")
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
    t0 = time.perf_counter()
    folder = drafts / draft_id
    old = Rig.load(folder)
    ox, oy = old.meta.get("crop_offset", [0, 0])
    crop = np.asarray(Image.open(folder / "crop.png").convert("RGB"))
    mask = np.asarray(Image.open(folder / "mask.png").convert("L"))
    in_crop = {k: (float(v[0]) + ox, float(v[1]) + oy) for k, v in joints.items()}
    in_crop["hip"] = in_crop.get("root", in_crop.get("hip"))
    rig = rig_from_mask(crop, mask, in_crop, old.description, {"joints_from": "parent"})
    _save_draft(rig, crop, mask, folder)
    return describe(rig, draft_id, time.perf_counter() - t0)


def draft_summary(draft_id: str, drafts: Path) -> dict:
    return json.loads((drafts / draft_id / "rig.json").read_text(encoding="utf-8"))
