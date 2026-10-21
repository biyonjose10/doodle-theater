"""HTTP API for the TV and the parent's phone.

TV:    POST /api/pair -> code + QR · GET /api/tv/{code}/events · GET /api/cast · POST /api/cast/samples
       GET /rigs/{id}/...
Phone: GET /p/{code} (page) · POST /api/p/{code}/photo · POST .../draft/{id}/joints · POST .../send
       POST /api/p/{code}/candidates -> pick one: POST .../upload/{id}/pick
       GET .../draft/{id}/crop.png|mask.png · POST .../draft/{id}/mask (the brush fix)
"""
from __future__ import annotations

import io
import logging
from importlib.resources import files

import segno
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import pipeline, samples, story, vision
from .story import agent, voice
from .config import STATIC, public_url
from .store import Store

log = logging.getLogger("doodle_theater")
app = FastAPI(title="Doodle Theater")
store = Store()

MAX_PHOTO = 15 * 1024 * 1024


def _session_or_404(code: str):
    s = store.session(code)
    if s is None:
        raise HTTPException(404, "That code has expired. Open 'Add a star' on the TV again.")
    return s


# TV side

@app.post("/api/pair")
def pair():
    s = store.new_session()
    url = f"{public_url()}/p/{s.code}"
    return {"code": s.code, "phone_url": url, "qr": f"/api/pair/{s.code}/qr.png"}


@app.get("/api/pair/{code}/qr.png")
def qr(code: str):
    s = _session_or_404(code)
    buf = io.BytesIO()
    segno.make(f"{public_url()}/p/{s.code}", error="m").save(buf, kind="png", scale=12, border=2,
                                                            dark="#2b2b3a", light="#ffffff")
    return Response(buf.getvalue(), media_type="image/png")


@app.get("/api/tv/{code}/events")
def events(code: str, after: int = 0):
    _session_or_404(code)
    return {"events": store.events_after(code, after)}


@app.get("/api/cast")
def cast():
    return {"cast": store.cast()}


@app.post("/api/cast/samples")
async def add_samples():
    """Three ready-made stars for anyone without a drawing. Safe to call twice: no duplicates."""
    added = await run_in_threadpool(samples.add_samples, store)
    return {"added": [c["id"] for c in added], "cast": store.cast()}


@app.delete("/api/cast")
def delete_everyone():
    store.remove(None)
    return {"ok": True}


@app.delete("/api/cast/{rig_id}")
def delete_one(rig_id: str):
    store.remove(rig_id)
    return {"ok": True}


@app.get("/rigs/{rig_id}/{name}")
def rig_file(rig_id: str, name: str):
    if name not in ("rig.json", "texture.png") or not rig_id.isalnum():
        raise HTTPException(404)
    for root in (store.rigs, store.drafts):
        f = root / rig_id / name
        if f.exists():
            return FileResponse(f, headers={"Cache-Control": "no-store"})
    raise HTTPException(404)


@app.get("/motions.json")
def motions_json():
    return Response(files("doodlerig").joinpath("motions.json").read_text(encoding="utf-8"),
                    media_type="application/json")


# Phone side

@app.get("/p/{code}", response_class=HTMLResponse)
def phone_page(code: str):
    page = (STATIC / "phone.html").read_text(encoding="utf-8")
    ok = store.session(code) is not None
    return page.replace("__CODE__", code.upper() if ok else "")


@app.post("/api/p/{code}/photo")
async def photo(code: str, file: UploadFile = File(...)):
    _session_or_404(code)
    data = await file.read()
    if len(data) > MAX_PHOTO:
        raise HTTPException(413, "That photo is too big.")
    try:
        return await run_in_threadpool(pipeline.make_draft, data, store.drafts)
    except ValueError as e:
        raise HTTPException(422, str(e))


def _draft_or_404(draft_id: str):
    folder = store.drafts / draft_id
    if not draft_id.isalnum() or not (folder / "crop.png").exists():
        raise HTTPException(404)
    return folder


@app.post("/api/p/{code}/candidates")
async def find_drawings(code: str, file: UploadFile = File(...)):
    """Every drawing on the photo, as boxes + thumbnails for the picker.

    With one drawing (or none) there is nothing to pick: the draft is made straight away and
    returned as `draft`. With several, the photo is kept under `upload` for .../pick.
    """
    _session_or_404(code)
    data = await file.read()
    if len(data) > MAX_PHOTO:
        raise HTTPException(413, "That photo is too big.")
    try:
        found = await run_in_threadpool(pipeline.candidates, data)
        if len(found) > 1:
            return {"upload": store.save_upload(data), "candidates": found, "draft": None}
        box = found[0]["box"] if found else None
        draft = await run_in_threadpool(pipeline.make_draft, data, store.drafts, box)
        return {"upload": None, "candidates": found, "draft": draft}
    except ValueError as e:
        raise HTTPException(422, str(e))


