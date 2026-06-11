#!/usr/bin/env python3
"""Export a Pixy sprite sheet to an engine-native format.

Usage:
    export_engine.py walk_sheet.json --engine aseprite --out walk.json
    export_engine.py walk_sheet.json --engine css --out walk.html

Stdlib only. Reads the <name>_sheet.json that animate.py writes (frame
rectangles + fps) and emits:
  - aseprite : Aseprite-style sheet JSON (frames + meta + a frameTags loop),
  - godot    : a Godot 4 SpriteFrames .tres (AtlasTextures over the sheet;
               one animation per direction when the sheet carries them),
               read by many importers and tools.
  - css      : a self-contained HTML page that plays the sheet with a CSS
               steps() animation - a zero-dependency web preview/embed.

For Unity and Godot, slice the sheet by the cell size from the JSON
(frame_width x frame_height); see references/engine-targets.md.

Exit codes: 0 = written, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_sheet(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: sheet json not found: {path}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"error: invalid sheet json: {e}", file=sys.stderr)
        return None
    for k in ("frame_width", "frame_height", "count", "fps", "frames"):
        if k not in data:
            print(f"error: sheet json missing '{k}'", file=sys.stderr)
            return None
    return data


def to_aseprite(sheet, sheet_png_name):
    fps = sheet["fps"]
    dur = max(1, round(1000 / fps))
    frames = {}
    for f in sheet["frames"]:
        frames[f"frame {f['index']}"] = {
            "frame": {"x": f["x"], "y": f["y"], "w": f["w"], "h": f["h"]},
            "rotated": False, "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": f["w"], "h": f["h"]},
            "sourceSize": {"w": f["w"], "h": f["h"]},
            "duration": dur,
        }
    return {
        "frames": frames,
        "meta": {
            "app": "pixy-the-pixel-art", "version": "1.0",
            "image": sheet_png_name,
            "format": "RGBA8888",
            "size": {"w": sheet["frame_width"] * sheet["columns"],
                     "h": sheet["frame_height"] * sheet["rows"]},
            "scale": "1",
            "frameTags": [{"name": "loop", "from": 0,
                           "to": sheet["count"] - 1, "direction": "forward"}],
        },
    }


def to_godot(sheet, sheet_png_name):
    """Godot 4 SpriteFrames resource: drop the .tres next to the sheet PNG,
    point an AnimatedSprite2D at it. One animation per direction row when
    the sheet json carries 'directions'; else a single 'default' loop."""
    fps = sheet["fps"]
    dirs = sheet.get("directions")
    frames = sheet["frames"]
    lines = []
    sub_ids = []
    for i, f in enumerate(frames):
        sid = f"Atlas_{i}"
        sub_ids.append(sid)
        lines.append(f'[sub_resource type="AtlasTexture" id="{sid}"]')
        lines.append('atlas = ExtResource("1")')
        lines.append(f'region = Rect2({f["x"]}, {f["y"]}, {f["w"]}, '
                     f'{f["h"]})')
        lines.append("")
    if dirs:
        per = len(frames) // max(1, len(dirs))
        anims = [(d, list(range(i * per, (i + 1) * per)))
                 for i, d in enumerate(dirs)]
    else:
        anims = [("default", list(range(len(frames))))]
    anim_strs = []
    for name, idxs in anims:
        fr = ", ".join('{"duration": 1.0, "texture": SubResource("%s")}'
                       % sub_ids[i] for i in idxs)
        anim_strs.append('{"frames": [%s], "loop": true, "name": &"%s", '
                         '"speed": %s.0}' % (fr, name, fps))
    steps = len(frames) + 2
    nl = chr(10)
    head = (f'[gd_resource type="SpriteFrames" load_steps={steps} '
            f'format=3]{nl}{nl}'
            f'[ext_resource type="Texture2D" '
            f'path="res://{sheet_png_name}" id="1"]{nl}{nl}')
    return (head + nl.join(lines) + nl + "[resource]" + nl
            + "animations = [" + ", ".join(anim_strs) + "]" + nl)


def to_css(sheet, sheet_png_name):
    fw, fh = sheet["frame_width"], sheet["frame_height"]
    n = sheet["count"]
    cols = sheet["columns"]
    total_w = fw * cols
    dur_s = round(n / sheet["fps"], 3)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>pixy animation</title>
<style>
  body {{ background:#222; display:flex; justify-content:center;
          align-items:center; min-height:100vh; margin:0; }}
  .pixy-anim {{
    width:{fw}px; height:{fh}px;
    background-image:url('{sheet_png_name}');
    background-repeat:no-repeat;
    image-rendering:pixelated;
    animation:pixy-play {dur_s}s steps({n}) infinite;
  }}
  @keyframes pixy-play {{
    from {{ background-position:0 0; }}
    to   {{ background-position:-{total_w}px 0; }}
  }}
</style></head>
<body><div class="pixy-anim"></div></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sheet_json", type=Path, help="<name>_sheet.json")
    p.add_argument("--engine", required=True, choices=("aseprite", "css", "godot"))
    p.add_argument("--out", type=Path, required=True, help="output file")
    p.add_argument("--image", help="sheet PNG name to reference "
                                   "(default: sheet json name + _sheet.png)")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    sheet = load_sheet(args.sheet_json)
    if sheet is None:
        return 2

    # Default the referenced PNG to the sheet's sibling <stem>.png.
    png_name = args.image or (args.sheet_json.stem + ".png")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.engine == "aseprite":
        args.out.write_text(json.dumps(to_aseprite(sheet, png_name), indent=2)
                            + "\n", encoding="utf-8")
    elif args.engine == "godot":
        args.out.write_text(to_godot(sheet, png_name), encoding="utf-8")
    else:
        args.out.write_text(to_css(sheet, png_name), encoding="utf-8")
    print(f"wrote {args.out} ({args.engine}, references {png_name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
