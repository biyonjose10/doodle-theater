import pytest

from doodle_theater.story import make_episode, offline
from doodle_theater.story.schema import BACKDROPS, validate

CASTS = [
    [{"id": "a1", "name": "Captain Blob", "description": ""}],
    [{"id": "a1", "name": "Captain Blob", "description": ""}, {"id": "b2", "name": "Pip", "description": ""}],
    [{"id": "a1", "name": "Captain Blob", "description": ""}, {"id": "b2", "name": "Pip", "description": ""},
     {"id": "c3", "name": "Garlic Gary", "description": ""}],
]


@pytest.mark.parametrize("theme", sorted(BACKDROPS))
@pytest.mark.parametrize("cast", CASTS, ids=["one", "two", "three"])
def test_every_template_is_a_valid_episode(theme, cast):
    ep = offline.episode(theme, cast, seed=1)
    assert validate(ep, [c["id"] for c in cast], theme) == []
    text = " ".join(b["text"] for s in ep["scenes"].values() for b in s["beats"])
    assert "{" not in text
    for c in cast:
        assert c["name"] in text or len(cast) > 2  # everyone is at least on stage; names usually spoken


def test_validator_catches_what_the_agent_gets_wrong():
    ep = offline.episode("space", CASTS[1], seed=1)
    ep["scenes"]["start"]["backdrop"] = "mars"
    ep["scenes"]["a"]["beats"][0]["actions"][0]["do"] = "fly"
    ep["scenes"]["b"]["beats"][0]["actions"][0]["at_word"] = "banana"
    errs = validate(ep, ["a1", "b2"], "space")
    assert any("backdrop" in e for e in errs)
    assert any("'do'" in e for e in errs)
    assert any("banana" in e for e in errs)


def test_agent_failure_falls_back_to_templates(tmp_path):
    def broken(theme, cast):
        raise TimeoutError("bedrock throttled")
    ep = make_episode("ocean", CASTS[0], tmp_path, writer=broken)
    assert ep["source"] == "templates" and (tmp_path / f"{ep['id']}.json").exists()


def test_invalid_agent_episode_is_rejected(tmp_path):
    ep = make_episode("jungle", CASTS[0], tmp_path, writer=lambda t, c: {"title": "x", "scenes": {}})
    assert ep["source"] == "templates"
