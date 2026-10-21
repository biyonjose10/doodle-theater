"""Reference implementation of posing: motion curves -> joint transforms -> skinned mesh.

The TV app (Kotlin) and the web preview (JS) port these few functions; the
tests here pin down the maths they must reproduce.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from importlib.resources import files

import numpy as np

from .joints import NAMES, PARENT


@lru_cache(maxsize=1)
def motions() -> dict:
    return json.loads(files("doodlerig").joinpath("motions.json").read_text(encoding="utf-8"))["motions"]


def _smooth(a: float) -> float:
    return a * a * (3 - 2 * a)


def eval_curve(curve: dict, t: float, duration: float) -> float:
    if "keys" in curve:
        keys = curve["keys"]
        if t <= keys[0][0]:
            return float(keys[0][1])
        for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
            if t <= t1:
                return v0 + (v1 - v0) * _smooth((t - t0) / max(t1 - t0, 1e-9))
        return float(keys[-1][1])
    (kind, (amp, cycles, phase, offset)), = curve.items()
    s = math.sin(2 * math.pi * (cycles * t / duration + phase))
    if kind == "abs_sin":
        s = abs(s)
    elif kind == "pos_sin":
        s = max(0.0, s)
    elif kind != "sin":
        raise ValueError(f"unknown curve {kind}")
    return offset + amp * s


def sample(name: str, t: float) -> tuple[np.ndarray, dict[str, float]]:
    """Joint angles (degrees, one per skeleton joint) and root channels at time t."""
    m = motions()[name]
    d = m["duration"]
    t = t % d if m["loop"] else min(max(t, 0.0), d)
    angles = np.zeros(len(NAMES))
    root = {"root.x": 0.0, "root.y": 0.0, "root.sx": 1.0, "root.sy": 1.0}
    for ch, curve in m["channels"].items():
        v = eval_curve(curve, t, d)
        if ch in root:
            root[ch] = v
        else:
            angles[NAMES.index(ch)] = v
    return angles, root


def _T(x, y):
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], dtype=np.float64)


def _R(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def _S(sx, sy):
    return np.diag([sx, sy, 1.0])


def skin_matrices(rest: np.ndarray, angles: np.ndarray, root: dict[str, float],
                  ground_y: float, height: float) -> np.ndarray:
    """One 3x3 matrix per joint mapping rest-pose points to posed points.

    Joints are listed parents-first, so one pass suffices.
    """
    world = np.empty((len(NAMES), 3, 3))
    r = rest[0]
    pivot = np.array([r[0], ground_y])
    off = np.array([root["root.x"], root["root.y"]]) * height
    world[0] = (_T(*(pivot + off)) @ _S(root["root.sx"], root["root.sy"])
                @ _T(*(r - pivot)) @ _R(angles[0]))
    for j in range(1, len(NAMES)):
        p = PARENT[j]
        world[j] = world[p] @ _T(*(rest[j] - rest[p])) @ _R(angles[j])
    return np.stack([world[j] @ _T(-rest[j][0], -rest[j][1]) for j in range(len(NAMES))])


def skin(vertices: np.ndarray, index: np.ndarray, weight: np.ndarray, mats: np.ndarray) -> np.ndarray:
    """Linear blend skinning: each vertex is the weighted mix of its joints' transforms."""
    hv = np.concatenate([vertices.astype(np.float64), np.ones((len(vertices), 1))], axis=1)
    out = np.zeros((len(vertices), 2))
    for k in range(index.shape[1]):
        m = mats[index[:, k]]                       # (N,3,3)
        out += weight[:, k:k + 1] * np.einsum("nij,nj->ni", m, hv)[:, :2]
    return out
