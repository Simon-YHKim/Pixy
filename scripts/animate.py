#!/usr/bin/env python3
"""Animate Pixy sprite frames into a GIF, APNG, and/or sprite sheet.

Usage:
    animate.py --spec pixy.spec.json --frames f0.pix f1.pix f2.pix \\
               --out walk --format all [--fps 8] [--no-loop] [--pingpong]
    animate.py --spec pixy.spec.json --manifest walk.anim.json --out walk

Takes several .pix frames that share ONE spec and produces, deterministically:
    - <out>.gif        : looping animated GIF (binary transparency, crisp)
    - <out>.png        : animated PNG (APNG) preserving full alpha
    - <out>_sheet.png  : a single sprite sheet (frames tiled)
    - <out>_sheet.json : frame rectangles + fps, for game-engine slicing
    - <out>_onion.png  : (with --onion) all frames overlaid to preview motion

Because every frame is validated against the same spec, all frames share the
canvas size and palette, so the sheet never misaligns and the animation never
flickers between palettes.

Timing: --fps sets a constant rate; a manifest may instead give per-frame
milliseconds ({"frame": "f0.pix", "ms": 120}). --pingpong plays forward then
back. Formats: gif | apng | sheet | all (default all). Sheet layout:
horizontal (default) | grid:COLSxROWS.

Exit codes: 0 = written, 1 = a frame failed validation, 2 = usage/IO error,
3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402

try:
    from PIL import Image
except ImportError:
    print("error: Pillow is required for animation. Install it with:\n"
          "    python -m pip install Pillow", file=sys.stderr)
    sys.exit(3)

from render_sprite import render  # noqa: E402


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SpriteError(f"manifest not found: {path}")
    except json.JSONDecodeError as e:
        raise SpriteError(f"manifest is not valid JSON: {e}")
    if "frames" not in data or not isinstance(data["frames"], list) \
            or not data["frames"]:
        raise SpriteError("manifest must have a non-empty 'frames' list")
    return data


def register_frames(frames, spec):
    """Shift each frame so its content pivot lands on the spec frame pivot -
    keeps an animation grounded (no jitter) when frames drift slightly."""
    fr = spec.get("frame", {})
    W, H = frames[0].size
    px_pivot = fr.get("pivot", [0.5, 1.0])
    tx, ty = px_pivot[0] * W, px_pivot[1] * H
    out = []
    for f in frames:
        bb = f.getbbox()                     # (l, t, r, b) of non-zero alpha
        if not bb:
            out.append(f)
            continue
        cx = (bb[0] + bb[2]) / 2
        cy = bb[3]                           # bottom of content
        dx, dy = int(round(tx - cx)), int(round(ty - cy))
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.alpha_composite(f, (dx, dy))
        out.append(canvas)
    return out


def manifest_frames(man: dict[str, Any], base: Path):
    """Return (paths, per_frame_ms or None). Frames may be strings or
    {"frame": name, "ms": int} objects."""
    paths, ms = [], []
    has_ms = False
    for item in man["frames"]:
        if isinstance(item, dict):
            paths.append(base / item["frame"])
            ms.append(item.get("ms"))
            has_ms = has_ms or "ms" in item
        else:
            paths.append(base / item)
            ms.append(None)
    return paths, (ms if has_ms else None)


def render_frames(frame_paths, spec, scale):
    frames = []
    for fp in frame_paths:
        rows = parse_pix(fp)
        errors = validate_grid(rows, spec)
        if errors:
            raise SpriteError(f"frame {fp} is invalid: {'; '.join(errors)}")
        frames.append(render(rows, spec, scale).convert("RGBA"))
    return frames


def build_palette(spec):
    def hex_rgb(h):
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    background = spec.get("background", "transparent")
    legend_rgbs = [hex_rgb(v) for v in spec["legend"].values()]
    if background == "transparent":
        palette = [(0, 0, 0)] + legend_rgbs
        transparent_index = 0
    else:
        palette = [hex_rgb(background)] + legend_rgbs
        transparent_index = None
    rgb_to_index = {rgb: i + 1 for i, rgb in enumerate(legend_rgbs)}
    if background != "transparent":
        rgb_to_index[hex_rgb(background)] = 0
    return palette, rgb_to_index, transparent_index


def to_p_frame(img, palette, rgb_to_index, transparent_index):
    w, h = img.size
    px = img.load()
    indices = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if transparent_index is not None and a == 0:
                indices.append(transparent_index)
            else:
                indices.append(rgb_to_index.get((r, g, b), 0))
    p = Image.new("P", (w, h))
    flat: list[int] = []
    for c in palette:
        flat.extend(c)
    flat.extend([0] * (768 - len(flat)))
    p.putpalette(flat)
    p.putdata(indices)
    return p


def save_gif(frames, spec, out, durations, loop):
    palette, rgb_to_index, t_index = build_palette(spec)
    p_frames = [to_p_frame(f, palette, rgb_to_index, t_index) for f in frames]
    kwargs: dict[str, Any] = {
        "save_all": True, "append_images": p_frames[1:],
        "duration": durations, "disposal": 2,
    }
    if loop:
        kwargs["loop"] = 0
    if t_index is not None:
        kwargs["transparency"] = t_index
    p_frames[0].save(out, **kwargs)


def save_apng(frames, out, durations, loop):
    frames[0].save(out, format="PNG", save_all=True, append_images=frames[1:],
                   duration=durations, loop=0 if loop else 1, disposal=1)


def save_onion(frames, out):
    """Overlay all frames with rising opacity to preview the motion arc."""
    base = Image.new("RGBA", frames[0].size, (0, 0, 0, 0))
    n = len(frames)
    for i, fr in enumerate(frames):
        alpha = int(60 + 195 * (i / max(1, n - 1)))  # back frames fainter
        ghost = fr.copy()
        a = ghost.getchannel("A").point(lambda v, _a=alpha: min(v, _a))
        ghost.putalpha(a)
        base = Image.alpha_composite(base, ghost)
    base.save(out, "PNG")


def parse_layout(layout, count):
    if layout == "horizontal":
        return count, 1
    if layout.startswith("grid:") and "x" in layout:
        cols, rows = layout[5:].split("x", 1)
        cols, rows = int(cols), int(rows)
        if cols * rows < count:
            raise SpriteError(
                f"grid {cols}x{rows} holds {cols * rows} < {count} frames")
        return cols, rows
    raise SpriteError(f"bad --layout {layout!r}; use 'horizontal' or 'grid:4x2'")


def save_sheet(frames, out_png, out_json, fps, layout):
    fw, fh = frames[0].size
    cols, rows = parse_layout(layout, len(frames))
    sheet = Image.new("RGBA", (fw * cols, fh * rows), (0, 0, 0, 0))
    meta_frames = []
    for i, fr in enumerate(frames):
        r, c = divmod(i, cols)
        x, y = c * fw, r * fh
        sheet.paste(fr, (x, y))
        meta_frames.append({"index": i, "x": x, "y": y, "w": fw, "h": fh})
    sheet.save(out_png, "PNG")
    out_json.write_text(json.dumps({
        "frame_width": fw, "frame_height": fh, "columns": cols, "rows": rows,
        "count": len(frames), "fps": fps, "frames": meta_frames,
    }, indent=2) + "\n", encoding="utf-8")
    return cols, rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--frames", type=Path, nargs="+", help="ordered .pix frames")
    p.add_argument("--manifest", type=Path, help="anim manifest JSON")
    p.add_argument("--out", type=Path, required=True, help="output basename")
    p.add_argument("--format", choices=("gif", "apng", "sheet", "all"),
                   default="all")
    p.add_argument("--fps", type=int, default=8, help="frames per second")
    p.add_argument("--no-loop", action="store_true", help="play once")
    p.add_argument("--register", action="store_true",
                   help="align frames to the spec pivot (keeps it grounded)")
    p.add_argument("--pingpong", action="store_true",
                   help="play forward then back")
    p.add_argument("--onion", action="store_true",
                   help="also write <out>_onion.png motion preview")
    p.add_argument("--scale", type=int, help="override the spec export scale")
    p.add_argument("--layout", default="horizontal",
                   help="sheet layout: horizontal or grid:COLSxROWS")
    args = p.parse_args(argv)

    fps = args.fps
    loop = not args.no_loop
    per_frame_ms = None
    try:
        spec = load_spec(args.spec)
        if args.manifest:
            man = load_manifest(args.manifest)
            frame_paths, per_frame_ms = manifest_frames(man, args.manifest.parent)
            fps = man.get("fps", fps)
            loop = man.get("loop", loop)
        elif args.frames:
            frame_paths = args.frames
        else:
            print("error: provide --frames or --manifest", file=sys.stderr)
            return 2
        if fps < 1:
            print("error: --fps must be >= 1", file=sys.stderr)
            return 2
        scale = args.scale or int(spec.get("scale", 1))
        if scale < 1:
            print("error: scale must be >= 1", file=sys.stderr)
            return 2
        frames = render_frames(frame_paths, spec, scale)
        if args.register:
            frames = register_frames(frames, spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1 if "invalid" in str(e) else 2

    # Per-frame durations (ms): from manifest where given, else constant.
    const_ms = max(1, round(1000 / fps))
    durations = [m if m else const_ms for m in (per_frame_ms or [None] * len(frames))]

    if args.pingpong and len(frames) > 2:
        frames = frames + frames[-2:0:-1]
        durations = durations + durations[-2:0:-1]

    if len(frames) < 2 and args.format in ("gif", "apng", "all"):
        print("warning: only 1 frame; animation will be a still image",
              file=sys.stderr)

    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    try:
        if args.format in ("gif", "all"):
            gif = out.with_suffix(".gif")
            save_gif(frames, spec, gif, durations, loop)
            written.append(str(gif))
        if args.format in ("apng", "all"):
            apng = out.with_suffix(".png")
            save_apng(frames, apng, durations, loop)
            written.append(str(apng))
        if args.format in ("sheet", "all"):
            sheet_png = out.with_name(out.name + "_sheet").with_suffix(".png")
            sheet_json = out.with_name(out.name + "_sheet").with_suffix(".json")
            cols, rows = save_sheet(frames, sheet_png, sheet_json, fps,
                                    args.layout)
            written.append(f"{sheet_png} ({cols}x{rows} grid) + {sheet_json}")
        if args.onion:
            onion = out.with_name(out.name + "_onion").with_suffix(".png")
            save_onion(frames, onion)
            written.append(str(onion))
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    fw, fh = frames[0].size
    print(f"animated {len(frames)} frames @ {fps} fps "
          f"(loop={'yes' if loop else 'no'}"
          f"{', pingpong' if args.pingpong else ''}), frame {fw}x{fh} px:")
    for w in written:
        print(f"  wrote {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
