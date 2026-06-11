#!/usr/bin/env python3
"""Render a .pix character grid to a transparent, exact-size PNG.

Usage:
    render_sprite.py <sprite.pix> --spec <pixy.spec.json>
                     [--out <asset.png>] [--scale N] [--no-upscale]

Deterministic: the same grid and spec always produce the same PNG, byte
for byte, on any machine and for any agent. Validation (dimensions,
palette, transparency) runs first via check_sprite; rendering aborts on
any violation so a bad sprite never silently produces a wrong image.

Pixels are placed 1:1 from the native grid, then upscaled by the spec
'scale' with nearest-neighbor (no blurring). The transparent_char maps
to alpha 0 when the spec background is 'transparent' (nukki), otherwise to
the opaque background color.

Exit codes: 0 = PNG written, 1 = validation failed, 2 = usage/IO error,
3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# check_sprite lives alongside this file; reuse its loader/validator so the
# two scripts can never drift apart.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402

try:
    from PIL import Image
except ImportError:
    print("error: Pillow is required for rendering. Install it with:\n"
          "    python -m pip install Pillow", file=sys.stderr)
    sys.exit(3)

# Pillow moved resampling constants to Image.Resampling in 9.1; the module
# alias still exists but resolve defensively for forward compatibility.
NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")


def hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = value.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def build_color_map(spec: dict[str, Any]) -> dict[str, tuple[int, int, int, int]]:
    transparent = str(spec["transparent_char"])
    background = spec.get("background", "transparent")
    # older/hand-written specs map the transparent char to "transparent"
    # inside the legend itself: only hex values are colors
    cmap = {ch: hex_to_rgba(hexv) for ch, hexv in spec["legend"].items()
            if str(hexv).startswith("#")}
    if background == "transparent":
        cmap[transparent] = (0, 0, 0, 0)
    else:
        cmap[transparent] = hex_to_rgba(background)
    return cmap


def render(rows: list[str], spec: dict[str, Any], scale: int) -> "Image.Image":
    width = int(spec["canvas"]["width"])
    height = int(spec["canvas"]["height"])
    cmap = build_color_map(spec)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            px[x, y] = cmap[ch]
    if scale > 1:
        img = img.resize((width * scale, height * scale), NEAREST)
    return img


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path, help="path to .pix file")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--out", type=Path, help="output PNG (default: sprite name + .png)")
    p.add_argument("--scale", type=int, help="override the spec export scale")
    p.add_argument("--no-upscale", action="store_true",
                   help="render at native size (scale 1)")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
        rows = parse_pix(args.sprite)
        errors = validate_grid(rows, spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if errors:
        print(f"FAIL: {args.sprite} is invalid; not rendering "
              f"({len(errors)} issue(s)):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    scale = 1 if args.no_upscale else (args.scale or int(spec.get("scale", 1)))
    if scale < 1:
        print("error: scale must be >= 1", file=sys.stderr)
        return 2

    out = args.out or args.sprite.with_suffix(".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img = render(rows, spec, scale)
    img.save(out, "PNG")
    print(f"wrote {out}  ({img.width}x{img.height} px, scale {scale})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
