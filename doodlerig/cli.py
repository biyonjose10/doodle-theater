"""`doodlerig PHOTO -o OUT_DIR` : photo of a drawing -> rig.json + texture.png (+ previews)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

from .rig import build_rig


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="doodlerig", description=__doc__)
    ap.add_argument("photo", help="photo or scan of the drawing")
    ap.add_argument("-o", "--out", required=True, help="output directory")
    ap.add_argument("--cropped", action="store_true", help="the image is already cropped to the character")
    ap.add_argument("--joints", help="JSON file of {name: [x, y]} in crop coordinates (skips the guess)")
    ap.add_argument("--preview", action="store_true", help="also write overlay.png, motions.png and walk.gif")
    args = ap.parse_args(argv)

    joints = None
    if args.joints:
        joints = {k: tuple(v) for k, v in json.loads(Path(args.joints).read_text()).items()}
    try:
        rig = build_rig(args.photo, joints=joints, already_cropped=args.cropped)
    except ValueError as e:
        print(f"doodlerig: {e}", file=sys.stderr)
        return 2
    path = rig.save(args.out)
    print(f"{path}  ({len(rig.vertices)} vertices, {len(rig.triangles)} triangles)")
    if args.preview:
        from .render import contact_sheet, gif, overlay
        out = Path(args.out)
        Image.fromarray(overlay(rig)).save(out / "overlay.png")
        Image.fromarray(contact_sheet(rig)).save(out / "motions.png")
        gif(rig, "walk", out / "walk.gif")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
