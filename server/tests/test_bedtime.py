import pytest

from doodle_theater.story import is_bedtime, make_episode, offline
from doodle_theater.story.schema import BACKDROPS, validate, words
from doodle_theater.story.voice import BEDTIME_CLOSE, BEDTIME_OPEN, polly_input, to_char_marks

CAST = [{"id": "a1", "name": "Captain Blob", "description": ""}, {"id": "b2", "name": "Pip", "description": ""}]


def _fake_marks(text: str, sent: str, starts: list[int]) -> list[dict]:
    """What Polly would report: byte offsets of each word in what was sent (escaped as it was sent)."""
    raw, enc, cursor = [], sent.encode("utf-8"), 0
    for w in ["Fish", "&", "chips", "<3", "café", "naïve"]:
        i = text.index(w, cursor)
        cursor = i + len(w)
        # the word's bytes in the sent string run from the start of its first char to the end of its last
        raw.append({"time": len(raw) * 100, "type": "word", "start": starts[i], "end": starts[i + len(w)],
                    "value": enc[starts[i]:starts[i + len(w)]].decode("utf-8")})
    return raw


@pytest.mark.parametrize("bedtime", [False, True])
def test_speech_marks_map_back_to_plain_text(bedtime):
    text = "Fish & chips <3 for the café, said naïve Pip."
    sent, starts = polly_input(text, bedtime)
    marks = to_char_marks(_fake_marks(text, sent, starts), starts, text)
    assert [text[m["start"]:m["end"]] for m in marks] == ["Fish", "&", "chips", "<3", "café", "naïve"]


def test_bedtime_ssml_is_wrapped_and_escaped():
    sent, starts = polly_input("Tom & Jerry <3 > all", True)
    assert sent == BEDTIME_OPEN + "Tom &amp; Jerry &lt;3 &gt; all" + BEDTIME_CLOSE
    assert starts[0] == len(BEDTIME_OPEN)          # 'T' starts right after the prefix
    assert sent.encode()[starts[4]:starts[5]] == b"&amp;"
    plain, pstarts = polly_input("Tom & Jerry", False)
    assert plain == "Tom & Jerry" and pstarts[0] == 0


def test_real_polly_shaped_marks_with_utf8():
    # Polly's own numbers for '<speak><prosody rate="90%" volume="-3dB">Hi café!</prosody></speak>'
    sent, starts = polly_input("Hi café!", True)
    p = len(BEDTIME_OPEN)
    raw = [{"time": 6, "start": p, "end": p + 2}, {"time": 200, "start": p + 3, "end": p + 8}]
    assert to_char_marks(raw, starts, "Hi café!") == [{"time": 6, "start": 0, "end": 2}, {"time": 200, "start": 3, "end": 7}]


@pytest.mark.parametrize("bedtime", [False, True])
def test_marks_after_an_emoji_count_utf16_units_like_the_tv(bedtime):
    # The TV highlights with Kotlin's substring, which counts UTF-16 units: the rocket is two.
    text = "Go 🚀 Pip go!"
    sent, starts = polly_input(text, bedtime)
    raw = [{"time": 0, "start": starts[0], "end": starts[2]},    # Go
           {"time": 100, "start": starts[5], "end": starts[8]}]  # Pip
    marks = to_char_marks(raw, starts, text)
    utf16 = text.encode("utf-16-le")
    assert [utf16[2 * m["start"]:2 * m["end"]].decode("utf-16-le") for m in marks] == ["Go", "Pip"]


@pytest.mark.parametrize("theme", sorted(BACKDROPS))
@pytest.mark.parametrize("n", [1, 2, 4])
def test_bedtime_templates_are_calm_and_valid(theme, n):
    cast = [{"id": f"c{i}", "name": f"Star Number {i}", "description": ""} for i in range(n)]
    ep = offline.episode(theme, cast, seed=3, bedtime=True)
    assert validate(ep, [c["id"] for c in cast], theme) == []
    moves = {a["do"] for s in ep["scenes"].values() for b in s["beats"] for a in b["actions"]}
    assert not moves & {"scared", "run"}
    for sid in ("a", "b"):
        last = ep["scenes"][sid]["beats"][-1]["text"]
        assert last.endswith("The end!")
        assert offline.SLEEPY_WORDS & set(words(last)), last


def test_bedtime_keeps_already_sleepy_endings_and_splits_long_ones():
    ep = offline.episode("space", CAST, seed=1)
    ep["scenes"]["a"]["beats"][-1]["text"] = "Everyone danced, then snuggled down to sleep. The end!"
    long = " ".join(["la"] * 36) + " danced. The end!"
    ep["scenes"]["b"]["beats"][-1] = {"speaker": "narrator", "text": long,
                                      "actions": [{"who": "a1", "do": "dance", "at_word": "danced"}]}
    offline.bedtime_calm(ep)
    assert ep["scenes"]["a"]["beats"][-1]["text"] == "Everyone danced, then snuggled down to sleep. The end!"
    assert ep["scenes"]["b"]["beats"][-1]["text"] == f"{offline.SLEEPY_LINE} The end!"
    assert not ep["scenes"]["b"]["beats"][-2]["text"].endswith("The end!")
    assert validate(ep, ["a1", "b2"], "space") == []


def test_daytime_templates_are_unchanged():
    assert offline.episode("space", CAST, seed=1) == offline.episode("space", CAST, seed=1, bedtime=False)
    moves = {a["do"] for s in offline.episode("space", CAST, seed=1)["scenes"].values()
             for b in s["beats"] for a in b["actions"]}
    assert "scared" in moves  # bedtime is what removes them


def test_make_episode_passes_bedtime_to_the_writer_and_calms_its_episode(tmp_path):
    seen = {}

    def writer(theme, cast, bedtime=False):
        seen["bedtime"] = bedtime
        return offline.episode(theme, cast, seed=2)  # a lively episode, as if the agent ignored the note
    ep = make_episode("dino", CAST, tmp_path, writer=writer, bedtime=True)
    assert seen["bedtime"] is True and ep["bedtime"] is True and ep["source"].startswith("agent")
    moves = {a["do"] for s in ep["scenes"].values() for b in s["beats"] for a in b["actions"]}
    assert not moves & {"scared", "run"}
    day = make_episode("dino", CAST, tmp_path, writer=lambda t, c: None)  # old two-argument writers still work
    assert day["bedtime"] is False


@pytest.mark.parametrize("hour,expected", [(18, False), (19, True), (23, True), (0, True), (5, True),
                                           (6, False), (12, False)])
def test_bedtime_window_wraps_midnight(hour, expected):
    assert is_bedtime(hour, start=19, end=6) is expected


def test_bedtime_window_same_day_and_off():
    assert is_bedtime(14, start=13, end=15) and not is_bedtime(15, start=13, end=15)
    assert not is_bedtime(20, start=20, end=20)  # equal start and end: never bedtime
