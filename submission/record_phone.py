"""Record clip C: the parent's phone adding a star, with the TV recorded at the same time.

The phone page opens the camera straight away, which a script can't point at paper, so the
photo is handed to the page through Chrome's remote debugging (exactly the file the camera
would return); every other step is a real touch on the real page.

usage: python record_phone.py <PAIR_CODE> <photo.png> "<Star name>"
needs: phone + emulator on adb, `adb reverse tcp:8787 tcp:8787`, websocket-client
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websocket

ADB = os.environ.get("ADB", "adb")
PHONE = os.environ.get("PHONE_SERIAL", "")
TV = "emulator-5554"
OUT = Path(__file__).resolve().parent / "clips"
os.environ["MSYS_NO_PATHCONV"] = "1"


def adb(serial, *args):
    return subprocess.run([ADB, "-s", serial, *args], capture_output=True, text=True)


class Page:
    def __init__(self):
        tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
        tab = next(t for t in tabs if t.get("type") == "page" and "/p/" in t.get("url", ""))
        self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], suppress_origin=True)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                return msg.get("result", {})

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")

    def centre(self, selector):
        return self.js(f"(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();"
                       f" return [r.x + r.width / 2, r.y + r.height / 2]; }})()")

    def touch(self, x, y, to=None, steps=12):
        self.call("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}])
        if to:
            for i in range(1, steps + 1):
                self.call("Input.dispatchTouchEvent", type="touchMove",
                          touchPoints=[{"x": x + (to[0] - x) * i / steps, "y": y + (to[1] - y) * i / steps}])
                time.sleep(0.04)
        self.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])

    def tap(self, selector):
        x, y = self.centre(selector)
        self.touch(x, y)


def main(code: str, photo: Path, name: str):
    OUT.mkdir(exist_ok=True)
    adb(PHONE, "forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    adb(PHONE, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "about:blank", "com.android.chrome")
    time.sleep(2)
    for s in (PHONE, TV):
        adb(s, "shell", "rm", "-f", "/sdcard/clipC.mp4")
    # Phone encoders often refuse the full ~1080x2400 panel (err -38); 720 wide is safe everywhere.
    size = {PHONE: ["--size", "720x1594"], TV: []}
    rec = [subprocess.Popen([ADB, "-s", s, "shell", "screenrecord", "--bit-rate", "12000000", *size[s],
                             "--time-limit", "45", "/sdcard/clipC.mp4"]) for s in (PHONE, TV)]
    time.sleep(1.5)
    adb(PHONE, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d",
        f"http://localhost:8787/p/{code}", "com.android.chrome")
    time.sleep(4)
    page = Page()
    b64 = base64.b64encode(photo.read_bytes()).decode()
    # The tap on "Photograph the drawing" delivers the photo instead of opening the camera.
    page.js("""(() => { window.addEventListener('click', (e) => {
        if (!e.target.closest('#pick')) return;
        e.stopImmediatePropagation(); e.preventDefault();
        const bytes = Uint8Array.from(atob('%s'), c => c.charCodeAt(0));
        const dt = new DataTransfer(); dt.items.add(new File([bytes], 'drawing.png', {type: 'image/png'}));
        const input = document.getElementById('file'); input.files = dt.files;
        input.dispatchEvent(new Event('change', {bubbles: true}));
    }, true); return true; })()""" % b64)
    time.sleep(1.5)
    page.tap("#pick")
    for _ in range(40):  # cut out + rig on the laptop
        if page.js("!document.getElementById('s-check').classList.contains('hidden')"):
            break
        time.sleep(0.25)
    time.sleep(2.5)
    page.tap("#fix summary")
    time.sleep(1)
    page.js("document.getElementById('editor').scrollIntoView({block: 'center', behavior: 'smooth'})")
    time.sleep(1.5)
    # Nudge the right hand dot: the "drag any dot that's off" moment.
    x, y = page.centre(".dot.r:nth-of-type(1)") or (0, 0)
    hand = page.js("""(() => { const d = [...document.querySelectorAll('.dot')].find(d => d.title === 'right_hand'
        || d.dataset.name === 'right_hand') || document.querySelector('.dot.r');
        const r = d.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()""")
    if hand:
        page.touch(hand[0], hand[1], to=(hand[0] - 18, hand[1] - 14))
    time.sleep(1.5)
    page.js("document.getElementById('name').scrollIntoView({block: 'center', behavior: 'smooth'})")
    time.sleep(1.2)
    page.tap("#name")
    time.sleep(0.8)
    for ch in name:  # typed, so it shows up letter by letter
        page.call("Input.insertText", text=ch)
        time.sleep(0.09)
    time.sleep(0.8)
    page.call("Runtime.evaluate", expression="document.activeElement.blur()")
    time.sleep(0.6)
    page.tap("#send")
    time.sleep(7)  # "On the TV now!" + the star walking in on the TV
    # SIGINT lets screenrecord write the MP4 index; killing adb first leaves an unplayable file.
    for s in (PHONE, TV):
        adb(s, "shell", "pkill", "-INT", "screenrecord")
    for p in rec:
        try:
            p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            p.terminate()
    time.sleep(1)
    adb(PHONE, "pull", "/sdcard/clipC.mp4", str(OUT / "phone.mp4"))
    adb(TV, "pull", "/sdcard/clipC.mp4", str(OUT / "phone_tv.mp4"))
    print("DONE", OUT / "phone.mp4", OUT / "phone_tv.mp4")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
