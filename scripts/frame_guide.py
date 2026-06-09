#!/usr/bin/env python3
"""Render the spec's proportion frame as a guide overlay.

Usage:
    frame_guide.py --spec pixy.spec.json --out guide.png
    frame_guide.py --spec pixy.spec.json --on hero.pix --out check.png

Draws the shared layout from the spec's `frame` block - safe-area margin,
baseline, center axis, content-height band, and pivot - at the export scale,
so an asset can be authored to sit in the same place and size as the rest of
the set. With --on, it overlays the guides on a rendered asset so you can see
whether it fits the frame.

Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("error: Pillow is required. Install: python -m pip install Pillow",
          file=sys.stderr)
    sys.exit(3)

AXIS = (65, 166, 246, 200)
BASE = (167, 240, 112, 220)
MARGIN = (255, 205, 117, 160)
BAND = (255, 255, 255, 40)
PIVOT = (239, 125, 87, 255)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--on", type=Path, help="overlay guides on this .pix")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        scale = int(spec.get("scale", 1))
        W = int(spec["canvas"]["width"]) * scale
        H = int(spec["canvas"]["height"]) * scale
        frame = spec.get("frame", {})
        if args.on:
            from render_sprite import render
            rows = parse_pix(args.on)
            errs = validate_grid(rows, spec)
            if errs:
                raise SpriteError("; ".join(errs))
            base = render(rows, spec, scale).convert("RGBA")
        else:
            base = Image.new("RGBA", (W, H), (18, 19, 27, 255))
    except (SpriteError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    m = frame.get("margin", 0.06)
    d.rectangle([m * W, m * H, (1 - m) * W - 1, (1 - m) * H - 1],
                outline=MARGIN, width=max(1, scale // 4))
    base_y = frame.get("baseline", 0.94) * H
    d.line([0, base_y, W, base_y], fill=BASE, width=max(1, scale // 3))
    ax = frame.get("center_axis", 0.5) * W
    d.line([ax, 0, ax, H], fill=AXIS, width=max(1, scale // 4))
    ch = frame.get("content_height", 0.82)
    d.rectangle([0, base_y - ch * H, W, base_y], fill=BAND)
    pv = frame.get("pivot", [0.5, 0.94])
    pr = max(2, scale)
    d.ellipse([pv[0] * W - pr, pv[1] * H - pr, pv[0] * W + pr, pv[1] * H + pr],
              fill=PIVOT)

    out = Image.alpha_composite(base, ov)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out, "PNG")
    print(f"wrote {args.out}  ({W}x{H}, frame guides"
          + (" over " + args.on.name if args.on else "") + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
