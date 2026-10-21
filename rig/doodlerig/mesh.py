"""Triangulate a character mask into a mesh that bends without tearing."""
from __future__ import annotations

import cv2
import numpy as np
from scipy.spatial import Delaunay


def _resample(contour: np.ndarray, step: float) -> np.ndarray:
    """Evenly spaced points along a closed contour."""
    pts = contour.reshape(-1, 2).astype(np.float64)
    seg = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    n = max(8, int(total / step))
    t = np.linspace(0, total, n, endpoint=False)
    closed = np.vstack([pts, pts[:1]])
    x = np.interp(t, cum, closed[:, 0])
    y = np.interp(t, cum, closed[:, 1])
    return np.stack([x, y], axis=1)


def build_mesh(mask: np.ndarray, step: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (vertices float32 Nx2 in pixel coords, triangles int32 Mx3).

    Points: the outline resampled every `step` px plus an interior grid. Delaunay
    triangulates the convex hull, so triangles that bridge a gap (between an arm
    and the body, say) are dropped by testing points along every edge.
    """
    inside = mask > 0
    ys, xs = np.nonzero(inside)
    size = max(xs.max() - xs.min(), ys.max() - ys.min()) + 1
    step = step or max(3.0, size / 45.0)

    contours, _ = cv2.findContours(inside.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    outline = _resample(max(contours, key=cv2.contourArea), step)

    dist = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5)
    gx = np.arange(xs.min() + step / 2, xs.max(), step)
    gy = np.arange(ys.min() + step / 2, ys.max(), step)
    GX, GY = np.meshgrid(gx, gy)
    gxi, gyi = GX.round().astype(int), GY.round().astype(int)
    keep = dist[gyi, gxi] > 0.5 * step
    grid = np.stack([GX[keep], GY[keep]], axis=1)

    pts = np.vstack([outline, grid])
    pts = np.unique(np.round(pts, 2), axis=0)
    tri = Delaunay(pts).simplices

    # A 1-px grown mask so edges lying exactly on the outline still count as inside.
    grown = cv2.dilate(inside.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    h, w = mask.shape

    def inside_at(p):
        xi = np.clip(np.round(p[..., 0]).astype(int), 0, w - 1)
        yi = np.clip(np.round(p[..., 1]).astype(int), 0, h - 1)
        return grown[yi, xi]

    a, b, c = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
    ok = inside_at((a + b + c) / 3)
    for p, q in ((a, b), (b, c), (c, a)):
        for t in (0.25, 0.5, 0.75):
            ok &= inside_at(p + (q - p) * t)
    tri = tri[ok]

    used = np.unique(tri)
    remap = -np.ones(len(pts), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return pts[used].astype(np.float32), remap[tri].astype(np.int32)
