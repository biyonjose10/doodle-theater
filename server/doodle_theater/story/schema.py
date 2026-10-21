"""The episode format the TV plays, and the checks every episode must pass.

An episode is a tiny branching play: an opening scene ending in a choice, and one
scene per option. Every beat is a line of narration or dialogue plus stage directions.
"""
from __future__ import annotations

import re

from doodlerig.pose import motions

MOVES = sorted(motions())                     # idle, walk, run, jump, wave, dance, cheer, spin, scared
STAGE_DIRECTIONS = MOVES + ["enter", "exit"]  # enter/exit = walk on from / off to the wings

BACKDROPS: dict[str, list[str]] = {
    "space": ["space_station", "moon", "comet"],
    "jungle": ["jungle_path", "river", "temple"],
    "ocean": ["reef", "shipwreck", "kelp_forest"],
    "castle": ["castle_gate", "throne_room", "dragon_cave"],
    "snow": ["snowy_village", "ice_cave", "mountain_top"],
    "dino": ["dino_valley", "volcano", "nest"],
}
THEME_TITLES = {"space": "Space Adventure", "jungle": "Jungle Explorer", "ocean": "Under the Sea",
                "castle": "Dragon Castle", "snow": "Snowy Mountain", "dino": "Dinosaur Valley"}

MAX_WORDS_PER_BEAT = 40
_WORD = re.compile(r"[A-Za-z']+")


MAX_EMOJI_CHARS = 8  # one emoji, allowing variation selectors and ZWJ sequences


def is_emoji(value) -> bool:
    """Loose check for 'one picture emoji': short, and no letters, digits or spaces (so not a word)."""
    return (isinstance(value, str) and 0 < len(value) <= MAX_EMOJI_CHARS
            and not any(ch.isalnum() or ch.isspace() for ch in value))


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def validate(ep: dict, cast_ids: list[str], theme: str) -> list[str]:
    """Human-readable problems; empty means the TV can play it. Fed back to the agent to fix."""
    errs: list[str] = []
    if not isinstance(ep, dict):
        return ["episode must be a JSON object"]
    if not str(ep.get("title", "")).strip():
        errs.append("missing title")
    scenes = ep.get("scenes")
    if not isinstance(scenes, dict) or "start" not in scenes:
        return errs + ["scenes must be an object with a 'start' scene"]
    allowed_backdrops = BACKDROPS.get(theme, [])
    speakers = set(cast_ids) | {"narrator"}

    start = scenes["start"]
    choice = start.get("choice") if isinstance(start, dict) else None
    if not isinstance(choice, dict) or len(choice.get("options", [])) != 2:
        errs.append("the start scene must end with a choice that has exactly 2 options")
        targets = []
    else:
        targets = [o.get("next") for o in choice["options"]]
        for o in choice["options"]:
            if not str(o.get("label", "")).strip() or len(o.get("label", "")) > 32:
                errs.append("each choice label must be 1-32 characters")
            if "emoji" in o and not is_emoji(o["emoji"]):
                errs.append(f"choice emoji must be one picture emoji (max {MAX_EMOJI_CHARS} characters), "
                            f"not {o['emoji']!r}")
            if o.get("next") not in scenes or o.get("next") == "start":
                errs.append(f"choice option points to unknown scene {o.get('next')!r}")
    if set(scenes) != {"start", *targets}:
        errs.append(f"scenes must be exactly 'start' plus the two choice targets; got {sorted(scenes)}")

    for sid, sc in scenes.items():
        if not isinstance(sc, dict):
            errs.append(f"scene {sid} must be an object"); continue
        if sc.get("backdrop") not in allowed_backdrops:
            errs.append(f"scene {sid}: backdrop must be one of {allowed_backdrops}")
        beats = sc.get("beats")
        if not isinstance(beats, list) or not 2 <= len(beats) <= 6:
            errs.append(f"scene {sid}: needs 2-6 beats"); continue
        if sid != "start" and sc.get("choice"):
            errs.append(f"scene {sid}: only the start scene may have a choice")
        for i, b in enumerate(beats):
            where = f"scene {sid} beat {i + 1}"
            text = str(b.get("text", "")).strip()
            if not text:
                errs.append(f"{where}: empty text")
            elif len(words(text)) > MAX_WORDS_PER_BEAT:
                errs.append(f"{where}: {len(words(text))} words, max {MAX_WORDS_PER_BEAT}")
            if b.get("speaker", "narrator") not in speakers:
                errs.append(f"{where}: speaker must be 'narrator' or a cast id {cast_ids}")
            acts = b.get("actions", [])
            if not isinstance(acts, list) or not acts:
                errs.append(f"{where}: every beat needs at least one action so the stage moves")
                continue
            for a in acts:
                if a.get("who") not in cast_ids:
                    errs.append(f"{where}: action 'who' must be a cast id {cast_ids}")
                if a.get("do") not in STAGE_DIRECTIONS:
                    errs.append(f"{where}: action 'do' must be one of {STAGE_DIRECTIONS}")
                w = a.get("at_word")
                if w is not None and str(w).lower() not in words(text):
                    errs.append(f"{where}: at_word {w!r} does not appear in the beat's text")
    present = {a.get("who") for sc in scenes.values() if isinstance(sc, dict)
               for b in sc.get("beats", []) for a in b.get("actions", [])}
    for cid in cast_ids:
        if cid not in present:
            errs.append(f"cast member {cid} never appears in any action")
    return errs
