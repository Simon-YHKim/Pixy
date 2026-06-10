#!/usr/bin/env python3
"""Apply safe automatic cleanups to a .pix to raise its quality.

Usage:
    autofix.py sprite.pix --spec pixy.spec.json --out clean.pix

Fixes only unambiguous craft defects - no artistic guessing:
  - orphan pixels (a solid pixel fully surrounded by transparent) -> removed
  - single-pixel holes (transparent fully surrounded by solid) -> filled with
    the majority neighbor color
  - with --smooth: 1px contour wobbles (lint_pix "jaggy") -> bumps shaved,
    dents filled, restoring the pixel-perfect line

Reports what changed and the detail score before/after. Run check_sprite.py
and lint_pix.py afterwards.

Exit codes: 0 = written, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid, write_pix  # noqa: E402
import detail_score  # noqa: E402
import lint_pix  # noqa: E402

NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def smooth_jaggies(grid, transparent, passes=2):
    """Shave 1px contour bumps and fill 1px dents (lint_pix's 'jaggy')."""
    fixed = 0
    for _ in range(passes):
        rows = ["".join(r) for r in grid]
        jags = lint_pix.find_jaggies(rows, transparent)
        if not jags:
            break
        cts = lint_pix.contours(rows, transparent)
        for name, i, kind in jags:
            seq = cts[name]
            v, flat = seq[i], seq[i - 1]
            if name in ("left", "right"):
                y = i
                if kind == "bump":                  # shave the outlier pixel
                    grid[y][v] = transparent
                else:                               # fill the bite
                    nx = flat
                    src = grid[y - 1][seq[i - 1]]
                    grid[y][nx] = src
            else:
                x = i
                if kind == "bump":
                    grid[v][x] = transparent
                else:
                    src = grid[seq[i - 1]][i - 1]
                    grid[flat][x] = src
            fixed += 1
    return fixed


def fix(grid, transparent):
    h, w = len(grid), len(grid[0])

    def at(y, x):
        return grid[y][x] if 0 <= y < h and 0 <= x < w else transparent

    orphans = holes = 0
    for _ in range(3):                       # a few passes until stable
        changed = 0
        for y in range(h):
            for x in range(w):
                c = grid[y][x]
                neigh = [at(y + dy, x + dx) for dy, dx in NEI4]
                if c != transparent and all(n == transparent for n in neigh):
                    grid[y][x] = transparent
                    orphans += 1
                    changed += 1
                elif c == transparent and all(n != transparent for n in neigh):
                    grid[y][x] = Counter(neigh).most_common(1)[0][0]
                    holes += 1
                    changed += 1
        if not changed:
            break
    return orphans, holes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--outline", help="also add a clean 1px outline (legend char)")
    p.add_argument("--smooth", action="store_true",
                   help="also repair 1px contour wobbles (lint 'jaggy': "
                        "shave bumps, fill dents)")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force and args.out != args.sprite:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        rows = parse_pix(args.sprite)
        errs = validate_grid(rows, spec)
        if errs:
            raise SpriteError("; ".join(errs))
        before = detail_score.score(rows, spec)["overall"]
        transparent = str(spec["transparent_char"])
        grid = [list(r) for r in rows]
        orphans, holes = fix(grid, transparent)
        smoothed = 0
        if args.smooth:
            smoothed = smooth_jaggies(grid, transparent)
            if smoothed:                    # shaving can expose new orphans
                o2, h2_ = fix(grid, transparent)
                orphans += o2
                holes += h2_
        outlined = 0
        if args.outline:
            if args.outline not in spec["legend"]:
                raise SpriteError(f"--outline {args.outline!r} not in legend")
            h2, w2 = len(grid), len(grid[0])
            region = {(x, y) for y in range(h2) for x in range(w2)
                      if grid[y][x] != transparent}
            for (x, y) in region:
                if any((x + dx, y + dy) not in region for dx, dy in NEI4):
                    if grid[y][x] != args.outline:
                        grid[y][x] = args.outline
                        outlined += 1
        out_rows = ["".join(r) for r in grid]
        after = detail_score.score(out_rows, spec)["overall"]
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    write_pix(out_rows, args.out, header=f"autofixed {args.sprite.name}")
    print(f"wrote {args.out}")
    print(f"  removed {orphans} orphan pixel(s), filled {holes} hole(s)"
          + (f", smoothed {smoothed} jaggy(ies)" if args.smooth else "")
          + (f", outlined {outlined} edge pixel(s)" if args.outline else ""))
    print(f"  detail score {before} -> {after}/100")
    return 0


if __name__ == "__main__":
    sys.exit(main())
