"""Segmentation on synthetic phone photos where the true outline is known exactly.

Each photo is built from a known character mask, so every test can measure the cut-out against
ground truth instead of eyeballing it. The generators add paper grain, a wooden table and clumpy
crayon so the cases are not trivially clean. Cases marked xfail are known gaps still to fix.
"""
from pathlib import Path

import cv2
import numpy as np
import pytest

from doodlerig import build_rig, rig_from_mask
from PIL import Image

from doodlerig.segment import extract_character, find_characters, find_paper, load_image, soft_alpha, straighten

FIX = Path(__file__).parent / "fixtures"
PAPER = np.array([246, 244, 238], np.float32)
TABLE = np.array([150, 108, 72], np.float32)
DARK = (35, 35, 40)


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a > 0, b > 0
    return float((a & b).sum() / max((a | b).sum(), 1))


def _figure(shape: tuple[int, int], cx: float, cy: float, s: float) -> np.ndarray:
    """A gingerbread-ish character (head, body, arms out, legs apart), about 5*s tall."""
    m = np.zeros(shape, np.uint8)
    p = lambda x, y: (round(cx + x * s), round(cy + y * s))
    cv2.circle(m, p(0, -1.9), round(0.62 * s), 255, -1)                              # head
    cv2.ellipse(m, p(0, 0), (round(0.85 * s), round(1.3 * s)), 0, 0, 360, 255, -1)   # body
    for sx in (-1, 1):
        cv2.line(m, p(0.5 * sx, -0.6), p(1.9 * sx, -1.3), 255, round(0.38 * s))      # arms
        cv2.line(m, p(0.4 * sx, 0.9), p(0.9 * sx, 2.5), 255, round(0.45 * s))        # legs
    return m


def _paint(img: np.ndarray, where: np.ndarray, colour, rng, cover=0.85) -> None:
    """Crayon: the colour laid down in clumps, with blotches of paper showing through."""
    grain = cv2.GaussianBlur(rng.random(where.shape).astype(np.float32), (0, 0), 1.5)
    hit = (grain > np.quantile(grain, 1 - cover)).astype(np.float32)
    hit = cv2.GaussianBlur(hit, (3, 3), 0)[..., None] * (where[..., None] > 0)
    img[:] = img * (1 - hit) + np.asarray(colour, np.float32) * hit


def _outline(mask: np.ndarray, width: int) -> np.ndarray:
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = np.zeros_like(mask)
    cv2.drawContours(out, cs, -1, 255, width)
    return out


def _table(rng, h, w):
    img = np.empty((h, w, 3), np.float32)
    img[:] = TABLE
    img += cv2.GaussianBlur(rng.normal(0, 18, (h, w)).astype(np.float32), (0, 0), 3)[..., None]
    return img


def _page_on_table(rng, size=(1000, 800), page=(80, 60, 920, 740)):
    """A sheet of paper (y0, x0, y1, x1) lying square-on on a wooden table, as float RGB."""
    h, w = size
    img = _table(rng, h, w)
    y0, x0, y1, x1 = page
    img[y0:y1, x0:x1] = PAPER
    img += rng.normal(0, 3, (h, w, 1)).astype(np.float32)          # paper grain / sensor noise
    return img


def _finish(img: np.ndarray) -> np.ndarray:
    return np.clip(img, 0, 255).astype(np.uint8)


def _truth(fig: np.ndarray, line: np.ndarray) -> np.ndarray:
    return ((fig > 0) | (line > 0)).astype(np.uint8) * 255


