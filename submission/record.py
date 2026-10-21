"""Record Doodle Theater demo clips from the emulator, with the Polly narration rebuilt as audio.

screenrecord captures no sound, so this watches the server log: every narration line is an MP3
the TV fetches just before playing it. Fetch time + the MP3 = a synced soundtrack.

The bedtime wind-down at the end of a story ("The end!", "Goodnight, <names>.") is the TV's own
text-to-speech, not a fetched MP3, so those two lines are made with Polly (same narrator voice)
and placed where the TV says them: just after the last story line ends and the stage starts to dim.

Daytime clips switch the emulator to UTC (Bedtime off by the clock); the bedtime clip switches it
back to Asia/Kolkata (evening). The emulator is always left on Asia/Kolkata.

usage: python record.py <clip> --server-log PATH
clips: home_add, party, story, pause, bedtime
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

ADB = [os.environ.get("ADB", "adb"), "-s", "emulator-5554"]
SERVER = "http://127.0.0.1:8787"
MEDIA = Path(__file__).resolve().parent.parent / "server" / "data" / "media"
OUT = Path(__file__).resolve().parent / "clips"
CHARS = Path(os.environ.get("DT_CHARS", Path(__file__).resolve().parent / "chars"))  # cropped drawing photos
PLAY_LATENCY = 0.15  # fetch -> sound, roughly
HOME_TZ = "Asia/Kolkata"  # the emulator's own timezone (evening while recording -> Bedtime on)
DAY_TZ = "UTC"            # afternoon while recording -> Bedtime off
KEEP_CAT = "93975a973b1a"  # the original Queen Whiskers; home_add adds a duplicate that is removed again
# Wind-down timing, measured on the 2026-10-21 Under the Sea take (caption gone at 53.10 s, card at 62.77 s,
# last MP3 ending at 52.21 s by the log): the log-based end of the last line runs ~0.45 s early.
WIND_START = 0.9              # last story line ends (by the log) -> wind-down starts (caption gone, dim begins)
WIND_END_DELAY = 0.4          # wind-down starts -> TV TTS says "The end!"
WIND_GAP = 1.2 + 0.3          # "The end!" ends -> 1.2 s pause + TTS start-up -> "Goodnight, ..."
WIND_CARD = 9.67              # wind-down starts -> Goodnight card (9 s dim + 0.6 s)
CHOICE_DELAY = 2.1            # last line before a choice ends (by the log) -> TV TTS reads the choice out

os.environ["MSYS_NO_PATHCONV"] = "1"


def adb(*args, check=False):
    return subprocess.run(ADB + list(args), capture_output=True, text=True, check=check)


def key(name):
    adb("shell", "input", "keyevent", f"KEYCODE_{name}")


def set_tz(tz: str):
    adb("shell", "service", "call", "alarm", "3", "s16", tz)
    print("emulator clock:", adb("shell", "date").stdout.strip())


def polly_line(text: str, path: Path, rate: str = "85%") -> Path:
    """One wind-down line in the story narrator's voice (cached on disk)."""
    if not path.exists():
        import boto3
        r = boto3.client("polly", region_name="us-east-1").synthesize_speech(
            Text=f'<speak><prosody rate="{rate}">{text}</prosody></speak>', TextType="ssml",
            VoiceId="Ruth", Engine="neural", OutputFormat="mp3")
        path.write_bytes(r["AudioStream"].read())
    return path


