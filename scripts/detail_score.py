#!/usr/bin/env python3
"""Score the detail / finish quality of a .pix asset (0-100).

Usage:
    detail_score.py sprite.pix --spec pixy.spec.json
    detail_score.py *.pix --spec pixy.spec.json          # set summary too
    detail_score.py sprite.pix --spec pixy.spec.json --json

Gives the user a concrete read on how detailed an asset is, so a regeneration
request can be specific ("more shading", "add an outline", "go bigger"). The
score is a transparent weighted blend of measurable signals - it does not
judge artistic taste, only the presence of the things that make pixel art
read as finished rather than flat.

Metrics (each 0-1, shown in the card):
    shading    - distinct tones beyond the outline (volume)
    range      - light-to-dark spread of the colors used (dynamic range)
    palette    - how many palette colors are used (richness)
    outline    - fraction of the silhouette edge that is the outline char
    resolution - native canvas area vs a 48x48 detail baseline
    clean      - absence of orphan/noise pixels
    coverage   - silhouette fills a sensible part of the canvas

Exit codes: 0 = scored, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402
import lint_pix  # noqa: E402

# Weights sum to 1.0. Shading and dynamic range matter most because they are
# what separate a flat blob from a finished form; coverage matters least.
WEIGHTS = {"shading": 0.24, "range": 0.20, "palette": 0.16, "outline": 0.16,
           "resolution": 0.10, "clean": 0.09, "coverage": 0.05}
NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def luminance(hexv):
    h = hexv.lstrip("#")
    return 0.299 * int(h[0:2], 16) + 0.587 * int(h[2:4], 16) + 0.114 * int(h[4:6], 16)


def tent(v, lo, hi):
    """1.0 inside [lo,hi], falling linearly to 0 outside - for 'sensible' ranges."""
    if lo <= v <= hi:
        return 1.0
    if v < lo:
        return max(0.0, v / lo) if lo else 0.0
    return max(0.0, 1.0 - (v - hi) / (1.0 - hi)) if hi < 1 else 1.0


def score(rows, spec):
    h, w = len(rows), len(rows[0])
    area = w * h
    transparent = str(spec["transparent_char"])
    legend = spec["legend"]
    outline_char = spec.get("shading", {}).get("outline") \
        or spec.get("outline", {}).get("char")

    region = {(x, y) for y in range(h) for x in range(w)
              if rows[y][x] != transparent}
    used = {rows[y][x] for (x, y) in region}
    pixels = len(region)
    if pixels == 0:
        return {"overall": 0, "metrics": {k: 0.0 for k in WEIGHTS},
                "grade": "empty", "suggestions": ["The grid is empty."]}

    used_lums = [luminance(legend[c]) for c in used if c in legend]
    non_outline = [c for c in used if c != outline_char]

    edge = [(x, y) for (x, y) in region
            if any((x + dx, y + dy) not in region for dx, dy in NEI4)]
    outlined = sum(1 for (x, y) in edge if rows[y][x] == outline_char)
    orphans = sum(1 for f in lint_pix.lint(rows, spec) if "orphan" in f)

    m = {
        "shading": min(1.0, len(non_outline) / 4.0),
        "range": (max(used_lums) - min(used_lums)) / 255.0 if used_lums else 0.0,
        "palette": min(1.0, len(used) / 8.0),
        "outline": (outlined / len(edge)) if edge else 0.0,
        "resolution": min(1.0, area / (48 * 48)),
        "clean": 1.0 - min(1.0, orphans / max(1.0, pixels * 0.03)),
        "coverage": tent(pixels / area, 0.18, 0.75),
    }
    overall = round(100 * sum(WEIGHTS[k] * m[k] for k in WEIGHTS))
    grade = ("rich" if overall >= 90 else "detailed" if overall >= 75
             else "shaded" if overall >= 55 else "basic" if overall >= 35
             else "flat/blocky")

    sug = []
    if m["shading"] < 0.5:
        sug.append("Low shading: add volume with shade_form (sphere/cyl forms) "
                   "or use a 3-5 tone ramp; don't leave regions flat.")
    if m["range"] < 0.45:
        sug.append("Low dynamic range: include a near-dark shadow and a "
                   "near-white highlight tone from the ramp.")
    if m["outline"] < 0.6 and outline_char:
        sug.append(f"Weak outline: only {m['outline']*100:.0f}% of the edge is "
                   f"the outline char {outline_char!r}; add shade_form --outline "
                   f"{outline_char}.")
    if m["resolution"] < 0.6:
        sug.append("Small canvas limits detail: use a 48px+ spec "
                   "(icon-hd/portrait/emblem presets) for detailed work.")
    if m["clean"] < 0.8:
        sug.append(f"{orphans} orphan pixel(s): clean with lint_pix --strict.")
    if m["coverage"] < 0.6:
        frac = pixels / area
        sug.append(f"Coverage {frac*100:.0f}% is {'low' if frac < 0.18 else 'high'}; "
                   f"size the subject to fill ~20-70% of the canvas.")
    if not sug:
        sug.append("Solid detail across the board.")
    return {"overall": overall, "metrics": m, "grade": grade,
            "suggestions": sug, "colors_used": len(used), "pixels": pixels}


def print_card(path, r):
    print(f"{path}: {r['overall']}/100 ({r['grade']})")
    bar = "  " + "  ".join(f"{k} {r['metrics'][k]*100:.0f}" for k in WEIGHTS)
    print(bar)
    for s in r["suggestions"]:
        print(f"  - {s}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprites", type=Path, nargs="+", help=".pix file(s)")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--json", action="store_true", help="JSON output")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    results = {}
    for sp in args.sprites:
        try:
            rows = parse_pix(sp)
            errs = validate_grid(rows, spec)
            if errs:
                raise SpriteError("; ".join(errs))
            results[str(sp)] = score(rows, spec)
        except SpriteError as e:
            print(f"error: {sp}: {e}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    for path, r in results.items():
        print_card(path, r)
        print()
    print("note: this scores measurable finish signals (shading, range, "
          "outline, size) - not artistry, form, or readability. A flat blob "
          "can score 'detailed'; judge the render too. For reference-level "
          "fidelity use the image-first path (generate_pixel.py / imageify.py).")
    if len(results) > 1:
        scores = [r["overall"] for r in results.values()]
        avg = sum(scores) / len(scores)
        print(f"set: {len(scores)} assets, average {avg:.0f}/100 "
              f"(min {min(scores)}, max {max(scores)})")
        outliers = [p for p, r in results.items() if r["overall"] < avg - 15]
        if outliers:
            print("  uneven detail (well below the set average): "
                  + ", ".join(Path(o).name for o in outliers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
