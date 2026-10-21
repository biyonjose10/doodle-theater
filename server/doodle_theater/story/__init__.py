"""Story writing: an AI agent when AWS is available, hand-written templates otherwise."""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from ..config import BEDTIME_END, BEDTIME_START
from . import offline
from .schema import BACKDROPS, validate

log = logging.getLogger(__name__)

# Character voices for on-TV speech when there is no Polly audio: pitch shifts per speaker.
TV_PITCHES = [1.35, 1.6, 1.15, 1.8, 1.25]


def is_bedtime(hour: int | None = None, start: int = BEDTIME_START, end: int = BEDTIME_END) -> bool:
    """Is `hour` (default: now, server local time) inside the bedtime window? The window may wrap midnight."""
    if hour is None:
        hour = datetime.now().hour
    if start == end:
        return False
    return start <= hour < end if start < end else (hour >= start or hour < end)


def make_episode(theme: str, cast: list[dict], episodes: Path, writer=None, bedtime: bool = False) -> dict:
    """Write, check and store an episode. `writer(theme, cast[, bedtime=True]) -> dict | None` is the AI path.

    Bedtime episodes are calmer: the agent is asked for it, and either way `offline.bedtime_calm`
    swaps the lively moves out and gives every ending a sleepy last line.
    """
    if theme not in BACKDROPS:
        raise ValueError(f"unknown theme {theme!r}")
    if not cast:
        raise ValueError("add a star first")
    cast = cast[:4]
    ids = [c["id"] for c in cast]
    ep, source = None, "templates"
    if writer is not None:
        t0 = time.perf_counter()
        try:
            ep = writer(theme, cast, bedtime=True) if bedtime else writer(theme, cast)
        except Exception as e:  # network, throttling, guardrail block: the show must go on
            log.warning("story agent failed, using templates: %s", e)
        if ep is not None and validate(ep, ids, theme):
            log.warning("agent episode failed validation, using templates: %s", validate(ep, ids, theme))
            ep = None
        if ep is not None and bedtime:
            ep = offline.bedtime_calm(ep)
            if validate(ep, ids, theme):  # e.g. a 6-beat ending with no room for the sleepy line
                log.warning("bedtime agent episode failed validation, using templates: %s", validate(ep, ids, theme))
                ep = None
        if ep is not None:
            source = f"agent ({time.perf_counter() - t0:.1f}s)"
    if ep is None:
        ep = offline.episode(theme, cast, bedtime=bedtime)
    problems = validate(ep, ids, theme)
    if problems:  # templates are tested; this would be a bug
        raise RuntimeError("; ".join(problems))
    ep["id"] = uuid.uuid4().hex[:12]
    ep["theme"] = theme
    ep["source"] = source
    ep["bedtime"] = bool(bedtime)
    ep["cast"] = [{"id": c["id"], "name": c["name"], "pitch": TV_PITCHES[i % len(TV_PITCHES)]}
                  for i, c in enumerate(cast)]
    save_episode(ep, episodes)
    return ep


def save_episode(ep: dict, episodes: Path) -> None:
    episodes.mkdir(parents=True, exist_ok=True)
    (episodes / f"{ep['id']}.json").write_text(json.dumps(ep, indent=1), encoding="utf-8")


def load_episode(ep_id: str, episodes: Path) -> dict:
    return json.loads((episodes / f"{ep_id}.json").read_text(encoding="utf-8"))
