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