def _in_photo(photo: np.ndarray, crop: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Paste a crop's mask back where the (unwarped) crop sits in the photo."""
    _, _, (x, y), _ = cv2.minMaxLoc(cv2.matchTemplate(photo, crop, cv2.TM_SQDIFF))
    full = np.zeros(photo.shape[:2], np.uint8)
    full[y:y + mask.shape[0], x:x + mask.shape[1]] = mask
    return full


# Case builders: each returns (photo uint8 RGB, true character mask in photo coordinates). -----

def crayon_case(colour):
    """Coloured in lightly and outlined in the same light crayon: no dark line anywhere."""
    rng = np.random.default_rng(1)
    img = _page_on_table(rng)
    fig = _figure(img.shape[:2], 400, 520, 70)
    line = _outline(fig, 5)
    _paint(img, fig, colour, rng, cover=0.6)
    _paint(img, line, colour, rng, cover=0.85)
    return _finish(img), _truth(fig, line)


def shadow_case():
    """Dark outline; a soft-edged shadow (a person leaning over) darkens the left half to 35%."""
    rng = np.random.default_rng(3)
    img = _page_on_table(rng)
    fig = _figure(img.shape[:2], 400, 520, 70)
    line = _outline(fig, 5)
    _paint(img, line, DARK, rng, cover=0.97)
    w = img.shape[1]
    t = np.clip((440 - np.arange(w)) / 150, 0, 1)
    t = t * t * (3 - 2 * t)
    light = (1.0 - 0.65 * t)[None, :, None]
    tint = np.array([0.94, 0.97, 1.0], np.float32)[None, None, :] ** t[None, :, None]  # shade is bluish
    return _finish(img * light * tint), _truth(fig, line)


def gap_case(gap):
    """Outline only, with a piece `gap` x perimeter long rubbed out on the side of the body."""
    rng = np.random.default_rng(7)
    img = _page_on_table(rng)
    fig = _figure(img.shape[:2], 400, 520, 70)
    line = _outline(fig, 5)
    truth = _truth(fig, line)
    cs, _ = cv2.findContours(fig, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pts = cs[0][:, 0, :]
    side = pts[(np.abs(pts[:, 1] - 560) < 3) & (pts[:, 0] > 400)][0]
    r = max(2, round(gap * cv2.arcLength(cs[0], True) / 2))
    cv2.circle(line, (int(side[0]), int(side[1])), r, 0, -1)
    _paint(img, line, DARK, rng, cover=0.97)
    return _finish(img), truth


def page_with_figure(rng, size=(990, 700), at=(350, 470), s=70):
    h, w = size
    img = np.empty((h, w, 3), np.float32)
    img[:] = PAPER
    img += rng.normal(0, 3, (h, w, 1)).astype(np.float32)
    fig = _figure((h, w), at[0], at[1], s)
    line = _outline(fig, 5)
    _paint(img, fig, (120, 200, 120), rng, cover=0.8)
    _paint(img, line, DARK, rng, cover=0.97)
    return _finish(img), _truth(fig, line)


def camera_photo(page_rgb: np.ndarray, tilt=38.0, turn=12.0, size=(900, 1200)) -> np.ndarray:
    """Photograph a flat page with a pinhole camera tilted away from straight-down."""
    ph, pw = page_rgb.shape[:2]
    h, w = size
    table = _table(np.random.default_rng(4), h, w)
    a, b = np.radians(tilt), np.radians(turn)
    rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    rz = np.array([[np.cos(b), -np.sin(b), 0], [np.sin(b), np.cos(b), 0], [0, 0, 1]])
    f, dist = 900.0, 1150.0
    corners = np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float64)
    world = np.c_[corners - [pw / 2, ph / 2], np.zeros(4)] @ (rz @ rx).T + [0, 0, dist]
    proj = world[:, :2] / world[:, 2:] * f + [w / 2, h / 2]
    H = cv2.getPerspectiveTransform(corners.astype(np.float32), proj.astype(np.float32))
    warped = cv2.warpPerspective(page_rgb, H, (w, h), flags=cv2.INTER_LINEAR)
    cover = cv2.warpPerspective(np.full((ph, pw), 255, np.uint8), H, (w, h))
    return _finish(np.where(cover[..., None] > 127, warped.astype(np.float32), table))


def perspective_case():
    page, truth = page_with_figure(np.random.default_rng(5))
    return camera_photo(page), truth                     # truth is in *page* coordinates


def two_drawings():
    """A big and a small character side by side on one sheet. Returns (photo, [truth big, small])."""
    rng = np.random.default_rng(8)
    img = _page_on_table(rng, size=(800, 1000), page=(60, 50, 740, 950))
    truths = []
    for fig, colour in ((_figure(img.shape[:2], 300, 400, 62), (200, 120, 200)),
                        (_figure(img.shape[:2], 720, 430, 45), (110, 170, 230))):
        line = _outline(fig, 5)
        _paint(img, fig, colour, rng, cover=0.8)
        _paint(img, line, DARK, rng, cover=0.97)
        truths.append(_truth(fig, line))
    return _finish(img), truths


# 1. Colour-aware ink ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="TODO: the colour-aware ink finds the crayon drawing, but the cut-out still uses min-channel ink", strict=True)
@pytest.mark.parametrize("colour", [(250, 238, 150), (178, 210, 245)], ids=["light_yellow", "light_blue"])
def test_crayon_without_a_dark_outline_is_cut_out(colour):
    photo, truth = crayon_case(colour)
    crop, mask = extract_character(photo)
    assert _iou(_in_photo(photo, crop, mask), truth) >= 0.9


@pytest.mark.xfail(reason="TODO: a blank sheet still yields a paper-sized region", strict=True)
def test_paper_grain_and_table_are_not_ink():
    """A blank sheet on a table: nothing should come out as a character."""
    _, mask = extract_character(_finish(_page_on_table(np.random.default_rng(2))))
    assert (mask > 0).mean() < 0.02


# 2. Shadows ------------------------------------------------------------------------------------

def test_a_shadow_across_half_the_page_is_not_cut_out():
    photo, truth = shadow_case()
    crop, mask = extract_character(photo)
    full = _in_photo(photo, crop, mask)
    assert _iou(full, truth) >= 0.9
    stray = (full > 0) & (cv2.dilate(truth, np.ones((9, 9), np.uint8)) == 0)
    assert stray.sum() < 0.01 * (truth > 0).sum()                  # no shadow blob
    assert cv2.connectedComponents((mask > 0).astype(np.uint8))[0] == 2


# 3. Perspective --------------------------------------------------------------------------------

def _aspect(mask: np.ndarray) -> float:
    ys, xs = np.nonzero(mask)
    return (ys.max() - ys.min() + 1) / (xs.max() - xs.min() + 1)


@pytest.mark.xfail(reason="TODO: straighten() does not yet detect this synthetic quad", strict=True)
def test_a_page_photographed_at_an_angle_is_straightened():
    photo, truth = perspective_case()
    _, mask = extract_character(photo)
    assert abs(_aspect(mask) / _aspect(truth) - 1) < 0.10


def test_straighten_leaves_square_on_photos_alone():
    photo = _finish(_page_on_table(np.random.default_rng(6)))
    assert straighten(photo) is photo                     # a square-on sheet is not resampled
    tex = cv2.imread(str(FIX / "char1_texture.png"))[..., ::-1]
    assert straighten(tex) is tex                         # nor is a tight crop with no paper edge


# 4. Leaks through a gap in the outline ---------------------------------------------------------

@pytest.mark.parametrize("gap", [0.01, pytest.param(0.02, marks=pytest.mark.xfail(
    reason="TODO: at 2% no closing size seals the gap with the 1.5x growth check", strict=True)), 0.03])
def test_a_gap_in_the_outline_does_not_hollow_out_the_character(gap):
    photo, truth = gap_case(gap)
    crop, mask = extract_character(photo)
    assert _iou(_in_photo(photo, crop, mask), truth) >= 0.9


# 5. Soft edges ---------------------------------------------------------------------------------

def test_texture_alpha_is_anti_aliased_but_the_mesh_mask_stays_binary():
    mask = np.zeros((300, 260), np.uint8)
    cv2.ellipse(mask, (130, 150), (90, 120), 23, 0, 360, 255, -1)
    alpha = soft_alpha(mask)
    assert alpha.dtype == np.uint8 and alpha.shape == mask.shape
    inner = cv2.erode(mask, np.ones((5, 5), np.uint8)) > 0
    outer = cv2.dilate(mask, np.ones((5, 5), np.uint8)) == 0
    assert (alpha[inner] == 255).all() and (alpha[outer] == 0).all()
    partial = (alpha > 0) & (alpha < 255)
    boundary = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    assert partial.sum() > 0.25 * boundary.sum()                  # a real feather, not a hard step
    assert _iou(alpha > 127, mask) > 0.97                        # but no fatter or thinner
    rig = rig_from_mask(np.full(mask.shape + (3,), 200, np.uint8), mask)
    a = rig.texture[..., 3]
    assert ((a > 0) & (a < 255)).any()


# 6. Several characters on one sheet ------------------------------------------------------------

def test_find_characters_returns_each_drawing_biggest_first():
    photo, truths = two_drawings()
    boxes = find_characters(photo)
    assert len(boxes) == 2
    for (x0, y0, x1, y1), truth in zip(boxes, truths):
        ys, xs = np.nonzero(truth)
        assert x0 <= xs.min() and y0 <= ys.min() and x1 > xs.max() and y1 > ys.max()
        assert (x1 - x0) < 1.4 * (np.ptp(xs) + 1)                 # one drawing per box


@pytest.mark.xfail(reason="TODO: the small figure's IoU is 0.875 (target 0.9)", strict=True)
def test_extract_character_uses_the_given_box():
    photo, truths = two_drawings()
    for box, truth in zip(find_characters(photo), truths):
        x0, y0, x1, y1 = box
        crop, mask = extract_character(photo, box=box)
        assert crop.shape[:2] == (y1 - y0, x1 - x0)
        assert _iou(mask, truth[y0:y1, x0:x1]) >= 0.9


def test_build_rig_accepts_a_box():
    photo, truths = two_drawings()
    rig = build_rig(photo, box=find_characters(photo)[1])
    tall = np.ptp(np.nonzero(truths[1])[0])
    assert abs(rig.texture.shape[0] - tall) < 0.2 * tall          # the small one, not the big one


@pytest.mark.parametrize("photo", ["garlic.png", "char6_image.png"])
def test_find_characters_sees_one_drawing_on_the_fixture_photos(photo):
    assert len(find_characters(FIX / photo)) == 1


def _modes() -> dict[str, Image.Image]:
    """A white 40x40 picture with a dark square, in every image mode a phone or scanner might send."""
    grey = np.full((40, 40), 255, np.uint8)
    grey[10:20, 10:20] = 0
    rgb = np.dstack([grey] * 3)
    rgb[25:35, 25:35] = (220, 30, 30)                       # and a red square, for colour modes
    opaque = np.where(grey == 0, 255, 0).astype(np.uint8)   # only the dark square is opaque
    p = Image.fromarray(grey, "L").convert("P")
    p.info["transparency"] = int(np.asarray(p)[0, 0])      # the white index is see-through
    pa = Image.fromarray(np.zeros_like(grey), "L").convert("P").convert("PA")
    pa.putalpha(Image.fromarray(opaque, "L"))
    return {
        "L": Image.fromarray(grey, "L"),
        "1": Image.fromarray(grey, "L").convert("1"),
        "I;16": Image.fromarray(grey.astype(np.uint16) * 257),
        "I": Image.fromarray(grey.astype(np.int32) * 257),
        "F": Image.fromarray(grey.astype(np.float32)),
        "CMYK": Image.fromarray(rgb, "RGB").convert("CMYK"),
        "LA": Image.fromarray(np.dstack([np.zeros_like(grey), opaque]), "LA"),
        "PA": pa,
        "P": p,
        "RGBA": Image.fromarray(np.dstack([np.zeros_like(rgb), opaque]), "RGBA"),
    }


@pytest.mark.parametrize("mode", list(_modes()))
def test_load_image_reads_every_mode_as_rgb_on_white(mode):
    im = _modes()[mode]
    assert im.mode == mode
    img = load_image(im)
    assert img.shape == (40, 40, 3) and img.dtype == np.uint8
    assert img[15, 15].max() < 40, img[15, 15]              # the dark square stays dark
    assert img[2, 2].min() > 215, img[2, 2]                 # the paper (or transparency) is white
    if mode == "CMYK":                                      # K is ink, not alpha: red stays red
        r, g, b = img[30, 30].astype(int)
        assert r > 180 and g < 90 and b < 90, img[30, 30]


@pytest.mark.parametrize("shape", [(3000, 20), (20, 3000)])
def test_a_very_narrow_sheet_does_not_crash(shape):
    """A thin strip of paper on a table: trimming 3% of its LONG side used to turn the box inside out."""
    img = np.full((*shape, 3), TABLE, np.uint8)
    h, w = shape
    img[h // 10:h - h // 10, w // 10:w - w // 10] = PAPER
    box = find_paper(img)
    assert box is None or (box[0] < box[2] and box[1] < box[3])
    find_characters(img)
