"""The phone's "pick your character" step and the cut-out brush, through the HTTP API."""
import base64
import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("httpx")  # FastAPI's TestClient needs it
from fastapi.testclient import TestClient  # noqa: E402

from doodle_theater import app as app_module  # noqa: E402
from doodle_theater import pipeline, vision  # noqa: E402
from doodle_theater.samples import SAMPLES  # noqa: E402
from doodle_theater.store import Store  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SHEET = REPO / "submission" / "images" / "drawings_photo.webp"  # four drawings on a table


@pytest.fixture
def phone(tmp_path, monkeypatch):
    """(client, code, store) on a throwaway data folder, with the vision model off: no AWS calls."""
    monkeypatch.setattr(vision, "VISION_MODEL", "off")
    store = Store(tmp_path)
    monkeypatch.setattr(app_module, "store", store)
    client = TestClient(app_module.app)
    return client, client.post("/api/pair").json()["code"], store


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _one_drawing() -> bytes:
    """A sample star on a sheet of white paper: a photo with exactly one drawing."""
    art = Image.open(SAMPLES / "crown.png").convert("RGBA")
    art = art.resize((art.width // 2, art.height // 2), Image.Resampling.LANCZOS)  # half size: quicker
    sheet = Image.new("RGBA", (art.width + 80, art.height + 80), (255, 255, 255, 255))
    sheet.alpha_composite(art, (40, 40))
    return _png(sheet.convert("RGB"))


def _photo(client, code, data: bytes, name="p.png"):
    return client.post(f"/api/p/{code}/candidates", files={"file": (name, data)})


def _mask(client, code, draft_id) -> np.ndarray:
    r = client.get(f"/api/p/{code}/draft/{draft_id}/mask.png")
    assert r.status_code == 200
    return np.asarray(Image.open(io.BytesIO(r.content)).convert("L")).copy()


def _send_mask(client, code, draft_id, mask: np.ndarray):
    return client.post(f"/api/p/{code}/draft/{draft_id}/mask",
                       files={"file": ("mask.png", _png(Image.fromarray(mask)))})


# --- Pick your character ------------------------------------------------------------------------

def test_a_sheet_of_drawings_offers_a_candidate_for_each(phone):
    client, code, store = phone
    body = _photo(client, code, SHEET.read_bytes(), "sheet.webp").json()
    assert body["draft"] is None and body["upload"]
    cands = body["candidates"]
    assert len(cands) >= 3
    for c in cands:
        x0, y0, x1, y1 = c["box"]
        assert 0 <= x0 < x1 and 0 <= y0 < y1
        assert c["thumb"].startswith("data:image/jpeg;base64,")
        thumb = Image.open(io.BytesIO(base64.b64decode(c["thumb"].split(",", 1)[1])))
        assert max(thumb.size) <= pipeline.THUMB
    # Separate drawings: no two boxes are mostly the same region.
    boxes = [c["box"] for c in cands]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            ix = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            assert ix < 0.5 * min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    assert (store.uploads / body["upload"]).is_file()


def test_picking_a_candidate_rigs_that_drawing(phone):
    client, code, store = phone
    body = _photo(client, code, SHEET.read_bytes(), "sheet.webp").json()
    drafts = []
    for c in body["candidates"][:2]:
        r = client.post(f"/api/p/{code}/upload/{body['upload']}/pick", json={"box": c["box"]})
        assert r.status_code == 200, r.text
        d = r.json()
        x0, y0, x1, y1 = c["box"]
        crop = Image.open(store.drafts / d["id"] / "crop.png")
        assert crop.size == (x1 - x0, y1 - y0)  # cut from exactly the chosen box
        assert d["joints_from"] == "heuristic" and len(d["joints"]) == 16
        drafts.append(d["id"])
    assert drafts[0] != drafts[1]
    # The picked draft goes to the TV like any other.
    sent = client.post(f"/api/p/{code}/draft/{drafts[1]}/send", json={"name": "Bloop"}).json()
    assert sent["id"] == drafts[1] and [c["id"] for c in store.cast()] == [drafts[1]]


def test_one_drawing_skips_the_picker(phone):
    client, code, store = phone
    body = _photo(client, code, _one_drawing()).json()
    assert len(body["candidates"]) == 1 and body["upload"] is None
    draft = body["draft"]
    assert draft["id"] and (store.drafts / draft["id"] / "rig.json").exists()
    assert list(store.uploads.iterdir()) == []  # nothing kept when there was nothing to pick


def test_pick_rejects_bad_input(phone):
    client, code, _ = phone
    upload = _photo(client, code, SHEET.read_bytes(), "sheet.webp").json()["upload"]
    url = f"/api/p/{code}/upload/{upload}/pick"
    assert client.post(f"/api/p/{code}/upload/nosuchupload/pick", json={"box": [0, 0, 9, 9]}).status_code == 404
    assert client.post(url, json={"box": [10, 10, 5, 50]}).status_code == 422       # inside out
    assert client.post(url, json={"box": [5000, 5000, 6000, 6000]}).status_code == 422  # off the photo
    assert client.post(url, json={"box": [1, 2, 3]}).status_code == 422
    assert client.post("/api/p/ZZZZ/upload/x/pick", json={"box": [0, 0, 9, 9]}).status_code == 404
    assert _photo(client, code, b"not a picture").status_code == 422


def test_delete_everyone_also_drops_waiting_photos(phone):
    client, code, store = phone
    _photo(client, code, SHEET.read_bytes(), "sheet.webp")
    assert list(store.uploads.iterdir())
    client.delete("/api/cast")
    assert list(store.uploads.iterdir()) == []


def test_deleting_one_star_stops_serving_its_drawing(phone):
    client, code, store = phone
    draft_id = _photo(client, code, _one_drawing()).json()["draft"]["id"]
    assert client.post(f"/api/p/{code}/draft/{draft_id}/send", json={"name": "Gone Soon"}).status_code == 200
    assert client.get(f"/rigs/{draft_id}/texture.png").status_code == 200
    client.delete(f"/api/cast/{draft_id}")
    assert [c for c in client.get("/api/cast").json()["cast"] if c["id"] == draft_id] == []
    for name in ("rig.json", "texture.png"):
        assert client.get(f"/rigs/{draft_id}/{name}").status_code == 404
    assert not (store.drafts / draft_id).exists()


# --- Fix the cut-out ----------------------------------------------------------------------------

@pytest.fixture
def draft(phone):
    client, code, store = phone
    return (*phone, _photo(client, code, _one_drawing()).json()["draft"])


def test_brush_files_are_behind_the_session_code(draft):
    client, code, _, d = draft
    crop = client.get(f"/api/p/{code}/draft/{d['id']}/crop.png")
    assert crop.status_code == 200 and crop.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(crop.content)).size == _mask(client, code, d["id"]).shape[::-1]
    assert client.get(f"/api/p/ZZZZ/draft/{d['id']}/crop.png").status_code == 404
    assert client.get(f"/api/p/{code}/draft/{d['id']}/rig.json").status_code == 404
    assert client.get(f"/api/p/{code}/draft/nosuchdraft/mask.png").status_code == 404


def test_erasing_shrinks_the_puppet_and_keeps_the_parents_joints(draft):
    client, code, store, d = draft
    # The parent placed the joints first; a brush fix elsewhere must not throw that away.
    d = client.post(f"/api/p/{code}/draft/{d['id']}/joints", json={"joints": d["joints"]}).json()
    assert d["joints_from"] == "parent"
    before = pipeline.draft_summary(d["id"], store.drafts)
    joints = {j["name"]: [j["x"], j["y"]] for j in before["skeleton"]}

    mask = _mask(client, code, d["id"])
    ys, xs = np.nonzero(mask)
    cut = ys.max() - int(0.06 * (ys.max() - ys.min()))  # rub out the bottom of the feet
    mask[cut:] = 0
    r = _send_mask(client, code, d["id"], mask)
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["joints_from"] == "parent"
    assert after["height"] < before["height"]
    saved = _mask(client, code, d["id"])
    assert not saved[cut:].any() and (saved > 0).sum() < (mask > 0).sum() + 1
    # Joints in crop coordinates: the hands and head did not move.
    off0, off1 = before["meta"]["crop_offset"], pipeline.draft_summary(d["id"], store.drafts)["meta"]["crop_offset"]
    for name in ("neck", "left_hand", "right_hand"):
        b, a = joints[name], after["joints"][name]
        assert abs(b[0] + off0[0] - a[0] - off1[0]) <= 1.5 and abs(b[1] + off0[1] - a[1] - off1[1]) <= 1.5


def test_adding_paint_grows_the_puppet(draft):
    client, code, store, d = draft
    mask = _mask(client, code, d["id"])
    ys, xs = np.nonzero(mask)
    top, cx = ys.min(), int(np.median(xs[ys == ys.min()]))
    mask[max(0, top - 30):top + 5, cx - 15:cx + 15] = 255  # a hat stuck to the head
    after = _send_mask(client, code, d["id"], mask).json()
    assert after["height"] > d["height"]
    assert after["joints_from"] == "heuristic"  # heuristic joints are re-guessed for the new shape


def test_detached_blobs_and_pinholes_are_tidied(draft):
    client, code, _, d = draft
    mask = _mask(client, code, d["id"])
    ys, xs = np.nonzero(mask)
    cy, cx = int(np.median(ys)), int(np.median(xs))
    mask[cy:cy + 2, cx:cx + 2] = 0             # a speck of hole from the brush edge
    mask[:12, :12] = 255                       # a dab of paint well away from the drawing
    after = _send_mask(client, code, d["id"], mask).json()
    saved = _mask(client, code, d["id"])
    assert not saved[:12, :12].any()
    assert saved[cy:cy + 2, cx:cx + 2].all()
    assert after["width"] == d["width"] and after["height"] == d["height"]


def test_bad_masks_are_refused_with_a_message(draft):
    client, code, _, d = draft
    mask = _mask(client, code, d["id"])
    wrong = _send_mask(client, code, d["id"], mask[:-10])
    assert wrong.status_code == 422 and "expected" in wrong.json()["error"]
    empty = _send_mask(client, code, d["id"], np.zeros_like(mask))
    assert empty.status_code == 422 and "Undo" in empty.json()["error"]
    junk = client.post(f"/api/p/{code}/draft/{d['id']}/mask", files={"file": ("m.png", b"nope")})
    assert junk.status_code == 422
    assert _send_mask(client, code, "nosuchdraft", mask).status_code == 404


def test_a_transparent_mask_png_works_too(draft):
    """White-on-transparent, as a canvas exports it without a black backdrop."""
    client, code, _, d = draft
    mask = _mask(client, code, d["id"])
    rgba = np.zeros((*mask.shape, 4), np.uint8)
    rgba[mask > 0] = 255
    r = client.post(f"/api/p/{code}/draft/{d['id']}/mask",
                    files={"file": ("m.png", _png(Image.fromarray(rgba, "RGBA")))})
    assert r.status_code == 200 and r.json()["width"] == d["width"]


# --- Bad input gets a message, never a 500 ------------------------------------------------------

def test_grey_and_one_bit_photos_are_rigged(phone):
    client, code, _ = phone
    grey = Image.open(io.BytesIO(_one_drawing())).convert("L")
    for im in (grey, grey.point(lambda v: 255 if v > 200 else 0).convert("1")):
        r = _photo(client, code, _png(im))
        assert r.status_code == 200, r.text
        assert r.json()["draft"]["id"]


def test_a_tiny_file_that_decodes_huge_is_refused_unread(phone, monkeypatch):
    client, code, _ = phone
    bomb = _png(Image.new("L", (7000, 7000)))           # ~50 KB on the wire, 49 megapixels decoded
    assert len(bomb) < 1024 * 1024
    loads = []
    monkeypatch.setattr(Image.Image, "load", lambda self, *a: loads.append(self.size))
    for url in (f"/api/p/{code}/candidates", f"/api/p/{code}/photo"):
        r = client.post(url, files={"file": ("bomb.png", bomb)})
        assert r.status_code == 422 and "too big" in r.json()["error"]
    assert (7000, 7000) not in loads                     # never decoded


def test_a_wrong_size_mask_is_refused_before_it_is_decoded(draft, monkeypatch):
    client, code, _, d = draft
    small = _mask(client, code, d["id"])[:-10]
    png, real_load = _png(Image.fromarray(small)), Image.Image.load

    def load(self, *a):
        assert self.size != small.shape[::-1], "decoded a mask it was about to refuse"
        return real_load(self, *a)

    monkeypatch.setattr(Image.Image, "load", load)
    wrong = client.post(f"/api/p/{code}/draft/{d['id']}/mask", files={"file": ("mask.png", png)})
    assert wrong.status_code == 422 and "expected" in wrong.json()["error"]


def test_uploads_are_read_only_up_to_the_limit(phone, monkeypatch):
    client, code, _ = phone
    from starlette.datastructures import UploadFile
    real_read, sizes = UploadFile.read, []

    async def read(self, size=-1):
        sizes.append(size)
        return await real_read(self, size)

    monkeypatch.setattr(UploadFile, "read", read)
    monkeypatch.setattr(app_module, "MAX_PHOTO", 1000)
    r = _photo(client, code, b"x" * 5000)
    assert r.status_code == 413 and "too big" in r.json()["error"]
    assert sizes == [1001]


@pytest.mark.parametrize("shape", [(3000, 20), (20, 3000)])
def test_a_very_narrow_photo_gets_a_message(phone, shape):
    client, code, _ = phone
    img = np.full((*shape, 3), (150, 108, 72), np.uint8)
    h, w = shape
    img[h // 10:h - h // 10, w // 10:w - w // 10] = 246
    r = _photo(client, code, _png(Image.fromarray(img)))
    assert r.status_code in (200, 422), r.text
    if r.status_code == 422:
        assert r.json()["error"]


def test_a_segmentation_crash_is_a_message_not_a_500(phone, monkeypatch):
    client, code, _ = phone

    def boom(*a, **k):
        raise IndexError("deep inside OpenCV")

    monkeypatch.setattr(pipeline, "find_characters", boom)
    monkeypatch.setattr(pipeline, "extract_character", boom)
    for url in (f"/api/p/{code}/candidates", f"/api/p/{code}/photo"):
        r = client.post(url, files={"file": ("p.png", _one_drawing())})
        assert r.status_code == 422 and "drawing" in r.json()["error"]


@pytest.mark.parametrize("root", [
    None,                    # no root (nor hip)
    "[X]",                   # not a pair
    "[X, Y, 30]",
    "[Infinity, Y]",
    "[NaN, Y]",
    "[X, 1e400]",            # overflows to inf
    '["left", Y]',
])
def test_malformed_joints_get_a_message(draft, root):
    """The draft's own joints, which rebuild fine, with only the root spoilt."""
    client, code, _, d = draft
    x, y = d["joints"]["root"]
    rest = [f'"{k}": {v}' for k, v in d["joints"].items() if k not in ("root", "hip")]
    if root is not None:
        rest.append('"root": ' + root.replace("X", str(x)).replace("Y", str(y)))
    url = f"/api/p/{code}/draft/{d['id']}/joints"
    for body in ('{"joints": {' + ", ".join(rest) + "}}", '{"joints": [1, 2]}'):
        r = client.post(url, content=body, headers={"Content-Type": "application/json"})
        assert r.status_code == 422 and r.json()["error"], r.text
    assert client.post(url, json={"joints": d["joints"]}).status_code == 200
