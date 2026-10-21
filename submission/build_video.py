"""Render the Doodle Theater demo video with ffmpeg, following the cut list in video-script.md.

usage:
  python build_video.py                         render final/doodle-theater-demo.mp4
  python build_video.py --phone-in 2 --phone-out 26   use only that part of clips/phone.mp4
  python build_video.py --check [--sheet x.jpg]  report length and loudness of the render
                                                 (and write a contact sheet, a frame every 8 s)

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

Deliberate departures from the cut list, to keep known glitches off screen:
- Scene 4b: the story's last scene has two name labels on top of each other ("Queen Whis" under
  "Professor Noodles"), so the "The End" screen is shown cropped to the title and buttons, and
  "The end!" is heard over the last moment of the kelp scene just before the cut.
- Scene 7b: the same overlap starts at story src 44.8, so the footage under "this demo plays
  from our hand-written story set" is the opening of the space story (pause_sound 18.4-21.5)
  and the start of the sea story's turtle line (42.6-44.7), slowed to 0.65x, instead of story
  41.8-50.9. The diagram stays up for the first part of that line to cover the shorter footage.
- The End screen is fully up at story src 53.0 (the cut list says 52.1, which is when "The
  end!" finishes being spoken).
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
FONT = HERE.parent / "tv" / "app" / "src" / "main" / "res" / "font" / "baloo2.ttf"
PHONE = CLIPS / "phone.mp4"

W, H, FPS = 1920, 1080, 30
CREAM = "0xfbf3e2"          # the app's background
INK = "0x3a2a22"            # dark brown text on cream
DUCK = 0.2                  # app narration under voice-over: 0.2 = -14 dB
DUCK_PAUSE = 0.35           # scene 5: keep the pause audible (cut list says 35%)
MASTER_DB = 6.0             # Polly MP3s sit around -25 dB mean; lift the whole mix a little
PHONE_PLANNED = 12.0        # placeholder length when clip C is missing
PHONE_MAX = 30.0            # with --phone-in/--phone-out: longer phone clips are sped up to fit this
# clips/phone.mp4 (22.4 s): 0-1.5 about:blank; "Photograph the drawing" to ~7.2; "Cutting out" spinner
# ~7.5; cat preview ~10; name field focused ~12.5; idle (keyboard closed) ~13-17.3; "Queen Whiskers"
# typed 17.5-20.5; Send ~21.9; "Queen Whiskers is on the TV now!" ~22.2.
PHONE_RANGES = [(5.0, 13.0, 1.0), (13.0, 17.3, 4.0), (17.3, None, 1.0)]  # (in, out, speed)
PHONE_CROP_TOP = 182        # status bar (notification icons) + Chrome URL bar
END_CROP = "860:484:530:0"  # "The End" title + buttons, without the overlapping name labels


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


def phone_piece(tmp: Path, a: float | None, b: float | None, max_len: float) -> tuple[Piece, PhoneLayout, str]:
    """Clip C on a cream frame. Uses PHONE_RANGES unless --phone-in/--phone-out are given."""
    info = probe(PHONE) if PHONE.exists() else None
    vs = [s for s in (info or {}).get("streams", []) if s.get("codec_type") == "video"]
    if vs and float(info["format"].get("duration", 0) or 0) > 1:
        sw, sh = int(vs[0]["width"]), int(vs[0]["height"])
        total = float(info["format"]["duration"])
        if a is not None or b is not None:
            a, b = max(0.0, a or 0.0), min(total, b if b is not None else total)
            ranges = [(a, b, max(1.0, (b - a) / max_len))]
        else:
            ranges = [(ra, min(total, rb if rb is not None else total), sp) for ra, rb, sp in PHONE_RANGES]
        crop = f"crop={sw}:{sh - PHONE_CROP_TOP}:0:{PHONE_CROP_TOP}," if PHONE_CROP_TOP else ""
        sh -= PHONE_CROP_TOP
        src, parts, dur = [], [], 0.0
        for n, (ra, rb, sp) in enumerate(ranges):
            d = fr((rb - ra) / sp)
            src.append(["-ss", f"{ra:.3f}", "-t", f"{rb - ra + 0.5:.3f}", "-i", str(PHONE)])
            parts.append(f"[{{i{4 + n}}}:v:0]setpts=(PTS-STARTPTS)/{sp},fps={FPS},{crop}setsar=1,"
                         f"tpad=stop_mode=clone:stop_duration=2,trim=duration={d:.4f},setpts=PTS-STARTPTS[r{n}{{out}}]")
            dur += d
        dur = fr(dur)
        head = ";".join(parts) + ";" + "".join(f"[r{n}{{out}}]" for n in range(len(ranges))) +             f"concat=n={len(ranges)}:v=1:a=0"
        note = "phone.mp4 {}x{} (top {} px cropped), ".format(sw, sh + PHONE_CROP_TOP, PHONE_CROP_TOP) +             ", ".join(f"src {ra:.1f}-{rb:.1f} at {sp:g}x" for ra, rb, sp in ranges) + f" -> {dur:.2f} s"
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
    ph, L, note = phone_piece(tmp, phone_in, phone_out, phone_max)
    scenes = [
        Scene("1 hook: the drawings", [still(IMAGES / "drawings_photo.webp", 7.5, zoom=(1.0, 1.12))],
              vo=[("1_hook", 0.5)], caps=[Cap("Doodle Theater", 0.5, 6.2, "title")]),
        Scene("2+3a home screen, Add a star + QR", [clip(home, 0.0, 18.0)],
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
        # "Press send, and..." over the phone's Send tap; "...Queen Whiskers walks on stage" as she
        # arrives (home_add src 24.2).
        Scene("3b Queen Whiskers arrives", [clip(home, 22.5, 32.0)], vo=[("3b_send", -0.3)],
              caps=[Cap("Photo to puppet in seconds, animated live on the TV", 2.0, 9.0)], xfade=0.3),
        # 4a + 4b. "The end!" (story src 51.55-52.09) plays over the end of the kelp scene, then a
        # hard cut to the cropped "The End" screen, so the overlapping labels never show. (The End
        # screen is fully up at src 53.0, not 52.1 as the cut list says; before that the text bubble
        # is still on screen and the crop would show a giant slice of it.)
        Scene("4 tonight's story", [clip(story, 12.5, 42.6), clip(story, 53.05, 56.35, crop=END_CROP)],
              audio=[(story, 12.5, 41.8), (story, 51.3, 55.4)], vo=[("4_story", 10.1)],
              caps=[Cap("Polly neural voices · word speech marks · D-pad choices", 10.5, 19.5)]),
        Scene("5 pause / resume", [clip(pause, 21.5, 29.6)], audio=[(pause, 21.5, 29.6)],
              vo=[("5_pause", 1.7)], duck=DUCK_PAUSE,
              caps=[Cap('Emulator: "Alexa, pause" sent as a media-session pause command', 1.7, 8.0)]),
        Scene("6 dance party", [clip(party, 18.5, 29.9)], vo=[("6_dance", 2.2)]),
        # 7b_honest starts on the diagram ("Our new AWS account was still waiting...") and the demo
        # footage comes in for "...so this demo plays from our hand-written story set". Only ~5 s of
        # clean, unused story footage exists: the sea story's labels overlap from src 44.8 on, and
        # the space story's from its walk-in until 18.4.
        Scene("7a diagram", [still(IMAGES / "diagram.png", 14.6, zoom=(1.0, 1.06))],
              vo=[("7a_built", 0.4), ("7b_honest", 11.0)], xfade=0.4),
        Scene("7b demo stories (muted, slowed)", [clip(pause, 18.4, 21.5, speed=0.65),
                                                  clip(story, 42.6, 44.7, speed=0.65)], xfade=0.3,
              caps=[Cap("Demo stories: hand-written offline set, narrated by Amazon Polly", 0.3, 7.7)]),
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
    a = ap.parse_args()
    if a.check:
        check(a.sheet)
    else:
        build(a.phone_in, a.phone_out, a.phone_max)
