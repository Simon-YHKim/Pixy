#!/usr/bin/env python3
"""Score how uniform an asset SET is (0-100) and flag the odd ones out.

Usage:
    consistency_report.py *.pix --spec pixy.spec.json

The spec already locks canvas and palette, so this measures the variance that
remains and breaks consistency in practice: detail spread (are some assets far
more/less finished than others), outline coverage (is the dark edge applied
the same way), and palette overlap (do they draw from the same colors). Prints
a per-asset line, an overall uniformity score, and the outliers to redo.

Exit codes: 0 = reported, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402
import detail_score  # noqa: E402

NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def asset_stats(rows, spec):
    h, w = len(rows), len(rows[0])
    transparent = str(spec["transparent_char"])
    outline_char = spec.get("shading", {}).get("outline") \
        or spec.get("outline", {}).get("char")
    region = {(x, y) for y in range(h) for x in range(w)
              if rows[y][x] != transparent}
    used = frozenset(rows[y][x] for (x, y) in region)
    edge = [(x, y) for (x, y) in region
            if any((x + dx, y + dy) not in region for dx, dy in NEI4)]
    outlined = sum(1 for (x, y) in edge if rows[y][x] == outline_char)
    outline_cov = (outlined / len(edge)) if edge else 0.0
    score = detail_score.score(rows, spec)["overall"]
    return {"used": used, "outline": outline_cov, "score": score}


def jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 1.0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprites", type=Path, nargs="+")
    p.add_argument("--spec", type=Path, required=True)
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
        stats = {}
        for sp in args.sprites:
            rows = parse_pix(sp)
            errs = validate_grid(rows, spec)
            if errs:
                raise SpriteError(f"{sp}: {'; '.join(errs)}")
            stats[sp] = asset_stats(rows, spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if len(stats) < 2:
        print("note: need 2+ assets to assess set consistency", file=sys.stderr)

    scores = [s["score"] for s in stats.values()]
    outs = [s["outline"] for s in stats.values()]
    palettes = [s["used"] for s in stats.values()]
    # average pairwise palette overlap
    pairs = [jaccard(palettes[i], palettes[j])
             for i in range(len(palettes)) for j in range(i + 1, len(palettes))]
    pal_overlap = sum(pairs) / len(pairs) if pairs else 1.0
    detail_uniform = max(0.0, 1 - stdev(scores) / 30.0)
    outline_avg = sum(outs) / len(outs)
    uniformity = round(100 * (0.4 * detail_uniform + 0.3 * outline_avg
                              + 0.3 * pal_overlap))

    for sp, s in stats.items():
        print(f"  {sp.name}: detail {s['score']}, outline "
              f"{s['outline']*100:.0f}%, {len(s['used'])} colors")
    avg = sum(scores) / len(scores)
    print(f"\nuniformity: {uniformity}/100  "
          f"(detail spread sigma {stdev(scores):.0f}, outline "
          f"{outline_avg*100:.0f}%, palette overlap {pal_overlap*100:.0f}%)")
    outliers = [sp.name for sp, s in stats.items()
                if s["score"] < avg - 15 or s["outline"] < outline_avg - 0.25]
    if outliers:
        print("  redo for consistency: " + ", ".join(outliers))
    else:
        print("  set is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
