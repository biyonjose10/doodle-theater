"""Record Doodle Theater demo clips from the emulator, with the Polly narration rebuilt as audio.

screenrecord captures no sound, so this watches the server log: every narration line is an MP3
the TV fetches just before playing it. Fetch time + the MP3 = a synced soundtrack.

usage: python record.py <clip> [--server-log PATH]
clips: home_add, party, story, pause
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

os.environ["MSYS_NO_PATHCONV"] = "1"


def adb(*args, check=False):
    return subprocess.run(ADB + list(args), capture_output=True, text=True, check=check)


def key(name):
    adb("shell", "input", "keyevent", f"KEYCODE_{name}")


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


def soundtrack(video: Path, start: float, watch: LogWatch, pauses=(), tail=7.0):
    """Mux the fetched MP3s onto the video at their play times. pauses: [(t_pause, t_resume)]."""
    segs = []  # (file, offset_in_clip, trim_start, trim_end|None)
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
    end = max(at + ((e if e else duration(f)) - s) for f, at, s, e in segs) + tail
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


def clip_home_add(watch):
    """Home (stars + themes) -> Add a star -> QR -> a new star walks in and waves."""
    launch()
    time.sleep(4)
    p, start = record("home_add", 40)
    time.sleep(3)
    key("DPAD_DOWN"); time.sleep(1.2); key("DPAD_RIGHT"); time.sleep(1.2); key("DPAD_RIGHT"); time.sleep(1.2)
    key("DPAD_UP"); time.sleep(1.5)  # back onto "Add a star" (focus starts there)
    key("DPAD_LEFT"); key("DPAD_LEFT"); key("DPAD_LEFT"); key("DPAD_LEFT"); time.sleep(1)
    key("DPAD_CENTER")
    _, m = wait_for(watch, r"GET /api/tv/(\w+)/events", 15)
    code = m.group(1)
    time.sleep(7)  # hold on the QR, while "the parent scans it"
    draft = upload(code, CHARS / "cat.png")
    post(f"/api/p/{code}/draft/{draft['id']}/send", {"name": "Queen Whiskers"})
    finish(p, "home_add")
    return draft["id"]


def clip_party(watch):
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


def clip_story(watch, theme_index=2, seconds=180):
    """Pick a theme, play the whole story, take the second choice, reach The End."""
    _start_story(theme_index)
    p, start = record("story", seconds)
    time.sleep(1.5)
    key("DPAD_CENTER")
    _, m = wait_for(watch, r"GET /media/(\w+)/start-0\.mp3", 60)
    ep = json.load(urllib.request.urlopen(f"{SERVER}/api/story/{m.group(1)}"))
    last = len(ep["scenes"]["start"]["beats"]) - 1
    t, _ = wait_for(watch, rf"GET /media/\w+/start-{last}\.mp3", 120)
    end_of_scene = t + duration(MEDIA / m.group(1) / f"start-{last}.mp3") + 1.5
    time.sleep(max(0, end_of_scene - time.time()) + 2.5)  # let the choice sit on screen
    key("DPAD_RIGHT"); time.sleep(1.5); key("DPAD_CENTER")
    video = finish(p, "story")
    return soundtrack(video, start, watch), ep["title"]


def clip_pause(watch, theme_index=0):
    """A story starts; mid-line it is paused (as by "Alexa, pause") and resumed."""
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
    result = {"home_add": clip_home_add, "party": clip_party, "story": clip_story, "pause": clip_pause}[a.clip](w)
    w.stop = True
    print("DONE", result)
