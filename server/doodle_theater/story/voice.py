"""Narration with Amazon Polly: one MP3 per beat plus word speech marks for read-along.

Neural voices: a warm narrator, and children's voices for the characters' own lines. The
TV reads `audio` + `marks` when present and falls back to its own TTS when they aren't.

Bedtime episodes are read slower and softer through SSML <prosody> (neural voices support
`rate` and `volume`, not `pitch`). Polly then reports speech-mark offsets into the SSML string,
so they are mapped back to positions in the beat's plain text, which the TV highlights. Those
positions count UTF-16 units, as Kotlin strings do, so an emoji (two units) doesn't shift the rest.
"""
from __future__ import annotations

import bisect
import json
import logging
from pathlib import Path

from ..config import AWS_REGION, NARRATOR_VOICE

log = logging.getLogger(__name__)

CHARACTER_VOICES = ["Ivy", "Justin", "Kevin", "Salli", "Joey"]   # Ivy/Justin/Kevin are child voices

BEDTIME_OPEN = '<speak><prosody rate="90%" volume="-3dB">'
BEDTIME_CLOSE = "</prosody></speak>"
_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def polly_input(text: str, bedtime: bool) -> tuple[str, list[int]]:
    """What to send Polly for `text`, and the UTF-8 byte offset where each character of `text` begins in it.

    Plain text is sent as-is; bedtime wraps it in SSML (escaping &, < and >). The offsets list has
    one entry per character plus a final one for the end of the text, for mapping marks back.
    """
    prefix = BEDTIME_OPEN if bedtime else ""
    pos = len(prefix.encode("utf-8"))
    parts, starts = [prefix], []
    for ch in text:
        out = _ESCAPES.get(ch, ch) if bedtime else ch
        starts.append(pos)
        parts.append(out)
        pos += len(out.encode("utf-8"))
    starts.append(pos)
    if bedtime:
        parts.append(BEDTIME_CLOSE)
    return "".join(parts), starts


def to_char_marks(raw: list[dict], starts: list[int], text: str) -> list[dict]:
    """Polly word marks (byte offsets into what was sent) -> {time, start, end} as UTF-16 offsets into `text`."""
    n = len(starts) - 1
    u16 = [0]
    for ch in text:
        u16.append(u16[-1] + (2 if ord(ch) > 0xFFFF else 1))
    marks = []
    for m in raw:
        # start: the character whose bytes contain m["start"]; end: first character starting at/after m["end"].
        start = min(max(bisect.bisect_right(starts, m["start"]) - 1, 0), n)
        end = min(max(bisect.bisect_left(starts, m["end"]), start), n)
        marks.append({"time": m["time"], "start": u16[start], "end": u16[end]})
    return marks


def _polly():
    import boto3
    return boto3.client("polly", region_name=AWS_REGION)


def narrate(ep: dict, media_dir: Path) -> dict:
    """Add `audio` and `marks` to every beat. Leaves the episode unchanged if Polly fails."""
    polly = _polly()
    voices = {c["id"]: CHARACTER_VOICES[i % len(CHARACTER_VOICES)] for i, c in enumerate(ep["cast"])}
    bedtime = bool(ep.get("bedtime"))
    text_type = "ssml" if bedtime else "text"
    out = media_dir / ep["id"]
    out.mkdir(parents=True, exist_ok=True)
    try:
        for sid, scene in ep["scenes"].items():
            for i, beat in enumerate(scene["beats"]):
                voice = voices.get(beat.get("speaker"), NARRATOR_VOICE)
                sent, starts = polly_input(beat["text"], bedtime)
                audio = polly.synthesize_speech(Text=sent, TextType=text_type, VoiceId=voice, Engine="neural",
                                                OutputFormat="mp3")
                name = f"{sid}-{i}.mp3"
                (out / name).write_bytes(audio["AudioStream"].read())
                marks_raw = polly.synthesize_speech(Text=sent, TextType=text_type, VoiceId=voice, Engine="neural",
                                                    OutputFormat="json", SpeechMarkTypes=["word"])
                raw = [json.loads(line) for line in marks_raw["AudioStream"].read().decode("utf-8").splitlines()
                       if line.strip()]
                beat["audio"] = f"/media/{ep['id']}/{name}"
                beat["marks"] = to_char_marks(raw, starts, beat["text"])
        ep["voice"] = "polly"
    except Exception as e:
        log.warning("Polly narration failed, the TV will use its own voice: %s", e)
        for scene in ep["scenes"].values():
            for beat in scene["beats"]:
                beat.pop("audio", None)
                beat.pop("marks", None)
    return ep
