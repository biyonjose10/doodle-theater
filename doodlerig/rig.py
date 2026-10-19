"""The Rig: everything a renderer needs to animate one drawing, and its file format."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image

from .joints import NAMES, PARENT, SKELETON, Joints, heuristic_joints, snap_inside, validate
from .mesh import build_mesh
from .segment import extract_character, whiten
from .weights import compute_weights

FORMAT_VERSION = 1

# Draw order: legs behind the body, arms in front of it.
_LAYER = {name: 1 for name in NAMES}
_LAYER.update({n: 0 for n in ("right_hip", "left_hip", "right_knee", "left_knee")})
_LAYER.update({n: 2 for n in ("right_shoulder", "left_shoulder", "right_elbow", "left_elbow")})

# A joint provider looks at the character crop (+ its mask) and returns joints,
# or None to fall back to the silhouette heuristic. A vision model plugs in here.
JointProvider = Callable[[np.ndarray, np.ndarray], "Joints | None"]


@dataclass
class Rig:
    texture: np.ndarray            # H x W x 4 RGBA, character only
    joints: Joints                 # texture pixel coords
    vertices: np.ndarray           # N x 2 float32, texture pixel coords
    triangles: np.ndarray          # M x 3 int32, in draw order
    bone_index: np.ndarray         # N x 2 int32, skeleton joint indices
    bone_weight: np.ndarray        # N x 2 float32, rows sum to 1
    ground_y: float                # y of the feet, the pivot for squash and stretch
    description: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def height(self) -> float:
        return float(np.ptp(self.vertices[:, 1]))

    def rest(self) -> np.ndarray:
        return np.array([self.joints[n] for n in NAMES], dtype=np.float64)

    def to_json(self) -> dict:
        r2 = lambda a: [round(float(x), 2) for x in np.asarray(a).ravel()]
        return {
            "format": "doodlerig",
            "version": FORMAT_VERSION,
            "texture": "texture.png",
            "width": int(self.texture.shape[1]),
            "height": int(self.texture.shape[0]),
            "ground_y": round(float(self.ground_y), 2),
            "skeleton": [{"name": n, "parent": p, "x": round(self.joints[n][0], 2),
                          "y": round(self.joints[n][1], 2)} for n, p in SKELETON],
            "vertices": r2(self.vertices),
            "triangles": [int(i) for i in self.triangles.ravel()],
            "influences": {"joints": [int(i) for i in self.bone_index.ravel()],
                           "weights": [round(float(w), 4) for w in self.bone_weight.ravel()]},
            "description": self.description,
            "meta": self.meta,
        }

    def save(self, out_dir: str | Path) -> Path:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.texture, "RGBA").save(out / "texture.png", optimize=True)
        (out / "rig.json").write_text(json.dumps(self.to_json(), separators=(",", ":")), encoding="utf-8")
        return out / "rig.json"

    @classmethod
    def load(cls, path: str | Path) -> "Rig":
        path = Path(path)
        if path.is_dir():
            path = path / "rig.json"
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("format") != "doodlerig" or d.get("version") != FORMAT_VERSION:
            raise ValueError(f"not a doodlerig v{FORMAT_VERSION} file: {path}")
        tex = np.asarray(Image.open(path.parent / d["texture"]).convert("RGBA"))
        return cls(
            texture=tex,
            joints={j["name"]: (j["x"], j["y"]) for j in d["skeleton"]},
            vertices=np.array(d["vertices"], np.float32).reshape(-1, 2),
            triangles=np.array(d["triangles"], np.int32).reshape(-1, 3),
            bone_index=np.array(d["influences"]["joints"], np.int32).reshape(-1, 2),
            bone_weight=np.array(d["influences"]["weights"], np.float32).reshape(-1, 2),
            ground_y=d["ground_y"],
            description=d.get("description", ""),
            meta=d.get("meta", {}),
        )


def _order_triangles(tris: np.ndarray, idx: np.ndarray, w: np.ndarray) -> np.ndarray:
    top = idx[np.arange(len(idx)), np.argmax(w, axis=1)]          # strongest joint per vertex
    layer = np.array([_LAYER[NAMES[j]] for j in top])
    tri_layer = np.max(layer[tris], axis=1)
    return tris[np.argsort(tri_layer, kind="stable")]


def rig_from_mask(crop: np.ndarray, mask: np.ndarray, joints: Joints | None = None,
                  description: str = "", meta: dict | None = None) -> Rig:
    """Build a rig from an RGB crop and its character mask (same size)."""
    ys, xs = np.nonzero(mask)
    size = max(xs.max() - xs.min(), ys.max() - ys.min()) + 1
    pad = int(0.04 * size) + 2
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(mask.shape[1], xs.max() + pad + 1), min(mask.shape[0], ys.max() + pad + 1)
    crop, mask = crop[y0:y1, x0:x1], mask[y0:y1, x0:x1]
    if joints is not None:
        joints = snap_inside(mask, {n: (x - x0, y - y0) for n, (x, y) in joints.items()})
    else:
        joints = heuristic_joints(mask)
    problems = validate(joints, mask)
    if problems:
        raise ValueError("; ".join(problems))

    rgb = whiten(crop, mask)
    alpha = cv2.GaussianBlur(mask, (3, 3), 0)
    texture = np.dstack([rgb, alpha]).astype(np.uint8)

    verts, tris = build_mesh(mask)
    idx, w = compute_weights(verts, tris, joints)
    tris = _order_triangles(tris, idx, w)
    ground = float(max(joints["right_foot"][1], joints["left_foot"][1], np.percentile(verts[:, 1], 99)))
    return Rig(texture, joints, verts, tris, idx, w, ground, description, meta or {})


def build_rig(src, joints: Joints | None = None, joint_provider: JointProvider | None = None,
              already_cropped: bool = False, description: str = "") -> Rig:
    """Photo of a drawing -> Rig.

    `joints` (in crop coordinates) wins over `joint_provider`, which wins over the heuristic.
    """
    crop, mask = extract_character(src, already_cropped=already_cropped)
    if not mask.any():
        raise ValueError("no character found: is the drawing outlined in dark marker on plain paper?")
    source = "given"
    if joints is None and joint_provider is not None:
        joints = joint_provider(crop, mask)
        source = "provider" if joints else "heuristic"
    elif joints is None:
        source = "heuristic"
    return rig_from_mask(crop, mask, joints, description, {"joints_from": source})


__all__ = ["Rig", "build_rig", "rig_from_mask", "JointProvider", "PARENT"]
