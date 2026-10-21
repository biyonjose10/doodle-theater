"""CPU renderer for previews and tests (the TV and web renderers use the GPU / canvas)."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from .joints import NAMES, PARENT
from .pose import motions, sample, skin, skin_matrices
from .rig import Rig


def posed_vertices(rig: Rig, motion: str | None = None, t: float = 0.0) -> np.ndarray:
    if motion is None:
        return rig.vertices.astype(np.float64)
    angles, root = sample(motion, t)
    mats = skin_matrices(rig.rest(), angles, root, rig.ground_y, rig.height)
    return skin(rig.vertices, rig.bone_index, rig.bone_weight, mats)


def draw(rig: Rig, verts: np.ndarray, size: tuple[int, int], offset=(0.0, 0.0), scale=1.0,
         background=(255, 255, 255, 0)) -> np.ndarray:
    """Rasterise the textured mesh at `verts` into an RGBA image of (w, h)."""
    w, h = size
    canvas = np.zeros((h, w, 4), np.float32)
    canvas[:] = background
    tex = rig.texture.astype(np.float32)
    src_all = rig.vertices.astype(np.float32)
    dst_all = (verts * scale + np.asarray(offset)).astype(np.float32)
    for tri in rig.triangles:
        src, dst = src_all[tri], dst_all[tri]
        sx, sy, sw, sh = cv2.boundingRect(src)
        dx, dy, dw, dh = cv2.boundingRect(dst)
        if dw <= 0 or dh <= 0:
            continue
        x0, y0, x1, y1 = max(dx, 0), max(dy, 0), min(dx + dw, w), min(dy + dh, h)
        if x0 >= x1 or y0 >= y1:
            continue
        m = cv2.getAffineTransform((src - [sx, sy]).astype(np.float32), (dst - [dx, dy]).astype(np.float32))
        patch = cv2.warpAffine(tex[sy:sy + sh + 1, sx:sx + sw + 1], m, (dw, dh),
                               flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        cover = np.zeros((dh, dw), np.uint8)
        cv2.fillConvexPoly(cover, np.round((dst - [dx, dy]) * 4).astype(np.int32), 1, cv2.LINE_8, 2)
        cover = cv2.dilate(cover, np.ones((2, 2), np.uint8))  # hide hairline seams
        sub = (slice(y0 - dy, y1 - dy), slice(x0 - dx, x1 - dx))
        a = patch[sub][..., 3:4] / 255.0 * cover[sub][..., None]
        region = canvas[y0:y1, x0:x1]
        region[..., :3] = patch[sub][..., :3] * a + region[..., :3] * (1 - a)
        region[..., 3:4] = 255 * a + region[..., 3:4] * (1 - a)
    return np.clip(canvas, 0, 255).astype(np.uint8)


def overlay(rig: Rig) -> np.ndarray:
    """Texture with the mesh, bones and joints drawn on top: for checking a rig by eye."""
    img = rig.texture[..., :3].copy()
    a = rig.texture[..., 3:4] / 255.0
    img = (img * a + 255 * (1 - a)).astype(np.uint8)
    v = rig.vertices
    for tri in rig.triangles:
        cv2.polylines(img, [np.round(v[tri]).astype(np.int32)], True, (190, 190, 255), 1, cv2.LINE_AA)
    pts = rig.rest()
    for j, p in enumerate(PARENT):
        if p is not None:
            cv2.line(img, tuple(np.round(pts[p]).astype(int)), tuple(np.round(pts[j]).astype(int)),
                     (40, 160, 40), 2, cv2.LINE_AA)
    for j, n in enumerate(NAMES):
        colour = (220, 40, 40) if n.startswith("right") else (40, 80, 220) if n.startswith("left") else (30, 30, 30)
        cv2.circle(img, tuple(np.round(pts[j]).astype(int)), 5, colour, -1, cv2.LINE_AA)
    return img


def contact_sheet(rig: Rig, names: list[str] | None = None, frames: int = 5, cell: int = 220) -> np.ndarray:
    """A grid: one row per motion, `frames` evenly spaced poses per row, on white."""
    names = names or list(motions())
    sheet = np.full((cell * len(names), cell * (frames + 1), 3), 255, np.uint8)
    scale = 0.62 * cell / max(rig.texture.shape[:2])
    for r, name in enumerate(names):
        cv2.putText(sheet, name, (8, r * cell + cell // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 60), 2)
        d = motions()[name]["duration"]
        for c in range(frames):
            t = d * c / frames
            v = posed_vertices(rig, name, t)
            cx = (c + 1) * cell + cell / 2 - rig.texture.shape[1] * scale / 2
            cy = r * cell + cell * 0.82 - rig.ground_y * scale
            rgba = draw(rig, v, (cell, cell), (cx - (c + 1) * cell, cy - r * cell), scale)
            a = rgba[..., 3:4] / 255.0
            tile = sheet[r * cell:(r + 1) * cell, (c + 1) * cell:(c + 2) * cell]
            tile[:] = (rgba[..., :3] * a + tile * (1 - a)).astype(np.uint8)
    return sheet


def gif(rig: Rig, motion: str, path, fps: int = 20, seconds: float | None = None, size: int = 360) -> None:
    d = seconds or motions()[motion]["duration"] * (2 if motions()[motion]["loop"] else 1)
    scale = 0.6 * size / max(rig.texture.shape[:2])
    frames = []
    for i in range(int(d * fps)):
        v = posed_vertices(rig, motion, i / fps)
        off = (size / 2 - rig.texture.shape[1] * scale / 2, size * 0.85 - rig.ground_y * scale)
        rgba = draw(rig, v, (size, size), off, scale, background=(255, 255, 255, 255))
        frames.append(Image.fromarray(rgba[..., :3]))
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0)
