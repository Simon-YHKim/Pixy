#!/usr/bin/env python3
"""Trace a reference image into an editable .pix grid against a spec.

Usage:
    trace_image.py <reference.png> --spec pixy.spec.json --out traced.pix

Where analyze_sample.py recovers the *style* (palette, size) from a sample,
this recovers the *art*: it downscales the image to the spec canvas and maps
each pixel to the nearest locked-palette color, producing a .pix you can
edit and animate. Transparent/low-alpha pixels become the transparent_char
when the spec background is transparent.

The result is a draft to clean up by hand - nearest-color mapping and the
downscale are approximations. Run check_sprite.py on it afterwards.

Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, write_pix  # noqa: E402
from analyze_sample import estimate_native_scale  # noqa: E402

try:
    from PIL import Image
except ImportError:
    print("error: Pillow is required. Install it with:\n"
          "    python -m pip install Pillow", file=sys.stderr)
    sys.exit(3)

NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def nearest_char(rgb, legend_rgb) -> str:
    r, g, b = rgb
    best_char, best_d = None, None
    for ch, (lr, lg, lb) in legend_rgb.items():
        d = (r - lr) ** 2 + (g - lg) ** 2 + (b - lb) ** 2
        if best_d is None or d < best_d:
            best_char, best_d = ch, d
    return best_char


def trace(img: "Image.Image", spec: dict, detect: bool = True) -> list[str]:
    width = int(spec["canvas"]["width"])
    height = int(spec["canvas"]["height"])
    transparent = str(spec["transparent_char"])
    bg_transparent = spec.get("background", "transparent") == "transparent"
    legend_rgb = {ch: hex_to_rgb(v) for ch, v in spec["legend"].items()}

    src = img.convert("RGBA")
    # If the reference is a clean integer upscale, drop it to its native grid
    # first so the final resize samples true pixels, not blended edges.
    if detect:
        scale = estimate_native_scale(src)
        if scale > 1:
            src = src.resize((src.width // scale, src.height // scale), NEAREST)
    native = src.resize((width, height), NEAREST)
    px = native.load()
    rows: list[str] = []
    for y in range(height):
        row = []
        for x in range(width):
            r, g, b, a = px[x, y]
            if bg_transparent and a < 128:
                row.append(transparent)
            else:
                row.append(nearest_char((r, g, b), legend_rgb))
        rows.append("".join(row))
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", type=Path, help="reference image")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--out", type=Path, required=True, help="output .pix")
    p.add_argument("--no-detect", action="store_true",
                   help="skip native-size detection; resize source directly")
    p.add_argument("--force", action="store_true", help="overwrite existing")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    if not args.image.exists():
        print(f"error: image not found: {args.image}", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        if not spec["legend"]:
            raise SpriteError("spec legend is empty; nothing to map to")
        img = Image.open(args.image)
        img.load()
    except (SpriteError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    rows = trace(img, spec, detect=not args.no_detect)
    write_pix(rows, args.out,
              header=f"traced from {args.image.name} "
                     f"({spec['canvas']['width']}x{spec['canvas']['height']})")
    used = sorted({c for row in rows for c in row
                   if c != str(spec["transparent_char"])})
    print(f"wrote {args.out}  ({spec['canvas']['width']}x"
          f"{spec['canvas']['height']} grid, {len(used)} colors used)")
    print("  REVIEW: nearest-color mapping is approximate; clean up by hand "
          "and run check_sprite.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