def join_names(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


class LogWatch(threading.Thread):
    """Timestamps every new server-log line."""

    def __init__(self, path: Path):
        super().__init__(daemon=True)
        self.path, self.lines, self.stop = path, [], False
        self.f = open(path, encoding="utf-8", errors="ignore")
        self.f.seek(0, 2)

    def run(self):
        while not self.stop:
            line = self.f.readline()
            if line:
                self.lines.append((time.time(), line.rstrip()))
            else:
                time.sleep(0.02)

    def media(self):
        out = []
        for t, line in self.lines:
            m = re.search(r'GET /media/(\w+)/([\w-]+\.mp3)', line)
            if m:
                out.append((t, m.group(1), m.group(2)))
        return out

    def find(self, pattern):
        for t, line in self.lines:
            m = re.search(pattern, line)
            if m:
                return t, m
        return None


def wait_for(watch: LogWatch, pattern: str, timeout: float):
    end = time.time() + timeout
    while time.time() < end:
        hit = watch.find(pattern)
        if hit:
            return hit
        time.sleep(0.05)
    raise TimeoutError(pattern)


def record(name: str, seconds: int):
    """Start screenrecord in the background; returns (process, start_time)."""
    adb("shell", "rm", "-f", f"/sdcard/{name}.mp4")
    p = subprocess.Popen(ADB + ["shell", "screenrecord", "--bit-rate", "12000000",
                                "--time-limit", str(seconds), f"/sdcard/{name}.mp4"])
    time.sleep(0.5)  # screenrecord's own start-up
    return p, time.time()


def stop_recording():
    """End screenrecord early; SIGINT lets it finish the MP4 properly."""
    adb("shell", "pkill", "-INT", "screenrecord")


def finish(p, name: str):
    p.wait()
    time.sleep(1)
    OUT.mkdir(exist_ok=True)
    adb("pull", f"/sdcard/{name}.mp4", str(OUT / f"{name}.mp4"), check=True)
    return OUT / f"{name}.mp4"


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def soundtrack(video: Path, start: float, watch: LogWatch, pauses=(), tail=7.0, extra=(), length=None):
    """Mux the fetched MP3s onto the video at their play times. pauses: [(t_pause, t_resume)].
    extra: [(mp3, offset_in_clip)] for lines the TV speaks itself. length: fixed output length."""
    segs = [(f, at, 0.0, None) for f, at in extra]  # (file, offset_in_clip, trim_start, trim_end|None)
    for t, ep, mp3 in watch.media():
        f = MEDIA / ep / mp3
        at = t - start + PLAY_LATENCY
        d = duration(f)
        cut = 0.0
        for tp, tr in pauses:
            p0, r0 = tp - start, tr - start
            if at < p0 < at + d:  # this line was paused mid-way
                segs.append((f, at, 0.0, p0 - at))
                cut = p0 - at
                at = r0
                break
        segs.append((f, at, cut, None))
    if not segs:
        return video
    inputs, filters = ["-i", str(video)], []
    for i, (f, at, s, e) in enumerate(segs):
        inputs += ["-i", str(f)]
        trim = f"atrim=start={s:.3f}" + (f":end={e:.3f}" if e else "") + ",asetpts=PTS-STARTPTS,"
        filters.append(f"[{i + 1}:a]{trim}adelay={max(0, int(at * 1000))}:all=1[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(segs)))
    filters.append(f"{mix}amix=inputs={len(segs)}:normalize=0,apad[aout]")
    end = length or max(at + ((e if e else duration(f)) - s) for f, at, s, e in segs) + tail
    out = video.with_name(video.stem + "_sound.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
                    "-map", "0:v", "-map", "[aout]", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-r", "30", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{end:.2f}", str(out)], check=True)
    return out


def post(path, body):
    req = urllib.request.Request(SERVER + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


def upload(code: str, png: Path):
    boundary = "----dt"
    data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{png.name}\"\r\n"
            "Content-Type: image/png\r\n\r\n").encode() + png.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{SERVER}/api/p/{code}/photo", data=data, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.load(urllib.request.urlopen(req))


def launch(screen=None):
    args = ["shell", "am", "start", "-S", "-n", "com.doodletheater.tv/.MainActivity"]
    if screen:
        args += ["--es", "screen", screen]
    adb(*args)


def remove_duplicate_cats():
    cast = json.load(urllib.request.urlopen(f"{SERVER}/api/cast"))["cast"]
    for c in cast:
        if c["name"] == "Queen Whiskers" and c["id"] != KEEP_CAT:
            urllib.request.urlopen(urllib.request.Request(f"{SERVER}/api/cast/{c['id']}", method="DELETE"))
            print("removed duplicate", c["id"])


def clip_home_add(watch):
    """Home: focus over the stars (Selected tag) and the themes -> Add a star -> QR -> a new star arrives."""
    set_tz(DAY_TZ)
    launch()
    time.sleep(4)
    p, start = record("home_add", 42)
    time.sleep(2.5)
    for k in ["DPAD_RIGHT", "DPAD_RIGHT", "DPAD_RIGHT", "DPAD_DOWN", "DPAD_RIGHT", "DPAD_RIGHT"]:
        key(k); time.sleep(1.2)
    key("DPAD_UP"); time.sleep(1.2)
    for _ in range(5):
        key("DPAD_LEFT"); time.sleep(0.25)  # back onto "Add a star"
    time.sleep(1)
    key("DPAD_CENTER")
    _, m = wait_for(watch, r"GET /api/tv/(\w+)/events", 15)
    code = m.group(1)
    time.sleep(7)  # hold on the QR, while "the parent scans it"
    try:
        draft = upload(code, CHARS / "cat.png")
        post(f"/api/p/{code}/draft/{draft['id']}/send", {"name": "Queen Whiskers"})
        finish(p, "home_add")
    finally:
        time.sleep(1)
        remove_duplicate_cats()
    return draft["id"]


def clip_party(watch):
    set_tz(DAY_TZ)
    launch("party")
    time.sleep(5)
    p, start = record("party", 30)
    time.sleep(2.5)
    for k in ["DPAD_CENTER", None, "DPAD_RIGHT", "DPAD_CENTER", None, "DPAD_RIGHT", "DPAD_CENTER", None,
              "DPAD_RIGHT", "DPAD_CENTER", None, "MEDIA_PLAY_PAUSE"]:
        if k:
            key(k)
        time.sleep(1.4)
    finish(p, "party")


def _start_story(theme_index: int):
    launch()
    time.sleep(4)
    key("DPAD_DOWN"); time.sleep(0.8)
    for _ in range(theme_index):
        key("DPAD_RIGHT"); time.sleep(0.5)


def wind_down(watch, start, ep_id, ep):
    """Polly stand-ins for the TV's own goodnight lines, and where they fall in the clip (s)."""
    last = [x for x in watch.media() if x[1] == ep_id][-1]
    dim = last[0] - start + PLAY_LATENCY + duration(MEDIA / ep_id / last[2]) + WIND_START  # dim begins
    names = join_names([c["name"] for c in ep["cast"]])
    the_end = polly_line("The end!", OUT / "winddown_the_end.mp3")
    night = polly_line(f"Goodnight, {names}.", OUT / "winddown_goodnight.mp3", rate="80%")
    t1 = dim + WIND_END_DELAY
    t2 = t1 + duration(the_end) + WIND_GAP
    print(f"wind-down: dim begins {dim:.2f}s, 'The end!' {t1:.2f}s, goodnight {t2:.2f}s, "
          f"card ~{dim + WIND_CARD:.2f}s  ({names})")
    return [(the_end, t1), (night, t2)], dim


def play_story(watch, name, seconds, pick_right=True, hold_end=4.0, before_ok=1.5, setup=None):
    """Record from before OK on the focused theme through the wind-down to the Goodnight card."""
    p, start = record(name, seconds)
    if setup:
        setup()
    time.sleep(before_ok)
    key("DPAD_CENTER")
    _, m = wait_for(watch, r"GET /media/(\w+)/start-0\.mp3", 90)
    ep_id = m.group(1)
    ep = json.load(urllib.request.urlopen(f"{SERVER}/api/story/{ep_id}"))
    last = len(ep["scenes"]["start"]["beats"]) - 1
    t, _ = wait_for(watch, rf"GET /media/{ep_id}/start-{last}\.mp3", 150)
    end_of_scene = t + duration(MEDIA / ep_id / f"start-{last}.mp3") + 1.5
    # the TV reads the choice out with its own TTS: a Polly stand-in, like the wind-down lines
    ch = ep["scenes"]["start"]["choice"]
    prompt = polly_line(f"{ch['prompt']} {ch['options'][0]['label']}, or {ch['options'][1]['label']}?",
                        OUT / f"{name}_choice_prompt.mp3", rate="92%")
    choice_at = t + PLAY_LATENCY + duration(MEDIA / ep_id / f"start-{last}.mp3") + CHOICE_DELAY - start
    time.sleep(max(0, end_of_scene - time.time()) + 2.5)  # let the choice sit on screen
    if pick_right:
        key("DPAD_RIGHT"); time.sleep(1.5)
    key("DPAD_CENTER")
    # the second scene: wait until its MP3s stop coming, then for the wind-down and the card
    n_seen = -1
    while True:
        time.sleep(4)
        mine = [x for x in watch.media() if x[1] == ep_id]
        if len(mine) == n_seen and time.time() - mine[-1][0] > duration(MEDIA / ep_id / mine[-1][2]) + 1:
            break
        n_seen = len(mine)
    extra, dim = wind_down(watch, start, ep_id, ep)
    stop_at = start + dim + WIND_CARD + hold_end
    time.sleep(max(0, stop_at - time.time()))
    stop_recording()
    video = finish(p, name)
    length = min(duration(video), dim + WIND_CARD + hold_end)
    print("episode", ep_id, ep["title"], "bedtime" if ep.get("bedtime") else "day")
    return soundtrack(video, start, watch, extra=[(prompt, choice_at)] + extra, length=length), ep["title"]


def clip_story(watch, theme_index=2, seconds=150):
    """Under the Sea in daytime: the choice (emoji cards), the second option, the wind-down, Goodnight."""
    set_tz(DAY_TZ)
    _start_story(theme_index)
    return play_story(watch, "story", seconds)


def clip_bedtime(watch, seconds=180):
    """Evening: Home with Bedtime ON (focus up to the two chips), then Space Adventure, bedtime edition."""
    set_tz(HOME_TZ)
    launch()
    time.sleep(5)

    def pan():
        time.sleep(2.5)
        for k, d in [("DPAD_RIGHT", 1.3), ("DPAD_UP", 2.0), ("DPAD_UP", 2.6), ("DPAD_DOWN", 1.2),
                     ("DPAD_DOWN", 1.2), ("DPAD_DOWN", 1.2)]:
            key(k); time.sleep(d)
        for _ in range(6):
            key("DPAD_LEFT"); time.sleep(0.3)  # onto Space Adventure

    return play_story(watch, "bedtime", seconds, pick_right=False, setup=pan)


def clip_pause(watch, theme_index=0):
    """A story starts; mid-line it is paused (as by "Alexa, pause") and resumed."""
    set_tz(DAY_TZ)
    _start_story(theme_index)
    p, start = record("pause", 30)
    time.sleep(1)
    key("DPAD_CENTER")
    t, m = wait_for(watch, r"GET /media/(\w+)/start-1\.mp3", 60)
    time.sleep(max(0, t + 1.6 - time.time()))
    tp = time.time(); adb("shell", "cmd", "media_session", "dispatch", "pause")
    time.sleep(3)
    tr = time.time(); adb("shell", "cmd", "media_session", "dispatch", "play")
    video = finish(p, "pause")
    return soundtrack(video, start, watch, pauses=[(tp, tr)])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--server-log", required=True)
    a = ap.parse_args()
    w = LogWatch(Path(a.server_log)); w.start()
    clips = {"home_add": clip_home_add, "party": clip_party, "story": clip_story, "pause": clip_pause,
             "bedtime": clip_bedtime}
    try:
        result = clips[a.clip](w)
    finally:
        w.stop = True
        set_tz(HOME_TZ)
    print("DONE", result)
