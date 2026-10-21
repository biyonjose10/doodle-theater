"""Pairing sessions (in memory) and the cast of characters (on disk)."""
from __future__ import annotations

import json
import secrets
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import DATA

# Four letters a child can read off the TV; no vowels, so no accidental words.
_LETTERS = "BCDFGHJKLMNPQRSTVWXZ"
# A photo with several drawings is kept this long, so the child can go back and pick another one.
UPLOAD_TTL = 3600


@dataclass
class Session:
    code: str
    created: float = field(default_factory=time.time)
    events: list[dict] = field(default_factory=list)


class Store:
    def __init__(self, root: Path = DATA):
        self.root = root
        self.rigs = root / "rigs"
        self.drafts = root / "drafts"
        self.uploads = root / "uploads"
        for d in (self.rigs, self.drafts, self.uploads):
            d.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}

    # Pairing
    def new_session(self) -> Session:
        with self._lock:
            while True:
                code = "".join(secrets.choice(_LETTERS) for _ in range(4))
                if code not in self._sessions:
                    s = self._sessions[code] = Session(code)
                    return s

    def session(self, code: str) -> Session | None:
        return self._sessions.get(code.upper())

    def push(self, code: str, event: dict) -> None:
        with self._lock:
            s = self._sessions[code]
            s.events.append({"n": len(s.events) + 1, **event})

    def events_after(self, code: str, after: int) -> list[dict]:
        s = self.session(code)
        return [] if s is None else [e for e in s.events if e["n"] > after]

    # Photos waiting for the child to pick a drawing
    def save_upload(self, photo: bytes) -> str:
        """Keep a photo for the picker; photos older than UPLOAD_TTL are dropped on the way."""
        with self._lock:
            cutoff = time.time() - UPLOAD_TTL
            for f in self.uploads.iterdir():
                if f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
            upload_id = uuid.uuid4().hex[:12]
            (self.uploads / upload_id).write_bytes(photo)
            return upload_id

    def upload(self, upload_id: str) -> bytes | None:
        f = self.uploads / upload_id
        return f.read_bytes() if upload_id.isalnum() and f.is_file() else None

    # Cast
    def _cast_file(self) -> Path:
        return self.root / "cast.json"

    def cast(self) -> list[dict]:
        f = self._cast_file()
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

    def add_to_cast(self, draft_id: str, name: str, description: str) -> dict:
        with self._lock:
            src, dst = self.drafts / draft_id, self.rigs / draft_id
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("crop.png", "mask.png"))
            entry = {"id": draft_id, "name": name, "description": description, "added": time.time()}
            cast = [c for c in self.cast() if c["id"] != draft_id] + [entry]
            self._cast_file().write_text(json.dumps(cast, indent=1), encoding="utf-8")
            return entry

    def remove(self, rig_id: str | None = None) -> None:
        """Delete one character, or everyone (the parent's "delete all drawings" button)."""
        with self._lock:
            keep = [] if rig_id is None else [c for c in self.cast() if c["id"] != rig_id]
            for c in self.cast():
                if rig_id is None or c["id"] == rig_id:
                    shutil.rmtree(self.rigs / c["id"], ignore_errors=True)
            if rig_id is None:
                for d in (self.drafts, self.uploads):
                    shutil.rmtree(d, ignore_errors=True)
                    d.mkdir(parents=True, exist_ok=True)
            elif rig_id.isalnum():
                # The draft holds the same drawing (and /rigs/ falls back to it), so it goes too.
                shutil.rmtree(self.drafts / rig_id, ignore_errors=True)
            self._cast_file().write_text(json.dumps(keep, indent=1), encoding="utf-8")
