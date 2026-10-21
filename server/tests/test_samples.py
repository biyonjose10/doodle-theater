import json

import pytest

pytest.importorskip("httpx")  # FastAPI's TestClient needs it
from fastapi.testclient import TestClient  # noqa: E402

from doodle_theater import app as app_module  # noqa: E402
from doodle_theater.samples import catalogue  # noqa: E402
from doodle_theater.store import Store  # noqa: E402


def test_sample_stars_are_added_once(tmp_path, monkeypatch):
    store = Store(tmp_path)
    monkeypatch.setattr(app_module, "store", store)
    client = TestClient(app_module.app)

    first = client.post("/api/cast/samples").json()
    ids = [s["id"] for s in catalogue()]
    assert len(ids) == 3 and first["added"] == ids
    assert [c["id"] for c in first["cast"]] == ids
    assert all(c["name"] and c["description"] for c in first["cast"])

    for i in ids:  # a real puppet the TV can load, like a phone upload's
        rig = json.loads(client.get(f"/rigs/{i}/rig.json").content)
        assert rig["format"] == "doodlerig" and len(rig["skeleton"]) == 16
        assert client.get(f"/rigs/{i}/texture.png").status_code == 200

    second = client.post("/api/cast/samples").json()
    assert second["added"] == [] and len(second["cast"]) == 3  # idempotent: no duplicates


def test_samples_join_an_existing_cast_without_touching_it(tmp_path, monkeypatch):
    store = Store(tmp_path)
    (tmp_path / "cast.json").write_text(json.dumps([{"id": "abc123", "name": "Bolt", "description": "",
                                                     "added": 1.0}]), encoding="utf-8")
    monkeypatch.setattr(app_module, "store", store)
    cast = TestClient(app_module.app).post("/api/cast/samples").json()["cast"]
    assert cast[0]["id"] == "abc123" and len(cast) == 4
