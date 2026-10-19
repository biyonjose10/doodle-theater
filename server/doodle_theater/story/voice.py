"""Narration with Amazon Polly: one MP3 per beat plus word speech marks for read-along.

Neural voices: a warm narrator, and children's voices for the characters' own lines. The
TV reads `audio` + `marks` when present and falls back to its own TTS when they aren't.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..config import AWS_REGION, NARRATOR_VOICE

log = logging.getLogger(__name__)

CHARACTER_VOICES = ["Ivy", "Justin", "Kevin", "Salli", "Joey"]   # Ivy/Justin/Kevin are child voices


def _polly():
    import boto3
    return boto3.client("polly", region_name=AWS_REGION)


def narrate(ep: dict, media_dir: Path) -> dict:
    """Add `audio` and `marks` to every beat. Leaves the episode unchanged if Polly fails."""
    polly = _polly()
    voices = {c["id"]: CHARACTER_VOICES[i % len(CHARACTER_VOICES)] for i, c in enumerate(ep["cast"])}
    out = media_dir / ep["id"]
    out.mkdir(parents=True, exist_ok=True)
    try:
        for sid, scene in ep["scenes"].items():
            for i, beat in enumerate(scene["beats"]):
                voice = voices.get(beat.get("speaker"), NARRATOR_VOICE)
                text = beat["text"]
                audio = polly.synthesize_speech(Text=text, VoiceId=voice, Engine="neural", OutputFormat="mp3")
                name = f"{sid}-{i}.mp3"
                (out / name).write_bytes(audio["AudioStream"].read())
                marks_raw = polly.synthesize_speech(Text=text, VoiceId=voice, Engine="neural",
                                                    OutputFormat="json", SpeechMarkTypes=["word"])
                marks = []
                for line in marks_raw["AudioStream"].read().decode("utf-8").splitlines():
                    m = json.loads(line)
                    # Polly reports byte offsets into the UTF-8 text; the TV indexes characters.
                    start = len(text.encode("utf-8")[:m["start"]].decode("utf-8", "ignore"))
                    end = len(text.encode("utf-8")[:m["end"]].decode("utf-8", "ignore"))
                    marks.append({"time": m["time"], "start": start, "end": end})
                beat["audio"] = f"/media/{ep['id']}/{name}"
                beat["marks"] = marks
        ep["voice"] = "polly"
    except Exception as e:
        log.warning("Polly narration failed, the TV will use its own voice: %s", e)
        for scene in ep["scenes"].values():
            for beat in scene["beats"]:
                beat.pop("audio", None)
                beat.pop("marks", None)
    return ep
