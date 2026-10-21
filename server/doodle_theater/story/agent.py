"""The story writer: a Strands agent on Amazon Bedrock that writes, checks and fixes its own episode.

The agent has three tools. It looks up which backdrops and moves exist, then submits a draft;
`submit_episode` runs the same validator the TV relies on and hands any problems back, so
the agent repairs its own mistakes (a move that doesn't exist, a cue word that isn't in the
line) before the child ever sees them. Bedrock Guardrails screen what goes in and comes out.
"""
from __future__ import annotations

import functools
import json
import logging
import re

from ..config import AWS_REGION, GUARDRAIL_ID, GUARDRAIL_VERSION, GUARDRAIL_NAME, OLLAMA_HOST, STORY_MODEL
from .schema import BACKDROPS, MOVES, STAGE_DIRECTIONS, THEME_TITLES, validate

log = logging.getLogger(__name__)

SYSTEM = """You write tiny bedtime plays for children aged 3 to 8, performed on a TV by puppets
made from the child's OWN drawings. The child picks one choice halfway through with the remote.

Rules:
- Warm, funny and gentle. Nothing scary, violent, sad or mean. No villains, only problems to fix together.
- Simple words a 5-year-old knows. Short sentences. Every line is read aloud, max 40 words per beat.
- Star EVERY cast member by name and work in one detail from each character's description, so the
  child recognises their drawing ("Captain Blob straightened her spiky purple crown").
- Shape: scene "start" (3-4 beats) ends with a choice of exactly 2 options (labels max 32 characters,
  each starting with a verb, each with one picture "emoji" that shows it, e.g. 🌙 for "Fly to the Moon",
  so children who can't read yet can choose too). Each option leads to its own scene (3-4 beats) that
  ends the story happily with the words "The end!".
- Every beat has at least one stage direction. Use "enter" for each character's first appearance.
  Time a direction to a word in the line with "at_word" (e.g. jump at "jumped") whenever it fits;
  that word MUST appear in the beat's text.
- speaker is "narrator" or a cast id for a line the character says.

Use the tools to look up backdrops and moves, then call submit_episode. If it returns problems,
fix every one and submit again. Stop once it says ACCEPTED."""

EXAMPLE = {
    "title": "Pip and the Lost Star",
    "scenes": {
        "start": {"backdrop": "space_station", "beats": [
            {"speaker": "narrator", "text": "Once upon a time, Pip pressed her nose to the window.",
             "actions": [{"who": "<id>", "do": "enter"}, {"who": "<id>", "do": "wave", "at_word": "window"}]}],
            "choice": {"prompt": "What should they do?",
                       "options": [{"label": "Fly to the Moon", "emoji": "🌙", "next": "moon"},
                                   {"label": "Chase the comet", "emoji": "☄️", "next": "comet"}]}},
        "moon": {"backdrop": "moon", "beats": ["..."]},
        "comet": {"backdrop": "comet", "beats": ["..."]},
    },
}


BEDTIME_NOTE = "It's bedtime: keep it calm and cosy, no running or scared moves, end sleepily."


def writer(theme: str, cast: list[dict], bedtime: bool = False) -> dict | None:
    """Write an episode with the Strands agent; None if it never produced a valid one."""
    from strands import Agent, tool
    from strands.models import BedrockModel

    ids = [c["id"] for c in cast]
    accepted: dict = {}

    @tool
    def list_backdrops() -> list[str]:
        """The backdrops available for tonight's theme. Every scene must use one of these."""
        return BACKDROPS[theme]

    @tool
    def list_moves() -> list[str]:
        """Stage directions the puppets can perform ('enter'/'exit' walk on or off stage)."""
        return STAGE_DIRECTIONS

    @tool
    def submit_episode(episode_json: str) -> str:
        """Submit the finished episode as a JSON string. Returns ACCEPTED, or the problems to fix."""
        try:
            ep = _loads(episode_json)
        except json.JSONDecodeError as e:
            accepted["last"] = f"That is not valid JSON ({e}). Submit the whole episode as one JSON object."
            return accepted["last"]
        problems = validate(ep, ids, theme)
        if problems:
            accepted["last"] = "Fix these problems and submit again:\n- " + "\n- ".join(problems[:12])
            return accepted["last"]
        accepted["episode"] = ep
        return "ACCEPTED. The story is ready."

    if STORY_MODEL.startswith("ollama:"):
        model = _ollama_model()
    else:
        kwargs = {}
        if guardrail := guardrail_id():
            kwargs.update(guardrail_id=guardrail, guardrail_version=GUARDRAIL_VERSION)
        model = BedrockModel(model_id=STORY_MODEL, region_name=AWS_REGION, temperature=0.8, max_tokens=4000,
                             **kwargs)
    agent = Agent(model=model, tools=[list_backdrops, list_moves, submit_episode],
                  system_prompt=SYSTEM, callback_handler=None)
    cast_lines = "\n".join(f'- id "{c["id"]}": {c["name"]}' + (f' ({c["description"]})' if c.get("description") else "")
                           for c in cast)
    bedtime_note = f"{BEDTIME_NOTE}\n\n" if bedtime else ""
    agent(f"Tonight's theme: {THEME_TITLES[theme]}.\nCast (the child's drawings):\n{cast_lines}\n\n{bedtime_note}"
          f"Moves: {', '.join(MOVES)}.\nFormat example (ids are placeholders):\n{json.dumps(EXAMPLE, ensure_ascii=False)}\n\n"
          "Write tonight's play and submit it.")
    # Smaller models sometimes stop after the look-ups, or after one rejected draft: nudge them on.
    for _ in range(3):
        if "episode" in accepted:
            break
        last = accepted.get("last")
        agent(f"The play is not accepted yet. {last + ' ' if last else ''}"
              "Call submit_episode now with the whole episode as one JSON string.")
    return accepted.get("episode")


def _loads(text: str):
    """json.loads, forgiving the slips small models make: code fences and trailing commas."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


@functools.cache
def guardrail_id() -> str:
    """DT_GUARDRAIL_ID, else the guardrail scripts/make_guardrail.py created in this account."""
    if GUARDRAIL_ID:
        return GUARDRAIL_ID
    try:
        import boto3
        found = boto3.client("bedrock", region_name=AWS_REGION).list_guardrails()["guardrails"]
    except Exception as e:
        log.warning("could not look up the guardrail, stories run without it: %s", e)
        return ""
    return next((g["id"] for g in found if g["name"] == GUARDRAIL_NAME), "")


def _ollama_model():
    """The same agent on a local model (DT_STORY_MODEL=ollama:<name>), for when Bedrock is unreachable.

    Guardrails are a Bedrock feature, so here the validator and the gentle system prompt are the
    only checks; qwen3's thinking mode is switched off so the story starts straight away.
    """
    from strands.models.ollama import OllamaModel
    return OllamaModel(OLLAMA_HOST, model_id=STORY_MODEL.removeprefix("ollama:"), temperature=0.8,
                       max_tokens=4000, additional_args={"think": False})


def available() -> bool:
    """Is the AI writer configured? (A local model, or AWS credentials; the model not switched off.)"""
    if STORY_MODEL.lower() == "off":
        return False
    if STORY_MODEL.startswith("ollama:"):
        return True
    from ..vision import has_aws
    return has_aws()
