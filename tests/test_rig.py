"""Tests run against Meta AnimatedDrawings' MIT-licensed example drawings (tests/fixtures)."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from doodlerig import NAMES, Rig, build_rig
from doodlerig.joints import from_animated_drawings, heuristic_joints, snap_inside, to_animated_drawings, validate
from doodlerig.mesh import build_mesh
from doodlerig.pose import motions, sample, skin, skin_matrices
from doodlerig.render import draw, posed_vertices
from doodlerig.segment import extract_character
from doodlerig.weights import compute_weights

FIX = Path(__file__).parent / "fixtures"
HUMANOIDS = ["char1", "char2", "char3"]


def _yaml(path: Path) -> dict:
    """Tiny reader for the fixtures' char_cfg.yaml (avoids a PyYAML dependency)."""
    lines = path.read_text().splitlines()
    cfg: dict = {"skeleton": []}
    cur: dict | None = None
    for i, line in enumerate(lines):
        s = line.strip()
        if line.startswith(("height:", "width:")):
            k, v = s.split(":")
            cfg[k] = int(v)
        elif s == "- loc:":
            cur = {"loc": [int(lines[i + 1].strip("- ")), int(lines[i + 2].strip("- "))]}
            cfg["skeleton"].append(cur)
        elif s.startswith("name:") and cur is not None:
            cur["name"] = s.split(":", 1)[1].strip()
    return cfg


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a > 0, b > 0
    return float((a & b).sum() / max((a | b).sum(), 1))


@pytest.fixture(scope="module", params=HUMANOIDS)
def humanoid(request):
    name = request.param
    crop, mask = extract_character(FIX / f"{name}_texture.png", already_cropped=True)
    return name, crop, mask


def test_segmentation_matches_reference_masks(humanoid):
    name, _, mask = humanoid
    ref = cv2.imread(str(FIX / f"{name}_mask.png"), cv2.IMREAD_GRAYSCALE)
    ref = cv2.resize(ref, (mask.shape[1], mask.shape[0]), interpolation=cv2.INTER_NEAREST)
    assert _iou(mask, ref) > 0.85


def test_heuristic_joints_land_near_hand_annotations(humanoid):
    name, _, mask = humanoid
    truth = from_animated_drawings(_yaml(FIX / f"{name}_cfg.yaml"))
    guess = heuristic_joints(mask)
    assert validate(guess, mask) == []
    h = mask.shape[0]
    sx = mask.shape[1] / _yaml(FIX / f"{name}_cfg.yaml")["width"]
    sy = mask.shape[0] / _yaml(FIX / f"{name}_cfg.yaml")["height"]
    ends = ["right_hand", "left_hand", "right_foot", "left_foot", "neck", "root"]
    err = [np.hypot(guess[n][0] - truth[n][0] * sx, guess[n][1] - truth[n][1] * sy) / h for n in ends]
    assert np.mean(err) < 0.12, dict(zip(ends, np.round(err, 3)))


def test_mesh_stays_inside_the_drawing(humanoid):
    _, _, mask = humanoid
    v, t = build_mesh(mask)
    assert 100 < len(v) < 5000
    cent = v[t].mean(axis=1).round().astype(int)
    assert (mask[cent[:, 1], cent[:, 0]] > 0).mean() > 0.99
    cover = np.zeros_like(mask)
    for tri in t:
        cv2.fillConvexPoly(cover, np.round(v[tri]).astype(np.int32), 255)
    assert _iou(cover, mask) > 0.9


def test_weights_are_normalised_and_follow_the_limbs(humanoid):
    _, _, mask = humanoid
    joints = heuristic_joints(mask)
    v, t = build_mesh(mask)
    idx, w = compute_weights(v, t, joints)
    assert np.allclose(w.sum(axis=1), 1.0, atol=1e-5)
    for hand, driver in (("right_hand", "right_elbow"), ("left_hand", "left_elbow"),
                         ("right_foot", "right_knee"), ("left_foot", "left_knee")):
        k = int(np.argmin(np.linalg.norm(v - np.array(joints[hand]), axis=1)))
        top = idx[k][np.argmax(w[k])]
        assert NAMES[top] == driver, (hand, NAMES[top])


@pytest.fixture(scope="module")
def rig() -> Rig:
    return build_rig(FIX / "char1_texture.png", already_cropped=True)


def test_rest_pose_is_identity(rig):
    angles = np.zeros(len(NAMES))
    root = {"root.x": 0.0, "root.y": 0.0, "root.sx": 1.0, "root.sy": 1.0}
    mats = skin_matrices(rig.rest(), angles, root, rig.ground_y, rig.height)
    assert np.allclose(skin(rig.vertices, rig.bone_index, rig.bone_weight, mats), rig.vertices, atol=1e-4)


def test_rest_render_reproduces_the_cutout(rig):
    h, w = rig.texture.shape[:2]
    out = draw(rig, rig.vertices.astype(np.float64), (w, h))
    assert _iou(out[..., 3] > 128, rig.texture[..., 3] > 128) > 0.95


def test_every_motion_moves_and_stays_finite(rig):
    for name, m in motions().items():
        moved = 0.0
        for t in np.linspace(0, m["duration"], 7):
            v = posed_vertices(rig, name, float(t))
            assert np.isfinite(v).all()
            moved = max(moved, float(np.abs(v - rig.vertices).max()))
        assert moved > 2.0, name


def test_one_shot_motions_end_where_they_start(rig):
    for name, m in motions().items():
        if not m["loop"]:
            a, r = sample(name, m["duration"])
            assert np.allclose(a, 0, atol=1e-6) and abs(r["root.y"]) < 1e-6, name


def test_save_load_round_trip(rig, tmp_path):
    rig.save(tmp_path)
    back = Rig.load(tmp_path)
    assert back.texture.shape == rig.texture.shape
    assert np.allclose(back.vertices, rig.vertices, atol=0.01)
    assert (back.triangles == rig.triangles).all()
    assert np.allclose(back.bone_weight, rig.bone_weight, atol=1e-3)


def test_animated_drawings_interop(rig):
    cfg = to_animated_drawings(rig.joints, rig.texture.shape[1], rig.texture.shape[0])
    back = from_animated_drawings(cfg)
    assert set(back) == set(NAMES)
    assert all(abs(back[n][0] - rig.joints[n][0]) <= 0.5 for n in NAMES)


def test_given_joints_are_snapped_inside(rig):
    mask = (rig.texture[..., 3] > 128).astype(np.uint8) * 255
    j = dict(rig.joints)
    j["right_hand"] = (0.0, 0.0)  # far outside
    snapped = snap_inside(mask, j)
    x, y = snapped["right_hand"]
    assert mask[int(y), int(x)] > 0


@pytest.mark.parametrize("photo", ["garlic.png", "char6_image.png"])
def test_full_phone_photos_find_one_character(photo):
    crop, mask = extract_character(FIX / photo)
    frac = (mask > 0).mean()
    assert 0.1 < frac < 0.9
    n, _ = cv2.connectedComponents((mask > 0).astype(np.uint8))
    assert n == 2  # background + exactly one character
