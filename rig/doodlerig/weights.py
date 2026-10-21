"""Skin weights: which joints move each mesh vertex, and by how much.

Distances are measured THROUGH the mesh (geodesic), not in a straight line, so
a hand resting near the belly still follows the arm, not the torso.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from .joints import NAMES, PARENT, Joints

MAX_INFLUENCES = 2


def bones(joints: Joints) -> list[tuple[int, np.ndarray, np.ndarray]]:
    """(driver joint index, start, end) for every non-degenerate parent->child bone.

    A bone moves with its PARENT joint's transform: the upper arm turns about the shoulder.
    """
    out = []
    for i, p in enumerate(PARENT):
        if p is None:
            continue
        a = np.array(joints[NAMES[p]], dtype=np.float64)
        b = np.array(joints[NAMES[i]], dtype=np.float64)
        if np.linalg.norm(b - a) > 1e-6:
            out.append((p, a, b))
    return out


def _point_segment_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0.0, 1.0)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def compute_weights(vertices: np.ndarray, triangles: np.ndarray, joints: Joints,
                    falloff: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (indices int32 Nx2, weights float32 Nx2), indices into the skeleton's joints."""
    v = vertices.astype(np.float64)
    n = len(v)
    # Each edge once: an interior edge belongs to two triangles, and the sparse matrix would
    # SUM the duplicates, making the interior cost twice the outline and bending every
    # geodesic out to the rim. Edges used by only one triangle form the outline.
    e, count = np.unique(np.sort(np.vstack([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]),
                                 axis=1), axis=0, return_counts=True)
    lengths = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    graph = coo_matrix((np.concatenate([lengths, lengths]),
                        (np.concatenate([e[:, 0], e[:, 1]]), np.concatenate([e[:, 1], e[:, 0]]))),
                       shape=(n, n)).tocsr()
    tree = cKDTree(v)
    size = float(np.ptp(v, axis=0).max())
    falloff = falloff or 0.05 * size

    rim = cKDTree(v[np.unique(e[count == 1])])

    bl = bones(joints)
    dist = np.empty((n, len(bl)))
    for k, (_, a, b) in enumerate(bl):
        samples = a + (b - a) * np.linspace(0, 1, max(3, int(np.linalg.norm(b - a) / 3) + 1))[:, None]
        _, seeds = tree.query(samples)
        seeds = np.unique(seeds)
        geo = dijkstra(graph, directed=False, indices=seeds, min_only=True)
        # Add how far the seed vertex sits from the bone itself; fall back to straight-line
        # distance for islands the mesh does not connect.
        straight = _point_segment_dist(v, a, b)
        geo = np.where(np.isfinite(geo), geo + _point_segment_dist(v[seeds], a, b).min(), np.inf)
        d = np.where(np.isfinite(geo), np.maximum(geo, straight), straight * 3 + size)
        # Treat the bone as a capsule as thick as the drawing around it and measure to its
        # surface. A stick skeleton says nothing about width: on a fat body the flank under an
        # arm is as near the thin upper-arm bone as the torso bone (both reach it through the
        # shoulder), so it got dragged up with the arm. Measured to the surfaces, the fat torso
        # capsule is clearly nearer and the flank stays put.
        dist[:, k] = d - np.median(rim.query(samples)[0])

    # Collapse bones to their driver joint (several bones can share one, e.g. the torso).
    drivers = sorted({d for d, _, _ in bl})
    jd = np.full((n, len(drivers)), np.inf)
    for k, (d, _, _) in enumerate(bl):
        c = drivers.index(d)
        jd[:, c] = np.minimum(jd[:, c], dist[:, k])

    order = np.argsort(jd, axis=1)[:, :MAX_INFLUENCES]
    best = np.take_along_axis(jd, order, axis=1)
    w = np.exp(-(best - best[:, :1]) / falloff)
    w /= w.sum(axis=1, keepdims=True)
    idx = np.array(drivers)[order]
    return idx.astype(np.int32), w.astype(np.float32)
