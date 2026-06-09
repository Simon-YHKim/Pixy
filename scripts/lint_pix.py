#!/usr/bin/env python3
"""Lint a .pix grid for common pixel-art quality problems.

Usage:
    lint_pix.py sprite.pix --spec pixy.spec.json [--strict]

Goes beyond check_sprite's hard rules (size/palette/transparency) to flag
craft issues that read as sloppy:
  - orphan pixels   : a solid pixel whose 4 neighbors are all transparent
  - single-pixel holes : a transparent pixel fully surrounded by solid
  - thin outline gaps : an outline-colored pixel with no adjacent outline
                        pixel (a broken 1px outline)

These are warnings by default (exit 0). With --strict, any finding fails
(exit 1) so it can gate a pipeline. check_sprite.py should pass first.

Exit codes: 0 = clean (or warnings only), 1 = findings with --strict,
2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402

NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def lint(rows, spec, tileable=False, max_colors=None):
    h, w = len(rows), len(rows[0])
    transparent = str(spec["transparent_char"])
    outline = spec.get("outline", {}).get("char")
    findings = []

    def at(y, x):
        # Toroidal wrap for tile seamlessness; otherwise off-grid is empty.
        if tileable:
            return rows[y % h][x % w]
        if 0 <= y < h and 0 <= x < w:
            return rows[y][x]
        return transparent

    for y in range(h):
        for x in range(w):
            c = rows[y][x]
            neigh = [at(y + dy, x + dx) for dy, dx in NEI4]
            if c != transparent:
                if all(n == transparent for n in neigh):
                    findings.append(f"orphan pixel '{c}' at ({x},{y})"
                                    + (" (even when tiled)" if tileable else ""))
                if outline and c == outline and \
                        all(n != outline for n in neigh):
                    findings.append(f"isolated outline pixel at ({x},{y}) "
                                    f"(possible broken outline)")
            else:
                if all(n != transparent for n in neigh):
                    findings.append(f"single-pixel hole at ({x},{y})"
                                    + (" (seam)" if tileable else ""))

    if max_colors is not None:
        used = {c for row in rows for c in row if c != transparent}
        if len(used) > max_colors:
            findings.append(f"uses {len(used)} colors {sorted(used)} > "
                            f"--max-colors {max_colors}")
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path, help="path to .pix")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--strict", action="store_true", help="exit 1 on findings")
    p.add_argument("--tileable", action="store_true",
                   help="check seamless tiling (wrap edges) for tiles")
    p.add_argument("--max-colors", dest="max_colors", type=int,
                   help="warn if more than N palette colors are used")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
        rows = parse_pix(args.sprite)
        hard = validate_grid(rows, spec)
        if hard:
            print(f"error: fix check_sprite issues first "
                  f"({len(hard)} found)", file=sys.stderr)
            for e in hard:
                print(f"  - {e}", file=sys.stderr)
            return 2
        findings = lint(rows, spec, tileable=args.tileable,
                        max_colors=args.max_colors)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not findings:
        print(f"clean: {args.sprite} - no lint findings")
        return 0

    stream = sys.stderr if args.strict else sys.stdout
    print(f"{'FAIL' if args.strict else 'lint'}: {args.sprite} "
          f"({len(findings)} finding(s))", file=stream)
    for f in findings:
        print(f"  - {f}", file=stream)
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
