"""Sample stars: three ready-made characters for anyone without a drawing to hand.

Built from `samples/` at the repo root (AnimatedDrawings' MIT example drawings, see its
NOTICE.md) through the same rig builder and cast store a phone upload goes through.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from doodlerig import rig_from_mask

from .config import SERVER_DIR
from .pipeline import _save_draft
from .store import Store

SAMPLES = Path(os.environ.get("DT_SAMPLES", SERVER_DIR.parent / "samples"))


def catalogue(folder: Path = SAMPLES) -> list[dict]:
    return json.loads((folder / "samples.json").read_text(encoding="utf-8"))


def _on_white(img: Image.Image) -> np.ndarray:
    rgba = img.convert("RGBA")
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return np.asarray(Image.alpha_composite(white, rgba).convert("RGB"))


def add_samples(store: Store, folder: Path = SAMPLES) -> list[dict]:
    """Add every sample star not already in the cast; return the ones added (idempotent)."""
    have = {c["id"] for c in store.cast()}
    added = []
    for s in catalogue(folder):
        if s["id"] in have:
            continue
        crop = _on_white(Image.open(folder / s["drawing"]))
        mask = np.asarray(Image.open(folder / s["mask"]).convert("L"))
        mask = np.where(mask > 127, 255, 0).astype(np.uint8)
        joints = {k: (float(v[0]), float(v[1])) for k, v in s["joints"].items()}
        rig = rig_from_mask(crop, mask, joints, s["description"], {"joints_from": "sample"})
        _save_draft(rig, crop, mask, store.drafts / s["id"])
        added.append(store.add_to_cast(s["id"], s["name"], s["description"]))
    return added
