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
  - jaggies         : a 1px wobble (bump or dent) on an otherwise flat
                      silhouette contour - the pixel-perfect-curve rule
                      hand-pixelled art follows (autofix --smooth repairs)
  - outline banding : double-thick outline runs along a straight edge when
                      the spec asks for a selective 1px outline

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


def contours(rows, transparent):
    """The four silhouette contours: left/right edge x per row, top/bottom
    edge y per column (None where the row/column is empty)."""
    h, w = len(rows), len(rows[0])
    left = [None] * h
    right = [None] * h
    top = [None] * w
    bot = [None] * w
    for y in range(h):
        for x in range(w):
            if rows[y][x] != transparent:
                if left[y] is None:
                    left[y] = x
                right[y] = x
                if top[x] is None:
                    top[x] = y
                bot[x] = y
    return {"left": left, "right": right, "top": top, "bot": bot}


def find_jaggies(rows, transparent):
    """1px wobbles on a flat contour: v,v,(v+-1),v,v - the isolated bump or
    dent that breaks a pixel-perfect line. Returns (name, index, kind) where
    kind is 'bump' (sticks out) or 'dent' (bites in)."""
    out = []
    cts = contours(rows, transparent)
    sticks_out = {"left": -1, "right": 1, "top": -1, "bot": 1}
    for name, seq in cts.items():
        n = len(seq)
        for i in range(1, n - 1):
            a, v, b = seq[i - 1], seq[i], seq[i + 1]
            if a is None or v is None or b is None:
                continue
            if a != b or abs(v - a) != 1:
                continue
            # demand flatness one step further out when available
            if i - 2 >= 0 and seq[i - 2] is not None and seq[i - 2] != a:
                continue
            if i + 2 < n and seq[i + 2] is not None and seq[i + 2] != b:
                continue
            kind = "bump" if (v - a) == sticks_out[name] else "dent"
            out.append((name, i, kind))
    return out


def find_outline_banding(rows, transparent, outline):
    """Double-thick outline pixels along STRAIGHT silhouette edges (corners
    are exempt - a corner legitimately doubles). Returns their coords."""
    h, w = len(rows), len(rows[0])
    hits = []
    for y in range(h):
        for x in range(w):
            if rows[y][x] != outline:
                continue
            open_dirs = [(dx, dy) for dx, dy in NEI4
                         if not (0 <= x + dx < w and 0 <= y + dy < h)
                         or rows[y + dy][x + dx] == transparent]
            if len(open_dirs) != 1:           # straight edge only
                continue
            dx, dy = open_dirs[0]
            ix, iy = x - dx, y - dy           # one pixel inward
            if 0 <= ix < w and 0 <= iy < h and rows[iy][ix] == outline:
                hits.append((x, y))
    return hits


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

    # pixel-perfect-curve discipline: isolated 1px contour wobbles
    jags = find_jaggies(rows, transparent)
    for name, i, kind in jags[:12]:
        axis = "row" if name in ("left", "right") else "col"
        findings.append(f"jaggy: 1px {kind} on the {name} contour at "
                        f"{axis} {i} (autofix --smooth repairs)")
    if len(jags) > 12:
        findings.append(f"jaggy: ... and {len(jags) - 12} more contour "
                        f"wobble(s)")

    # outline banding: double-thick outline along straight edges
    if outline and spec.get("outline", {}).get("style", "").startswith(
            "selective"):
        band = find_outline_banding(rows, transparent, outline)
        if len(band) >= 3:
            head = ", ".join(f"({x},{y})" for x, y in band[:4])
            findings.append(f"outline banding: {len(band)} double-thick "
                            f"outline pixel(s) on straight edges (e.g. "
                            f"{head}) - spec asks selective-1px")

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
