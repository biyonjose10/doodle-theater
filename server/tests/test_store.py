import json
import threading
import time

import pytest

pytest.importorskip("httpx")  # FastAPI's TestClient needs it
from fastapi.testclient import TestClient  # noqa: E402

from doodle_theater import app as app_module  # noqa: E402
from doodle_theater import store as store_module  # noqa: E402
from doodle_theater.store import SESSION_TTL, Store  # noqa: E402


def _within(seconds: float, fn):
    """fn() in a thread; fail instead of hanging the suite if it never returns."""
    out = {}

    def run():
        try:
            out["value"] = fn()
        except BaseException as e:  # noqa: BLE001 - handed back to the test
            out["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    assert not t.is_alive(), f"still running after {seconds}s"
    if "error" in out:
        raise out["error"]
    return out["value"]


def test_pairing_codes_expire(tmp_path):
    store = Store(tmp_path)
    s = store.new_session()
    assert store.session(s.code) is s
    s.created -= SESSION_TTL + 1
    assert store.session(s.code) is None
    store.new_session()
    assert s.code not in store._sessions          # pruned


def test_new_session_gives_up_when_no_code_is_free(tmp_path, monkeypatch):
    store = Store(tmp_path)
    monkeypatch.setattr(store_module.secrets, "choice", lambda letters: letters[0])
    assert store.new_session().code == "BBBB"
    with pytest.raises(store_module.SessionsFull):
        _within(5, store.new_session)


def test_pair_says_try_again_when_no_code_is_free(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", Store(tmp_path))
    monkeypatch.setattr(store_module.secrets, "choice", lambda letters: letters[0])
    client = TestClient(app_module.app)
    assert client.post("/api/pair").status_code == 200
    r = _within(5, lambda: client.post("/api/pair"))
    assert r.status_code == 503 and r.json()["error"]


def test_reading_the_cast_while_it_is_saved(tmp_path):
    """cast() used to read cast.json while add_to_cast/remove were halfway through rewriting it."""
    store = Store(tmp_path)
    entries = [{"id": f"c{i}", "name": "x" * 200, "description": "y" * 2000, "added": 0} for i in range(300)]
    store._cast_file().write_text(json.dumps(entries), encoding="utf-8")
    stop, errors = time.monotonic() + 1.5, []

    def writer():
        while time.monotonic() < stop:
            store.remove("nosuchstar")                # rewrites the whole file, unchanged

    t = threading.Thread(target=writer)
    t.start()
    try:
        while time.monotonic() < stop:
            try:
                assert len(store.cast()) == 300
            except Exception as e:  # noqa: BLE001
                errors.append(e)
                break
    finally:
        t.join()
    assert not errors, errors[0]
