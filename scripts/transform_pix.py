#!/usr/bin/env python3
"""Transform a .pix grid: flip, rotate, or recolor (palette swap).

Usage:
    transform_pix.py hero.pix --flip h --out hero_left.pix
    transform_pix.py hero.pix --rotate 90 --out hero_r.pix
    transform_pix.py red.pix --recolor r:b,R:c,o:L --out blue.pix --spec pixy.spec.json

Stdlib only. Common uses:
  - flip h  : mirror left<->right (e.g. make the opposite-facing sprite)
  - flip v  : mirror top<->bottom
  - rotate  : 90 / 180 / 270 degrees clockwise (rotate 90/270 needs a square
              canvas)
  - recolor : remap legend chars to make palette variants (red->blue slime).
              MAP is comma-separated FROM:TO pairs.

With --spec, the result is checked to stay inside the locked legend.

Exit codes: 0 = written, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, write_pix  # noqa: E402


def flip(grid, axis):
    if axis == "h":
        return [list(reversed(r)) for r in grid]
    return list(reversed([list(r) for r in grid]))


def rotate(grid, deg):
    if deg == 180:
        return [list(reversed(r)) for r in reversed(grid)]
    h, w = len(grid), len(grid[0])
    if w != h:
        raise SpriteError(f"rotate {deg} needs a square canvas ({w}x{h})")
    if deg == 90:
        return [[grid[h - 1 - x][y] for x in range(h)] for y in range(w)]
    if deg == 270:
        return [[grid[x][w - 1 - y] for x in range(h)] for y in range(w)]
    raise SpriteError("rotate must be 90, 180, or 270")


def recolor(grid, mapping):
    return [[mapping.get(c, c) for c in row] for row in grid]


def parse_map(s):
    out = {}
    for pair in s.split(","):
        if ":" not in pair:
            raise SpriteError(f"--recolor pair must be FROM:TO, got {pair!r}")
        a, b = pair.split(":", 1)
        if len(a) != 1 or len(b) != 1:
            raise SpriteError(f"--recolor chars must be single: {pair!r}")
        out[a] = b
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path, help="input .pix")
    p.add_argument("--out", type=Path, required=True, help="output .pix")
    p.add_argument("--flip", choices=("h", "v"))
    p.add_argument("--rotate", type=int, choices=(90, 180, 270))
    p.add_argument("--recolor", help="FROM:TO,FROM:TO char remap")
    p.add_argument("--spec", type=Path, help="validate result against legend")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    if not (args.flip or args.rotate or args.recolor):
        print("error: choose at least one of --flip/--rotate/--recolor",
              file=sys.stderr)
        return 2

    try:
        rows = parse_pix(args.sprite)
        grid = [list(r) for r in rows]
        if args.flip:
            grid = flip(grid, args.flip)
        if args.rotate:
            grid = rotate(grid, args.rotate)
        if args.recolor:
            grid = recolor(grid, parse_map(args.recolor))
        result = ["".join(r) for r in grid]
        if args.spec:
            spec = load_spec(args.spec)
            allowed = set(spec["legend"]) | {str(spec["transparent_char"])}
            bad = sorted({c for row in result for c in row if c not in allowed})
            if bad:
                raise SpriteError(f"result has off-palette chars {bad}")
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    write_pix(result, args.out, header=f"transformed from {args.sprite.name}")
    print(f"wrote {args.out}  ({len(result[0])}x{len(result)} grid)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
