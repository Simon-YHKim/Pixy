#!/usr/bin/env python3
"""Measure and enforce an asset's proportions against the spec frame.

Usage:
    proportions.py hero.pix --spec pixy.spec.json            # measure + check
    proportions.py hero.pix --spec pixy.spec.json --fit --out hero.pix

The spec's `frame` block stores the shared layout: safe-area margin, baseline
(where feet sit), center axis, target content height, pivot, and whether the
subject is symmetric. This reports how the asset's real proportions (bounding
box, margins, centering, baseline gap, symmetry) deviate from that frame, so a
set stays uniform in size and placement, not just palette. `--fit` recenters
the content on the axis and drops it onto the baseline (a safe pixel shift; it
never resamples the art).

Exit codes: 0 = ok (or measured), 1 = deviations with --strict, 2 = usage/IO.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid, write_pix  # noqa: E402


def bbox(rows, transparent):
    xs, ys = [], []
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != transparent:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def measure(rows, spec):
    h, w = len(rows), len(rows[0])
    transparent = str(spec["transparent_char"])
    bb = bbox(rows, transparent)
    if bb is None:
        return None
    minx, miny, maxx, maxy = bb
    cells = [(x, y) for y in range(h) for x in range(w)
             if rows[y][x] != transparent]
    mirror = sum(1 for (x, y) in cells if rows[y][w - 1 - x] != transparent)
    return {
        "content_h": (maxy - miny + 1) / h,
        "content_w": (maxx - minx + 1) / w,
        "center_x": ((minx + maxx) / 2 + 0.5) / w,
        "bottom": (maxy + 1) / h,
        "margins": (miny / h, (h - 1 - maxy) / h, minx / w, (w - 1 - maxx) / w),
        "symmetry": mirror / len(cells),
        "bb": bb,
    }


def check(m, frame):
    issues = []
    if abs(m["content_h"] - frame.get("content_height", 0.82)) > 0.12:
        issues.append(f"content height {m['content_h']*100:.0f}% vs target "
                      f"{frame.get('content_height', 0.82)*100:.0f}% (off by "
                      f"{abs(m['content_h']-frame.get('content_height',0.82))*100:.0f}pt)")
    if abs(m["center_x"] - frame.get("center_axis", 0.5)) > 0.06:
        issues.append(f"off-center: content axis {m['center_x']*100:.0f}% vs "
                      f"{frame.get('center_axis', 0.5)*100:.0f}%")
    if abs(m["bottom"] - frame.get("baseline", 0.94)) > 0.05:
        issues.append(f"baseline: content bottom {m['bottom']*100:.0f}% vs "
                      f"{frame.get('baseline', 0.94)*100:.0f}%")
    if min(m["margins"]) < frame.get("margin", 0.06) - 0.005:
        issues.append(f"touches the safe margin (min margin "
                      f"{min(m['margins'])*100:.0f}% < "
                      f"{frame.get('margin', 0.06)*100:.0f}%)")
    if frame.get("symmetry") and m["symmetry"] < 0.85:
        issues.append(f"not symmetric ({m['symmetry']*100:.0f}% mirror match)")
    return issues


def fit(rows, spec):
    h, w = len(rows), len(rows[0])
    transparent = str(spec["transparent_char"])
    frame = spec.get("frame", {})
    bb = bbox(rows, transparent)
    if bb is None:
        return rows
    minx, miny, maxx, maxy = bb
    target_cx = round(frame.get("center_axis", 0.5) * w)
    target_bottom = round(frame.get("baseline", 0.94) * h) - 1
    dx = target_cx - round((minx + maxx) / 2)
    dy = target_bottom - maxy
    # clamp so content stays fully on-canvas
    dx = max(-minx, min(w - 1 - maxx, dx))
    dy = max(-miny, min(h - 1 - maxy, dy))
    out = [[transparent] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            c = rows[y][x]
            if c != transparent:
                out[y + dy][x + dx] = c
    return ["".join(r) for r in out]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--fit", action="store_true", help="recenter + baseline-align")
    p.add_argument("--out", type=Path, help="output for --fit")
    p.add_argument("--strict", action="store_true", help="exit 1 on deviations")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
        rows = parse_pix(args.sprite)
        errs = validate_grid(rows, spec)
        if errs:
            raise SpriteError("; ".join(errs))
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    frame = spec.get("frame", {})

    if args.fit:
        out = args.out or args.sprite
        if out.exists() and not args.force and out != args.sprite:
            print(f"error: {out} exists; pass --force", file=sys.stderr)
            return 2
        write_pix(fit(rows, spec), out, header=f"fitted {args.sprite.name}")
        print(f"wrote {out} (recentered on axis, dropped to baseline)")
        return 0

    m = measure(rows, spec)
    if m is None:
        print("empty sprite", file=sys.stderr)
        return 2
    print(f"{args.sprite.name}: content {m['content_w']*100:.0f}x"
          f"{m['content_h']*100:.0f}% of canvas, axis {m['center_x']*100:.0f}%, "
          f"bottom {m['bottom']*100:.0f}%, symmetry {m['symmetry']*100:.0f}%")
    issues = check(m, frame)
    if issues:
        for i in issues:
            print(f"  - {i}")
        print("  (use --fit to recenter/baseline-align)")
        return 1 if args.strict else 0
    print("  proportions match the frame.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
