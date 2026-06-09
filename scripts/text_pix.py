#!/usr/bin/env python3
"""Render text with a built-in 3x5 pixel font.

Usage:
    text_pix.py --text "SCORE 100" --char K --out score.pix
    text_pix.py --text "GAME OVER" --png --color "#ffffff" --scale 6 --out go.png

Produces UI text - score readouts, labels, menu items - as pixel art. The
font is an embedded, deterministic 3x5 bitmap (uppercase A-Z, 0-9, space, and
common punctuation), so the same text renders identically everywhere. Glyphs
are 3 wide x 5 tall with a 1px gap.

Default output is a .pix grid (the `--char` maps "on" pixels; off is the
transparent_char "."), so it flows through check_sprite/render/compose. With
--png it renders straight to a colored PNG at --scale (Pillow).

Lowercase input is upcased (the font is uppercase-only). Unknown characters
render as "?".

Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing (--png only).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import write_pix  # noqa: E402

# 3x5 bitmap font. Each glyph is 5 rows of 3 columns, '/'-separated, 'X' = on.
FONT = {
    " ": "   /   /   /   /   ",
    "A": "XXX/X X/XXX/X X/X X", "B": "XX /X X/XX /X X/XX ",
    "C": "XXX/X  /X  /X  /XXX", "D": "XX /X X/X X/X X/XX ",
    "E": "XXX/X  /XXX/X  /XXX", "F": "XXX/X  /XXX/X  /X  ",
    "G": "XXX/X  /X X/X X/XXX", "H": "X X/X X/XXX/X X/X X",
    "I": "XXX/ X / X / X /XXX", "J": "  X/  X/  X/X X/XXX",
    "K": "X X/XX /X  /XX /X X", "L": "X  /X  /X  /X  /XXX",
    "M": "X X/XXX/XXX/X X/X X", "N": "X X/XXX/XXX/XXX/X X",
    "O": "XXX/X X/X X/X X/XXX", "P": "XXX/X X/XXX/X  /X  ",
    "Q": "XXX/X X/X X/XXX/  X", "R": "XX /X X/XX /X X/X X",
    "S": "XXX/X  /XXX/  X/XXX", "T": "XXX/ X / X / X / X ",
    "U": "X X/X X/X X/X X/XXX", "V": "X X/X X/X X/X X/ X ",
    "W": "X X/X X/XXX/XXX/X X", "X": "X X/X X/ X /X X/X X",
    "Y": "X X/X X/ X / X / X ", "Z": "XXX/  X/ X /X  /XXX",
    "0": "XXX/X X/X X/X X/XXX", "1": " X /XX / X / X /XXX",
    "2": "XXX/  X/XXX/X  /XXX", "3": "XXX/  X/XXX/  X/XXX",
    "4": "X X/X X/XXX/  X/  X", "5": "XXX/X  /XXX/  X/XXX",
    "6": "XXX/X  /XXX/X X/XXX", "7": "XXX/  X/  X/  X/  X",
    "8": "XXX/X X/XXX/X X/XXX", "9": "XXX/X X/XXX/  X/XXX",
    ".": "   /   /   /   / X ", ",": "   /   /   / X /X  ",
    "!": " X / X / X /   / X ", "?": "XXX/  X/ XX/   / X ",
    ":": "   / X /   / X /   ", "-": "   /   /XXX/   /   ",
    "+": "   / X /XXX/ X /   ", "/": "  X/  X/ X /X  /X  ",
    "=": "   /XXX/   /XXX/   ", "%": "X X/  X/ X /X  /X X",
    "(": " X /X  /X  /X  / X ", ")": " X /  X/  X/  X/ X ",
    "*": "X X/ X /XXX/ X /X X", "'": " X / X /   /   /   ",
}
GLYPH_W, GLYPH_H, GAP = 3, 5, 1


def text_to_rows(text: str, on: str = "K", off: str = ".") -> list[str]:
    glyphs = [FONT.get(c, FONT["?"]).split("/")
              for c in text.upper()] or [FONT[" "].split("/")]
    rows = []
    for r in range(GLYPH_H):
        parts = []
        for g in glyphs:
            parts.append("".join(on if px == "X" else off for px in g[r]))
        rows.append((off * GAP).join(parts))
    return rows


def text_to_image(text: str, color: str, scale: int):
    from PIL import Image  # local import: only needed for PNG output
    rows = text_to_rows(text, on="X", off=" ")
    w, h = len(rows[0]), len(rows)
    h_hex = color.lstrip("#")
    rgba = (int(h_hex[0:2], 16), int(h_hex[2:4], 16), int(h_hex[4:6], 16), 255)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "X":
                px[x, y] = rgba
    if scale > 1:
        nearest = getattr(getattr(Image, "Resampling", Image), "NEAREST")
        img = img.resize((w * scale, h * scale), nearest)
    return img


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--text", required=True, help="text to render")
    p.add_argument("--out", type=Path, required=True, help="output .pix or .png")
    p.add_argument("--char", default="K", help="legend char for 'on' (.pix mode)")
    p.add_argument("--png", action="store_true", help="render a colored PNG")
    p.add_argument("--color", default="#ffffff", help="PNG text color")
    p.add_argument("--scale", type=int, default=1, help="PNG upscale factor")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    if len(args.char) != 1:
        print("error: --char must be a single character", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.png:
        try:
            img = text_to_image(args.text, args.color, max(1, args.scale))
        except ImportError:
            print("error: Pillow is required for --png. Install: "
                  "python -m pip install Pillow", file=sys.stderr)
            return 3
        img.save(args.out, "PNG")
        print(f"wrote {args.out}  ({img.width}x{img.height} px)")
    else:
        rows = text_to_rows(args.text, on=args.char, off=".")
        write_pix(rows, args.out, header=f"text: {args.text}")
        print(f"wrote {args.out}  ({len(rows[0])}x{len(rows)} grid)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
