"""Record clip C2: the phone's "pick your character" grid, then the "fix the cut-out" brush.

Part 1 sends a photo of several drawings and taps one in the picker. Part 2 sends a drawing whose
outline has a gap (the cut-out keeps only the outline and loses the body), paints the body back
with Add, and taps Done so the puppet is rebuilt. Photos reach the page through Chrome's remote
debugging, as in record_phone.py; every other step is a real touch on the real page.

usage: python record_fix.py <PAIR_CODE> <several_drawings.webp> <cat_index> <gap_drawing.png>
needs: the phone on adb, `adb reverse tcp:8787 tcp:8787`, websocket-client
Prints when each part starts (seconds into the recording) for the cut list.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import sys
import time
from pathlib import Path

from record_phone import ADB, OUT, PHONE, Page, adb

os.environ["MSYS_NO_PATHCONV"] = "1"
REMOTE = "/sdcard/clipC2.mp4"

HOOK = """(() => { window.addEventListener('click', (e) => {
    if (!e.target.closest('#pick') || !window.__photo) return;
    e.stopImmediatePropagation(); e.preventDefault();
    const [type, b64] = window.__photo;
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const dt = new DataTransfer(); dt.items.add(new File([bytes], 'drawing', {type}));
    const input = document.getElementById('file'); input.files = dt.files;
    input.dispatchEvent(new Event('change', {bubbles: true}));
}, true); return true; })()"""

# Strokes over the pig's body, in fractions of the brush canvas (x0, y, x1): inside the outline only.
BODY = [(0.20, 0.30, 0.52), (0.14, 0.40, 0.58), (0.14, 0.50, 0.58), (0.18, 0.60, 0.56)]


def photo_js(path: Path) -> str:
    kind = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"window.__photo = {json.dumps([kind, base64.b64encode(path.read_bytes()).decode()])}; true"


def visible(page: Page, sid: str) -> bool:
    return bool(page.js(f"!document.getElementById('{sid}').classList.contains('hidden')"))


def wait_for(page: Page, sid: str, timeout: float = 20) -> None:
    end = time.time() + timeout
    while time.time() < end and not visible(page, sid):
        time.sleep(0.2)


def scroll_to(page: Page, selector: str, block: str = "center") -> None:
    page.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: '{block}', behavior: 'smooth'}})")


def main(code: str, sheet: Path, cat: int, gap: Path) -> None:
    OUT.mkdir(exist_ok=True)
    url = f"http://localhost:8787/p/{code}"
    adb(PHONE, "forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    adb(PHONE, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, "com.android.chrome")
    time.sleep(4)
    page = Page()
    page.js(HOOK)
    page.js(photo_js(sheet))
    adb(PHONE, "shell", "rm", "-f", REMOTE)
    rec = subprocess.Popen([ADB, "-s", PHONE, "shell", "screenrecord", "--bit-rate", "12000000",
                            "--size", "720x1594", "--time-limit", "90", REMOTE])
    t0 = time.time()
    time.sleep(1.5)

    # Part 1: several drawings -> the picker -> tap one.
    print(f"PART1 {time.time() - t0:.1f}")
    page.tap("#pick")
    wait_for(page, "s-pick")
    time.sleep(2.2)
    page.tap(f"#grid > :nth-child({cat})")
    wait_for(page, "s-check")
    time.sleep(4)
    print(f"PART1_END {time.time() - t0:.1f}")

    # Part 2: a fresh page and a drawing whose cut-out lost its body.
    page.call("Page.reload")
    time.sleep(3)
    page = Page()
    page.js(HOOK)
    page.js(photo_js(gap))
    time.sleep(0.5)
    print(f"PART2 {time.time() - t0:.1f}")
    page.tap("#pick")
    wait_for(page, "s-check")
    time.sleep(2.5)  # the puppet with only its outline: the body is missing
    scroll_to(page, "#cut", "start")
    time.sleep(1.2)
    page.tap("#cut summary")
    time.sleep(0.8)
    scroll_to(page, "#brush")
    time.sleep(1.5)
    page.tap("#b-add")
    time.sleep(0.4)
    page.tap('.tool.size[data-size="0.11"]')
    time.sleep(0.6)
    rect = page.js("(() => { const r = document.getElementById('brush').getBoundingClientRect();"
                   " return [r.x, r.y, r.width, r.height]; })()")
    x, y, w, h = rect
    for x0, yy, x1 in BODY:
        page.touch(x + x0 * w, y + yy * h, to=(x + x1 * w, y + yy * h), steps=16)
        time.sleep(0.35)
    time.sleep(1.2)
    print(f"DONE_TAP {time.time() - t0:.1f}")
    page.tap("#cut-done")
    end = time.time() + 20
    while time.time() < end and page.js("document.getElementById('cut-done').textContent.includes('Fixing')"):
        time.sleep(0.2)
    time.sleep(5)  # the rebuilt puppet moving in the preview
    print(f"PART2_END {time.time() - t0:.1f}")

    adb(PHONE, "shell", "pkill", "-INT", "screenrecord")
    try:
        rec.wait(timeout=15)
    except subprocess.TimeoutExpired:
        rec.terminate()
    time.sleep(1)
    adb(PHONE, "pull", REMOTE, str(OUT / "phone_fix.mp4"))
    print("SAVED", OUT / "phone_fix.mp4")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