class Pick(BaseModel):
    box: list[int] = Field(min_length=4, max_length=4)


@app.post("/api/p/{code}/upload/{upload_id}/pick")
async def pick(code: str, upload_id: str, body: Pick):
    _session_or_404(code)
    data = store.upload(upload_id)
    if data is None:
        raise HTTPException(404, "That photo has gone. Take it again.")
    x0, y0, x1, y1 = body.box
    if min(body.box) < 0 or x1 <= x0 or y1 <= y0:
        raise HTTPException(422, "That isn't a box around a drawing.")
    try:
        return await run_in_threadpool(pipeline.make_draft, data, store.drafts, body.box)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/p/{code}/draft/{draft_id}/{name}")
def draft_file(code: str, draft_id: str, name: str):
    """The crop and its cut-out mask, for the brush. Phone-only, so behind the session code."""
    _session_or_404(code)
    if name not in ("crop.png", "mask.png"):
        raise HTTPException(404)
    return FileResponse(_draft_or_404(draft_id) / name, headers={"Cache-Control": "no-store"})


@app.post("/api/p/{code}/draft/{draft_id}/mask")
async def fix_mask(code: str, draft_id: str, file: UploadFile = File(...)):
    _session_or_404(code)
    _draft_or_404(draft_id)
    data = await file.read()
    if len(data) > MAX_PHOTO:
        raise HTTPException(413, "That picture is too big.")
    try:
        return await run_in_threadpool(pipeline.fix_mask, draft_id, data, store.drafts)
    except ValueError as e:
        raise HTTPException(422, str(e))


class Joints(BaseModel):
    joints: dict[str, list[float]]


@app.post("/api/p/{code}/draft/{draft_id}/joints")
async def fix(code: str, draft_id: str, body: Joints):
    _session_or_404(code)
    if not draft_id.isalnum() or not (store.drafts / draft_id).exists():
        raise HTTPException(404)
    try:
        return await run_in_threadpool(pipeline.fix_joints, draft_id, body.joints, store.drafts)
    except ValueError as e:
        raise HTTPException(422, str(e))


class Send(BaseModel):
    name: str = Field(min_length=1, max_length=24)


@app.post("/api/p/{code}/draft/{draft_id}/send")
def send(code: str, draft_id: str, body: Send):
    _session_or_404(code)
    if not draft_id.isalnum() or not (store.drafts / draft_id).exists():
        raise HTTPException(404)
    desc = pipeline.draft_summary(draft_id, store.drafts).get("description", "")
    entry = store.add_to_cast(draft_id, body.name.strip(), desc)
    store.push(code.upper(), {"type": "character", **entry})
    return entry


# Stories

class StoryRequest(BaseModel):
    theme: str
    cast: list[str] = Field(default_factory=list, max_length=4)
    # Calmer story, slower softer narration. None = decide by the server's clock (DT_BEDTIME_START/END).
    bedtime: bool | None = None


@app.post("/api/story")
async def new_story(body: StoryRequest):
    everyone = {c["id"]: c for c in store.cast()}
    chosen = [everyone[i] for i in body.cast if i in everyone] or list(everyone.values())[-4:]
    bedtime = story.is_bedtime() if body.bedtime is None else body.bedtime
    try:
        ep = await run_in_threadpool(story.make_episode, body.theme, chosen, store.root / "episodes",
                                     story_writer(), bedtime)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if vision.has_aws():  # Polly narration; without it the TV speaks with its own voice
        ep = await run_in_threadpool(voice.narrate, ep, store.root / "media")
        story.save_episode(ep, store.root / "episodes")
    return ep


@app.get("/api/story/{ep_id}")
def get_story(ep_id: str):
    if not ep_id.isalnum():
        raise HTTPException(404)
    try:
        return story.load_episode(ep_id, store.root / "episodes")
    except FileNotFoundError:
        raise HTTPException(404)


def story_writer():
    """The AI story agent when a model is configured (Bedrock or local), else None (templates)."""
    return agent.writer if agent.available() else None


@app.get("/media/{ep_id}/{name}")
def media(ep_id: str, name: str):
    f = store.root / "media" / ep_id / name
    if not ep_id.isalnum() or not name.endswith(".mp3") or "/" in name or "\\" in name or not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="audio/mpeg")


@app.exception_handler(HTTPException)
async def friendly(_, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


app.mount("/static", StaticFiles(directory=STATIC), name="static")
