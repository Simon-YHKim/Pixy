#!/usr/bin/env python3
"""Draw shapes into a .pix grid, with symmetry and auto-outline.

Usage:
    draw_pix.py --spec pixy.spec.json --out body.pix \\
        --dot 8,4,W --line 2,8,13,8,g --rect 4,4,8,6,g,fill \\
        --circle 8,8,5,g,fill --mirror x --outline K

Stdlib only. Reduces hand-counting errors when blocking in a sprite. Start
from a blank canvas (default) or edit an existing grid with --in. Shape ops
use grid coordinates (x,y from the top-left, 0-based) and a legend char; add
',fill' to fill a rect/circle. Ops apply in the order given.

  --dot     x,y,CHAR
  --line    x1,y1,x2,y2,CHAR
  --rect    x,y,w,h,CHAR[,fill]
  --circle  cx,cy,r,CHAR[,fill]
  --mirror  x|y                 mirror the half you drew across the center
  --outline CHAR                add a 1px outline around all solid pixels

Canvas size comes from --spec (or --canvas WxH). All chars must be in the
spec legend; validate the result with check_sprite.py.

Exit codes: 0 = written, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, write_pix  # noqa: E402

CANVAS_RE = __import__("re").compile(r"^(\d+)x(\d+)$")


def blank(w: int, h: int, fill: str) -> list[list[str]]:
    return [[fill for _ in range(w)] for _ in range(h)]


def set_px(grid, x, y, ch):
    if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
        grid[y][x] = ch


def op_line(grid, x1, y1, x2, y2, ch):
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    sx, sy = (1 if x1 < x2 else -1), (1 if y1 < y2 else -1)
    err = dx - dy
    while True:
        set_px(grid, x1, y1, ch)
        if x1 == x2 and y1 == y2:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x1 += sx
        if e2 < dx:
            err += dx
            y1 += sy


def op_rect(grid, x, y, w, h, ch, fill):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if fill or yy in (y, y + h - 1) or xx in (x, x + w - 1):
                set_px(grid, xx, yy, ch)


def op_circle(grid, cx, cy, r, ch, fill):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            d = (xx - cx) ** 2 + (yy - cy) ** 2
            if (d <= r * r) if fill else (abs(d - r * r) <= r):
                set_px(grid, xx, yy, ch)


def op_mirror(grid, axis, transparent):
    h, w = len(grid), len(grid[0])
    if axis == "x":
        for y in range(h):
            for x in range(w // 2):
                if grid[y][x] != transparent:
                    grid[y][w - 1 - x] = grid[y][x]
    else:
        for y in range(h // 2):
            for x in range(w):
                if grid[y][x] != transparent:
                    grid[h - 1 - y][x] = grid[y][x]


def op_floodfill(grid, x, y, ch):
    h, w = len(grid), len(grid[0])
    if not (0 <= y < h and 0 <= x < w):
        return
    target = grid[y][x]
    if target == ch:
        return
    stack = [(y, x)]
    while stack:
        cy, cx = stack.pop()
        if not (0 <= cy < h and 0 <= cx < w) or grid[cy][cx] != target:
            continue
        grid[cy][cx] = ch
        stack.extend([(cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)])


def op_outline(grid, ch, transparent):
    h, w = len(grid), len(grid[0])
    solid = {(y, x) for y in range(h) for x in range(w)
             if grid[y][x] != transparent}
    for y in range(h):
        for x in range(w):
            if grid[y][x] != transparent:
                continue
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (y + dy, x + dx) in solid:
                    grid[y][x] = ch
                    break


def parse_ints(spec_str, n, name):
    parts = spec_str.split(",")
    nums = parts[:n]
    if len(nums) < n:
        raise SpriteError(f"--{name} needs {n} numbers + CHAR: {spec_str!r}")
    try:
        vals = [int(v) for v in nums]
    except ValueError:
        raise SpriteError(f"--{name} coords must be integers: {spec_str!r}")
    ch = parts[n]
    fill = len(parts) > n + 1 and parts[n + 1] == "fill"
    return vals, ch, fill


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", type=Path, help="pixy.spec.json (for canvas+legend)")
    p.add_argument("--canvas", help="WxH if no spec")
    p.add_argument("--in", dest="infile", type=Path, help="edit existing .pix")
    p.add_argument("--out", type=Path, required=True, help="output .pix")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dot", action="append", default=[])
    p.add_argument("--line", action="append", default=[])
    p.add_argument("--rect", action="append", default=[])
    p.add_argument("--circle", action="append", default=[])
    p.add_argument("--fill-area", dest="fill_area", action="append", default=[],
                   help="flood fill from x,y with CHAR (bucket)")
    p.add_argument("--mirror", choices=("x", "y"))
    p.add_argument("--outline")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2

    legend = None
    transparent = "."
    try:
        if args.spec:
            spec = load_spec(args.spec)
            w, h = int(spec["canvas"]["width"]), int(spec["canvas"]["height"])
            legend = set(spec["legend"]) | {str(spec["transparent_char"])}
            transparent = str(spec["transparent_char"])
        elif args.canvas:
            m = CANVAS_RE.match(args.canvas.lower())
            if not m:
                raise SpriteError("--canvas must look like 32x32")
            w, h = int(m.group(1)), int(m.group(2))
        else:
            raise SpriteError("provide --spec or --canvas")

        if args.infile:
            rows = parse_pix(args.infile)
            grid = [list(r) for r in rows]
            if len(grid) != h or any(len(r) != w for r in grid):
                raise SpriteError("--in grid size does not match canvas")
        else:
            grid = blank(w, h, transparent)

        for d in args.dot:
            (x, y), ch, _ = parse_ints(d, 2, "dot")
            set_px(grid, x, y, ch)
        for ln in args.line:
            (x1, y1, x2, y2), ch, _ = parse_ints(ln, 4, "line")
            op_line(grid, x1, y1, x2, y2, ch)
        for rc in args.rect:
            (x, y, rw, rh), ch, fill = parse_ints(rc, 4, "rect")
            op_rect(grid, x, y, rw, rh, ch, fill)
        for cc in args.circle:
            (cx, cy, r), ch, fill = parse_ints(cc, 3, "circle")
            op_circle(grid, cx, cy, r, ch, fill)
        for fa in args.fill_area:
            (x, y), ch, _ = parse_ints(fa, 2, "fill-area")
            op_floodfill(grid, x, y, ch)
        if args.mirror:
            op_mirror(grid, args.mirror, transparent)
        if args.outline:
            op_outline(grid, args.outline, transparent)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    rows = ["".join(r) for r in grid]
    if legend is not None:
        bad = sorted({c for row in rows for c in row if c not in legend})
        if bad:
            print(f"error: drew off-palette chars {bad} not in spec legend",
                  file=sys.stderr)
            return 2
    write_pix(rows, args.out, header=f"drawn {w}x{h}")
    print(f"wrote {args.out}  ({w}x{h} grid, {len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
