"""Render the Doodle Theater demo video with ffmpeg, following the cut list in video-script.md.

usage:
  python build_video.py                         render final/doodle-theater-demo.mp4
  python build_video.py --phone-in 2 --phone-out 26   use only that part of clips/phone.mp4
  python build_video.py --check [--sheet x.jpg]  report length and loudness of the render
                                                 (and write a contact sheet, a frame every 8 s)
  python build_video.py --preview                write the 720p preview next to the render

needs: ffmpeg + ffprobe on PATH. Python stdlib only.

How it is put together
- Each scene is rendered on its own to a lossless-ish intermediate (exact length, 1920x1080,
  30 fps, 48 kHz stereo PCM), with its captions burnt in. Then one final pass joins them with
  cuts or short crossfades, ducks the app's own narration under the voice-over, mixes the
  voice-over in and encodes H.264 + AAC.
- Voice-over lines are placed relative to the start of their scene, so if clip C (the phone)
  comes out longer or shorter, everything after it moves with it. A line never starts before
  the previous one has finished.
- clips/phone.mp4 is used when it exists and ffprobe can read it: the parts in PHONE_RANGES
  (skipping about:blank, fast-forwarding an idle stretch), with the status bar and URL bar
  cropped off, on the cream background with rounded corners and a drop shadow. --phone-in /
  --phone-out override PHONE_RANGES for a re-take. If the file is missing or unreadable, a
  placeholder card of the planned length (12 s) stands in, so the whole pipeline still runs.
- The phone take shows no joint dots, so Queen Whiskers' skeleton from rig_skeletons.png is
  laid beside the phone for "If a dot is off, you drag it".

Clips (re-recorded 2026-10-21 with the new TV UI; the first takes are kept as clips/*_v1.mp4):
- home_add.mp4: Home, focus over the stars (Selected tag) and themes, then Add a star, the QR, and
  Queen Whiskers arriving. story_sound.mp4: Under the Sea in daytime, through the picture-choice
  cards to the bedtime wind-down and the Goodnight card. bedtime.mp4: Home with Bedtime ON, then a
  bedtime Space Adventure to its wind-down. pause_sound.mp4, party.mp4: as before.
- The wind-down's "The end!" / "Goodnight, <names>." are the TV's own text-to-speech, so record.py
  lays Polly stand-ins (same narrator voice) into story_sound.mp4 and bedtime.mp4 at the measured
  times.

Deliberate departures from the cut list:
- Scene 4 ends on the kelp scene; the wind-down and Goodnight card are shown once, in the bedtime
  scene (6b), where the dimming reads best.
- Scene 6b (bedtime) punches in on the top-right of Home (bedtime.mp4 src 5.0-10.4, a 1280x720
  crop) so the "Bedtime ON" and "Stories tonight" chips are readable while focus visits them.
- Bedtime stories end their last line with "The end!" and the TV then says "The end!" again as
  the lights go down; both are heard (under the voice-over) in scene 6b.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIPS, IMAGES, VO_DIR = HERE / "clips", HERE / "images", HERE / "voiceover"
OUT = HERE / "final" / "doodle-theater-demo.mp4"
PREVIEW = HERE / "final" / "doodle-theater-demo-preview.mp4"
FONT = HERE.parent / "tv" / "app" / "src" / "main" / "res" / "font" / "baloo2.ttf"
PHONE = CLIPS / "phone.mp4"

W, H, FPS = 1920, 1080, 30
CREAM = "0xfbf3e2"          # the app's background
INK = "0x3a2a22"            # dark brown text on cream
DUCK = 0.0                  # app narration is muted under voice-over: never two voices at once
DUCK_PAUSE = 0.0           # scene 5: the voice-over comes first, then the pause is heard alone
MASTER_DB = 6.0             # Polly MP3s sit around -25 dB mean; lift the whole mix a little
PHONE_PLANNED = 12.0        # placeholder length when clip C is missing
PHONE_MAX = 30.0            # with --phone-in/--phone-out: longer phone clips are sped up to fit this
# clips/phone.mp4 (27.4 s, 2026-10-21 take): about:blank until 4.4; step bar on 1 "Photo",
# "Photograph the drawing" tapped 6.8; "Cutting out" 7.8, "Finding elbows and knees" 8.8 (step 2);
# cat preview 9.25; 9.3-11.7 a stray keyboard (the script's "Fix the joints" tap hit the name field)
# - skipped; idle on the moving cat 11.9-17.5; "Queen Whiskers" typed 17.9-19.9; Send ~21.0;
# "Queen Whiskers is on the TV now!" (all three steps ticked) 21.5, static to the end.
PHONE_RANGES = [(4.3, 9.25, 1.0), (11.9, 17.5, 1.5), (17.5, 22.3, 1.0)]  # (in, out, speed)
PHONE_CROP_TOP = 182        # status bar (notification icons) + Chrome URL bar
# clips/phone_fix.mp4 (record_fix.py, 2026-10-22): the picker grid 2.5, Queen Whiskers picked 4.5;
# the pig with only its outline 15.2; brush opened 20, body painted back 22-28, Done 29, rebuilt 30.
PHONE_FIX = CLIPS / "phone_fix.mp4"
FIX_RANGES = [(2.3, 6.6, 1.0), (15.0, 17.2, 1.0), (20.4, 28.4, 3.0), (29.6, 32.8, 1.0)]
CHIPS_CROP = "1280:720:640:0"  # Home's top-right: the Bedtime and Stories-tonight chips


def fr(x: float) -> float:
    """Round a length to whole frames."""
    return round(x * FPS) / FPS


def run(cmd: list[str], cwd: Path | None = None) -> None:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-6000:])
        raise SystemExit(f"ffmpeg failed: {' '.join(cmd[:8])} ...")


def probe(path: Path) -> dict | None:
    p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                        str(path)], capture_output=True, text=True)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- pieces of picture
# A piece is a few ffmpeg inputs plus a filter that turns them into exactly `dur` seconds of
# 1920x1080 yuv420p video at 30 fps, labelled [out].

@dataclass
class Piece:
    dur: float
    inputs: list[list[str]]
    graph: str  # uses {i0}, {i1}... for its inputs and {out} for its output label


def bg_input(dur: float) -> list[str]:
    return ["-f", "lavfi", "-t", f"{dur + 1:.3f}", "-i", f"color=c={CREAM}:s={W}x{H}:r={FPS}"]


TAIL = "setsar=1,format=yuv420p,tpad=stop_mode=clone:stop_duration=3,trim=duration={dur:.4f},setpts=PTS-STARTPTS"


def clip(src: Path, a: float, b: float, speed: float = 1.0, crop: str | None = None) -> Piece:
    dur = fr((b - a) / speed)
    c = f"crop={crop}," if crop else ""
    g = (f"[{{i0}}:v:0]setpts=(PTS-STARTPTS)/{speed},fps={FPS},{c}scale={W}:{H}:flags=lanczos,"
         + TAIL.format(dur=dur) + "[{out}]")
    return Piece(dur, [["-ss", f"{a:.3f}", "-t", f"{b - a + 0.5:.3f}", "-i", str(src)]], g)


def still(img: Path, dur: float, zoom: tuple[float, float] | None = None, fit: str = "cover",
          margin: int = 0) -> Piece:
    dur = fr(dur)
    n = int(round(dur * FPS))
    if fit == "cover":
        sized = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
    else:
        sized = (f"scale={W - 2 * margin}:{H - 2 * margin}:force_original_aspect_ratio=decrease:flags=lanczos")
    if zoom:
        z0, z1 = zoom
        # zoompan works in whole pixels, so zoom on a 3x upscale to keep the move smooth.
        move = (f",scale={W * 3}:{H * 3}:flags=lanczos,zoompan=z='{z0}+{z1 - z0}*on/{n}'"
                f":x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps={FPS}")
    else:
        move = ""
    g = (f"[{{i0}}:v]format=rgba,{sized}[img{{out}}];[{{i1}}:v][img{{out}}]overlay=(W-w)/2:(H-h)/2:shortest=1"
         f"{move}," + TAIL.format(dur=dur) + "[{out}]")
    return Piece(dur, [["-loop", "1", "-framerate", str(FPS), "-t", f"{dur + 1:.3f}", "-i", str(img)],
                       bg_input(dur)], g)


def gif(path: Path, dur: float, size: int = 760) -> Piece:
    dur = fr(dur)
    g = (f"[{{i0}}:v]fps={FPS},format=rgba,scale=-1:{size}:flags=lanczos[g{{out}}];"
         f"[{{i1}}:v][g{{out}}]overlay=(W-w)/2:(H-h)/2:shortest=1," + TAIL.format(dur=dur) + "[{out}]")
    return Piece(dur, [["-ignore_loop", "0", "-t", f"{dur + 1:.3f}", "-i", str(path)], bg_input(dur)], g)


@dataclass
class PhoneLayout:
    pw: int
    ph: int
    px: int
    py: int
    text_x: int
    radius: int = 34
    pad: int = 70  # shadow canvas border


def phone_layout(src_w: int, src_h: int) -> PhoneLayout:
    max_h, max_w = H - 2 * 60, 900
    s = min(max_h / src_h, max_w / src_w)
    pw, ph = int(src_w * s) // 2 * 2, int(src_h * s) // 2 * 2
    cx = int(W * 0.37)
    px, py = cx - pw // 2, (H - ph) // 2
    return PhoneLayout(pw, ph, px, py, text_x=px + pw + 110)


def make_phone_masks(tmp: Path, L: PhoneLayout) -> tuple[Path, Path]:
    """A rounded-rectangle alpha mask for the screen, and a soft drop shadow for under it."""
    def inside(w, h, ox=0, oy=0):
        r = L.radius
        return (f"lte(hypot(max(0,abs(X-{ox}-{(w - 1) / 2})-{w / 2 - r}),"
                f"max(0,abs(Y-{oy}-{(h - 1) / 2})-{h / 2 - r})),{r})")
    mask, shadow = tmp / "phone_mask.png", tmp / "phone_shadow.png"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={L.pw}x{L.ph}", "-frames:v", "1",
         "-vf", f"format=gray,geq=lum='255*{inside(L.pw, L.ph)}'", str(mask)])
    sw, sh = L.pw + 2 * L.pad, L.ph + 2 * L.pad
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={sw}x{sh}", "-frames:v", "1",
         "-vf", f"format=yuva444p,geq=lum=0:cb=128:cr=128:a='95*{inside(L.pw, L.ph, L.pad, L.pad)}',"
                f"boxblur=luma_radius=0:chroma_radius=0:alpha_radius=26:alpha_power=2", str(shadow)])
    return mask, shadow


def phone_piece(tmp: Path, a: float | None, b: float | None, max_len: float,
                path: Path = PHONE, use: list | None = None) -> tuple[Piece, PhoneLayout, str]:
    """A phone clip on a cream frame. Uses `use` (default PHONE_RANGES) unless --phone-in/--phone-out are given."""
    info = probe(path) if path.exists() else None
    vs = [s for s in (info or {}).get("streams", []) if s.get("codec_type") == "video"]
    if vs and float(info["format"].get("duration", 0) or 0) > 1:
        sw, sh = int(vs[0]["width"]), int(vs[0]["height"])
        total = float(info["format"]["duration"])
        if a is not None or b is not None:
            a, b = max(0.0, a or 0.0), min(total, b if b is not None else total)
            ranges = [(a, b, max(1.0, (b - a) / max_len))]
        else:
            ranges = [(ra, min(total, rb if rb is not None else total), sp) for ra, rb, sp in (use or PHONE_RANGES)]
        crop = f"crop={sw}:{sh - PHONE_CROP_TOP}:0:{PHONE_CROP_TOP}," if PHONE_CROP_TOP else ""
        sh -= PHONE_CROP_TOP
        src, parts, dur = [], [], 0.0
        for n, (ra, rb, sp) in enumerate(ranges):
            d = fr((rb - ra) / sp)
            src.append(["-ss", f"{ra:.3f}", "-t", f"{rb - ra + 0.5:.3f}", "-i", str(path)])
            parts.append(f"[{{i{4 + n}}}:v:0]setpts=(PTS-STARTPTS)/{sp},fps={FPS},{crop}setsar=1,"
                         f"tpad=stop_mode=clone:stop_duration=2,trim=duration={d:.4f},setpts=PTS-STARTPTS[r{n}{{out}}]")
            dur += d
        dur = fr(dur)
        head = ";".join(parts) + ";" + "".join(f"[r{n}{{out}}]" for n in range(len(ranges))) +             f"concat=n={len(ranges)}:v=1:a=0"
        note = path.name + " {}x{} (top {} px cropped), ".format(sw, sh + PHONE_CROP_TOP, PHONE_CROP_TOP) +             ", ".join(f"src {ra:.1f}-{rb:.1f} at {sp:g}x" for ra, rb, sp in ranges) + f" -> {dur:.2f} s"
    else:
        sw, sh, dur = 720, 1412, fr(PHONE_PLANNED)
        (tmp / "ph1.txt").write_text("Clip C: phone", encoding="utf-8", newline="\n")
        (tmp / "ph2.txt").write_text("placeholder until\nclips/phone.mp4 exists", encoding="utf-8", newline="\n")
        src = [["-f", "lavfi", "-t", f"{dur + 1:.3f}", "-i", f"color=c=0x2d2733:s={sw}x{sh}:r={FPS}"]]
        head = ("[{i4}:v]drawtext=fontfile=baloo2.ttf:textfile=ph1.txt:expansion=none:fontsize=78"
                ":fontcolor=white:x=(w-text_w)/2:y=h*0.42,drawtext=fontfile=baloo2.ttf:textfile=ph2.txt"
                ":expansion=none:fontsize=40:line_spacing=10:fontcolor=0xbfb6c8:x=(w-text_w)/2:y=h*0.52")
        note = ("phone.mp4 present but unreadable (still recording?) -> placeholder card" if PHONE.exists()
                else "phone.mp4 missing -> placeholder card")
    L = phone_layout(sw, sh)
    mask, shadow = make_phone_masks(tmp, L)
    g = (f"{head},scale={L.pw}:{L.ph}:flags=lanczos,format=rgba,tpad=stop_mode=clone:stop_duration=3[ps{{out}}];"
         f"[{{i2}}:v]format=gray[mk{{out}}];[ps{{out}}][mk{{out}}]alphamerge[pa{{out}}];"
         f"[{{i1}}:v][{{i3}}:v]overlay={L.px - L.pad + 6}:{L.py - L.pad + 14}[b{{out}}];"
         f"[b{{out}}][pa{{out}}]overlay={L.px}:{L.py}:eof_action=repeat," + TAIL.format(dur=dur) + "[{out}]")
    inputs = [[], bg_input(dur),
              ["-loop", "1", "-t", f"{dur + 1:.3f}", "-i", str(mask)],
              ["-loop", "1", "-t", f"{dur + 1:.3f}", "-i", str(shadow)]] + src
    return Piece(dur, inputs, g), L, note


# --------------------------------------------------------------------------- scenes

@dataclass
class Cap:
    text: str
    a: float
    b: float
    style: str = "bar"   # bar | title | side | note
    x: int | None = None   # side/note position; default is the scene's side_x/side_y
    y: str | None = None


@dataclass
class Scene:
    name: str
    pieces: list[Piece]
    audio: list[tuple[Path, float, float]] | None = None   # app sound; None = silent
    vo: list[tuple[str, float]] = field(default_factory=list)  # (file stem, offset in scene)
    caps: list[Cap] = field(default_factory=list)
    xfade: float = 0.0   # crossfade from the previous scene (0 = cut)
    duck: float = DUCK
    side_x: int = 0
    side_y: str = "(h-text_h)/2"
    # pictures laid over the scene: (image, from, to, x, y, height, crop or None)
    overlays: list[tuple[Path, float, float, int, int, int, str | None]] = field(default_factory=list)

    @property
    def dur(self) -> float:
        return fr(sum(p.dur for p in self.pieces))


def caption_filter(c: Cap, textfile: str, side_x: int, side_y: str) -> str:
    fade = 0.3
    alpha = (f"if(lt(t,{c.a + fade}),(t-{c.a})/{fade},if(gt(t,{c.b - fade}),({c.b}-t)/{fade},1))")
    base = (f"drawtext=fontfile=baloo2.ttf:textfile={textfile}:expansion=none:"
            f"enable='between(t,{c.a},{c.b})':alpha='{alpha}':")
    if c.style == "title":
        return base + (f"fontsize=104:fontcolor={INK}:box=1:boxcolor={CREAM}@0.93:boxborderw=26|64|18|64:"
                       f"x=(w-text_w)/2:y=h-text_h-120")
    if c.style == "note":
        return base + f"fontsize=46:line_spacing=-8:fontcolor={INK}:x={side_x}:y={side_y}"
    if c.style == "side":
        return base + f"fontsize=66:line_spacing=-12:fontcolor={INK}:x={side_x}:y={side_y}"
    return base + ("fontsize=46:fontcolor=white:box=1:boxcolor=0x2a2030@0.74:boxborderw=18|36|14|36:"
                   "x=(w-text_w)/2:y=h-text_h-70")


def render_scene(idx: int, sc: Scene, tmp: Path) -> Path:
    out = tmp / f"scene{idx:02d}.mkv"
    args: list[str] = ["ffmpeg", "-y", "-v", "error"]
    graph: list[str] = []
    k = 0
    labels = []
    for j, p in enumerate(sc.pieces):
        ids = {}
        for n, inp in enumerate(p.inputs):
            if not inp:  # unused slot
                continue
            args += inp
            ids[f"i{n}"] = k
            k += 1
        lbl = f"p{j}"
        graph.append(p.graph.replace("{out}", lbl).format(**ids))
        labels.append(f"[{lbl}]")
    v = "[vcat]"
    if len(labels) > 1:
        graph.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0{v}")
    else:
        v = labels[0]
    caps = []
    for n, c in enumerate(sc.caps):
        name = f"cap{idx:02d}_{n}"
        (tmp / f"{name}.txt").write_text(c.text, encoding="utf-8", newline="\n")  # CRLF draws as extra lines
        x, y = (c.x, c.y) if c.x is not None else (sc.side_x, sc.side_y)
        caps.append(caption_filter(c, f"{name}.txt", x, y))
    for n, (img, a, b, x, y, h, crop) in enumerate(sc.overlays):
        args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{sc.dur + 1:.3f}", "-i", str(img)]
        c = f"crop={crop}," if crop else ""
        graph.append(f"[{k}:v]format=rgba,{c}scale=-1:{h}:flags=lanczos,"
                     f"fade=t=in:st={a}:d=0.35:alpha=1,fade=t=out:st={b - 0.3:.3f}:d=0.3:alpha=1[ov{n}]")
        graph.append(f"{v}[ov{n}]overlay={x}:{y}:enable='between(t,{a},{b})'[vo{n}]")
        v = f"[vo{n}]"
        k += 1
    graph.append(f"{v}{','.join(caps) if caps else 'null'}[vout]")

    # app sound: pieces of the clips' own audio, or silence
    dur = sc.dur
    alabels = []
    for j, (src, a, b) in enumerate(sc.audio or []):
        args += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src)]
        graph.append(f"[{k}:a:0]aresample=48000,pan=stereo|c0=c0|c1=c0,apad,atrim=duration={b - a:.4f},"
                     f"asetpts=PTS-STARTPTS[a{j}]")
        alabels.append(f"[a{j}]")
        k += 1
    if not alabels:
        args += ["-f", "lavfi", "-t", f"{dur + 1:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        alabels = [f"[{k}:a]"]
        k += 1
    graph.append("".join(alabels) + (f"concat=n={len(alabels)}:v=0:a=1," if len(alabels) > 1 else "")
                 + f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,apad,"
                   f"atrim=duration={dur:.4f}[aout]")
    args += ["-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]",
             "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "pcm_s16le", "-ar", "48000", "-t", f"{dur:.4f}", str(out)]
    run(args, cwd=tmp)
    return out


def build_scenes(tmp: Path, phone_in, phone_out, phone_max) -> tuple[list[Scene], str]:
    home, party = CLIPS / "home_add.mp4", CLIPS / "party.mp4"
    story, pause = CLIPS / "story_sound.mp4", CLIPS / "pause_sound.mp4"
    bed = CLIPS / "bedtime.mp4"
    ph, L, note = phone_piece(tmp, phone_in, phone_out, phone_max)
    fx, LF, _ = phone_piece(tmp, None, None, PHONE_MAX, path=PHONE_FIX, use=FIX_RANGES)
    scenes = [
        Scene("1 hook: the drawings", [still(IMAGES / "drawings_photo.webp", 7.5, zoom=(1.0, 1.12))],
              vo=[("1_hook", 0.5)], caps=[Cap("Doodle Theater", 0.5, 6.2, "title")]),
        # home_add: focus over the stars ("Selected") 2.5-7, the themes 7.5-11; back to Add a star
        # 12-18 (sped up 3x); Add a star opens 19.5, QR 20.5.
        Scene("2+3a home screen, Add a star + QR",
              [clip(home, 1.5, 12.0), clip(home, 12.0, 18.0, speed=3.0), clip(home, 18.0, 23.0)],
              vo=[("2_idea", 0.5)], xfade=0.5),
        # 3a_add starts 1.8 s before the phone, so "scans the code on the TV" is over the QR,
        # "cuts the character out" over the spinner, and "If a dot is off, you drag it" (VO 9.9 s)
        # over Queen Whiskers' joint dots from rig_skeletons.png (the phone take shows no dots).
        Scene("3C phone", [ph], vo=[("3a_add", -1.8)], xfade=0.3, side_x=L.text_x, side_y="200",
              caps=[Cap("Phone: no app,\njust the camera\nand a QR code", 0.4, ph.dur - 0.3, "side"),
                    Cap("Joint dots found\nby doodle-rig.\nOne off? Drag it.", 7.7, ph.dur - 0.3, "note",
                        x=L.text_x + 380, y="640")],
              overlays=[(IMAGES / "rig_skeletons.png", 7.7, ph.dur - 0.3, L.text_x - 20, 540, 420,
                         "320:400:0:0")]),
        # "Press send, and..." then "...Queen Whiskers walks on stage" as "Queen Whiskers has
        # arrived!" pops up (home_add src 30.4) and she walks in (to ~34), then waves.
        Scene("3b Queen Whiskers arrives", [clip(home, 28.7, 38.2)], vo=[("3b_send", -0.3)],
              caps=[Cap("Photo to puppet in seconds, animated live on the TV", 2.0, 9.2)], xfade=0.3),
        # A page of drawings -> tap one; then a drawing whose cut-out lost its body, painted back.
        Scene("3c pick a drawing, fix the cut-out", [fx], vo=[("3c_fix", 0.3)], xfade=0.3,
              side_x=LF.text_x, side_y="200",
              caps=[Cap("Lots of drawings?\nTap your star.", 0.3, 4.4, "side"),
                    Cap("Cut-out missed\na bit? Paint it\nback with Add.", 4.6, fx.dur - 0.3, "side"),
                    Cap("Pig: test drawing from\nMeta AnimatedDrawings (MIT)", 6.7, fx.dur - 0.3, "note",
                        x=LF.text_x, y="820")]),
        # story_sound: title 12.3, narration from 13.0, "What should they do?" with the picture
        # cards 32.3, focus moves to "Swim through the kelp" 36.0, kelp scene 38.0.
        Scene("4 tonight's story", [clip(story, 12.1, 42.5)], audio=[(story, 12.1, 42.5)],
              vo=[("4_story", 10.1)],
              caps=[Cap("Polly neural voices · word speech marks · picture choices on the D-pad", 10.5, 19.8)]),
        # pause_sound: "Look! A little star..." from 23.0, Paused 23.33, resumed 26.42.
        # Voice-over first (over the opening line), then the narration alone: "Look!" stops at the
        # pause and picks up again, so the viewer hears the pause rather than two voices at once.
        Scene("5 pause / resume", [clip(pause, 15.8, 29.5)], audio=[(pause, 15.8, 29.5)],
              vo=[("5_pause", 0.1)], duck=DUCK_PAUSE,
              caps=[Cap('Emulator: "Alexa, pause" sent as a media-session pause command', 7.2, 13.5)]),
        # party: tricks with the spotlight + "Now dancing" tag, everybody dances from ~23.
        Scene("6 dance party", [clip(party, 18.5, 29.95)], vo=[("6_dance", 2.2)]),
        # bedtime: Home with Bedtime ON, focus on Bolt (3-5), then a punch-in on the chips while
        # focus visits "Stories tonight" (5.3-7.5) and "Bedtime ON" (7.8-10.3); then the end of the
        # bedtime story: "...a big, sleepy yawn. The end!", the wind-down from 81.0 (stars wave,
        # stage dims, moon), "The end!" 81.4, "Goodnight, Queen Whiskers, ..." 83.8-89.0 (after the
        # voice-over), the Goodnight card 90.6.
        Scene("6b bedtime", [clip(bed, 3.0, 5.0), clip(bed, 5.0, 10.4, crop=CHIPS_CROP), clip(bed, 79.3, 93.0)],
              audio=[(bed, 3.0, 10.4), (bed, 79.3, 93.0)], vo=[("6b_bedtime", 0.4)], xfade=0.3,
              caps=[Cap("Bedtime mode · goodnight wind-down · stories-tonight limit", 0.6, 11.4)]),
        # 7b_honest starts on the diagram ("Our new AWS account was still waiting...") and the demo
        # footage comes in for "...so this demo plays from our hand-written story set".
        Scene("7a diagram", [still(IMAGES / "diagram.png", 14.6, zoom=(1.0, 1.06))],
              vo=[("7a_built", 0.4), ("7b_honest", 11.0)], xfade=0.4),
        Scene("7b demo story (muted)", [clip(story, 42.5, 51.5)], xfade=0.3,
              caps=[Cap("Demo stories: hand-written offline set, narrated by Amazon Polly", 0.3, 8.7)]),
        Scene("7c rig skeletons", [still(IMAGES / "rig_skeletons.png", 3.6, fit="contain", margin=80)],
              vo=[("7c_open", 0.5)], xfade=0.3),
        Scene("7c cat walk", [gif(IMAGES / "cat_walk.gif", 3.2)], xfade=0.3),
        Scene("8 end card", [still(IMAGES / "endcard.png", 8.5)], vo=[("8_close", 0.5)], xfade=0.5),
    ]
    return scenes, note


def build(phone_in=None, phone_out=None, phone_max=PHONE_MAX) -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not on PATH")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="doodle_video_") as t:
        tmp = Path(t)
        shutil.copy(FONT, tmp / "baloo2.ttf")
        scenes, note = build_scenes(tmp, phone_in, phone_out, phone_max)
        print("clip C:", note)

        # timeline
        starts, cur = [], 0.0
        for i, sc in enumerate(scenes):
            start = 0.0 if i == 0 else cur - sc.xfade
            starts.append(start)
            cur = start + sc.dur
        total = fr(cur)

        vo_events, prev_end = [], -1.0
        for sc, st in zip(scenes, starts):
            for stem, off in sc.vo:
                f = VO_DIR / f"{stem}.mp3"
                d = float(probe(f)["format"]["duration"])
                t0 = max(st + off, prev_end + 0.25)
                vo_events.append((stem, f, t0, d, sc.duck))
                prev_end = t0 + d
        if prev_end > total - 1.5:
            raise SystemExit(f"voice-over runs to {prev_end:.1f}s, past the end card ({total:.1f}s)")

        files = []
        for i, sc in enumerate(scenes):
            print(f"  {starts[i]:7.2f}s  {sc.dur:6.2f}s  {sc.name}")
            files.append(render_scene(i, sc, tmp))
        for stem, _, t0, d, g in vo_events:
            print(f"  VO {stem:10s} {t0:7.2f} -> {t0 + d:7.2f}   (app sound x{g})")

        args = ["ffmpeg", "-y", "-v", "error"]
        for f in files:
            args += ["-i", str(f)]
        for _, f, *_ in vo_events:
            args += ["-i", str(f)]
        g = []
        for i in range(len(files)):
            g.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={FPS},format=yuv420p[v{i}]")
            g.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
        cv, ca, length = "v0", "a0", scenes[0].dur
        for i in range(1, len(files)):
            d = scenes[i].xfade
            if d > 0:
                g.append(f"[{cv}][v{i}]xfade=transition=fade:duration={d}:offset={length - d:.4f}[vx{i}]")
                g.append(f"[{ca}][a{i}]acrossfade=d={d}:c1=tri:c2=tri[ax{i}]")
                length += scenes[i].dur - d
            else:
                g.append(f"[{cv}][{ca}][v{i}][a{i}]concat=n=2:v=1:a=1[vc{i}][ax{i}]")
                g.append(f"[vc{i}]settb=1/{FPS}[vx{i}]")  # xfade needs matching timebases
                length += scenes[i].dur
            cv, ca = f"vx{i}", f"ax{i}"
        g.append(f"[{cv}]fade=t=in:st=0:d=0.6,fade=t=out:st={total - 1:.3f}:d=1,format=yuv420p[vout]")

        # duck the app narration while any voice-over line plays (0.25 s in, 0.4 s out)
        terms = []
        for _, _, t0, d, gain in vo_events:
            a, b = t0, t0 + d
            terms.append(f"(1-{1 - gain:.3f}*clip(min((t-{a - 0.25:.3f})/0.25,({b + 0.4:.3f}-t)/0.4),0,1))")
        expr = terms[0]
        for t_ in terms[1:]:
            expr = f"min({expr},{t_})"
        g.append(f"[{ca}]volume=eval=frame:volume='{expr}'[duck]")
        mix = ["[duck]"]
        base = len(files)
        for n, (_, _, t0, _, _) in enumerate(vo_events):
            g.append(f"[{base + n}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
                     f"adelay=delays={int(round(t0 * 1000))}:all=1[vo{n}]")
            mix.append(f"[vo{n}]")
        g.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first:dropout_transition=0,"
                 f"volume={MASTER_DB}dB,afade=t=out:st={total - 1:.3f}:d=1,"
                 f"alimiter=limit=0.84:level=0,atrim=duration={total:.4f}[aout]")
        args += ["-filter_complex", ";".join(g), "-map", "[vout]", "-map", "[aout]",
                 "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
                 "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                 "-movflags", "+faststart", "-t", f"{total:.4f}", str(OUT)]
        print("final pass ...")
        run(args, cwd=tmp)
    print(f"wrote {OUT}  ({total:.2f} s = {int(total // 60)}:{total % 60:04.1f})")


def preview() -> None:
    """A 720p copy of the render for quick sharing (aim: under 25 MB)."""
    run(["ffmpeg", "-y", "-v", "error", "-i", str(OUT), "-vf", "scale=1280:720:flags=lanczos",
         "-c:v", "libx264", "-preset", "slow", "-crf", "25", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(PREVIEW)])
    print(f"wrote {PREVIEW}  ({PREVIEW.stat().st_size / 1e6:.1f} MB)")


def check(sheet: Path | None) -> None:
    info = probe(OUT)
    if not info:
        raise SystemExit(f"cannot read {OUT}")
    dur = float(info["format"]["duration"])
    print(f"{OUT}\n  duration {dur:.2f} s ({'OK' if dur < 180 else 'TOO LONG'})")
    for s in info["streams"]:
        print("  ", s["codec_type"], s["codec_name"], s.get("width", ""), s.get("height", ""),
              s.get("r_frame_rate", ""), s.get("sample_rate", ""), s.get("bit_rate", ""))
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(OUT), "-vn", "-af",
                        "volumedetect,silencedetect=n=-45dB:d=2", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in p.stderr.splitlines():
        if any(k in line for k in ("max_volume", "mean_volume", "silence_start", "silence_end")):
            print("  ", line.split("]", 1)[-1].strip())
    if sheet:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(OUT), "-vf",
             "select='isnan(prev_selected_t)+gte(t-prev_selected_t,8)',scale=384:-1,drawtext=fontfile=baloo2.ttf:text='%{pts\\:hms}':x=6:y=6:fontsize=22"
             ":fontcolor=white:box=1:boxcolor=black@0.6,tile=5x4:padding=4", "-frames:v", "1", str(sheet)],
            cwd=FONT.parent)
        print("  contact sheet:", sheet)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone-in", type=float, help="start of the usable part of clips/phone.mp4 (s)")
    ap.add_argument("--phone-out", type=float, help="end of the usable part of clips/phone.mp4 (s)")
    ap.add_argument("--phone-max", type=float, default=PHONE_MAX,
                    help=f"longest the phone part may run; longer is sped up (default {PHONE_MAX:g})")
    ap.add_argument("--check", action="store_true", help="only report on the existing render")
    ap.add_argument("--sheet", type=Path, help="with --check: write a contact sheet here")
    ap.add_argument("--preview", action="store_true", help="only write the 720p preview of the render")
    a = ap.parse_args()
    if a.preview:
        preview()
    elif a.check:
        check(a.sheet)
    else:
        build(a.phone_in, a.phone_out, a.phone_max)
