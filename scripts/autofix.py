#!/usr/bin/env python3
"""Apply safe automatic cleanups to a .pix to raise its quality.

Usage:
    autofix.py sprite.pix --spec pixy.spec.json --out clean.pix

Fixes only unambiguous craft defects - no artistic guessing:
  - orphan pixels (a solid pixel fully surrounded by transparent) -> removed
  - single-pixel holes (transparent fully surrounded by solid) -> filled with
    the majority neighbor color

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

NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


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
        grid = [list(r) for r in rows]
        orphans, holes = fix(grid, str(spec["transparent_char"]))
        out_rows = ["".join(r) for r in grid]
        after = detail_score.score(out_rows, spec)["overall"]
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    write_pix(out_rows, args.out, header=f"autofixed {args.sprite.name}")
    print(f"wrote {args.out}")
    print(f"  removed {orphans} orphan pixel(s), filled {holes} hole(s)")
    print(f"  detail score {before} -> {after}/100")
    return 0


if __name__ == "__main__":
    sys.exit(main())
