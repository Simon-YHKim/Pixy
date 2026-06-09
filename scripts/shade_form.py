#!/usr/bin/env python3
"""Shade a flat region into a 3D-looking form with a light model.

Usage:
    shade_form.py in.pix --spec spec.json --region g --ramp "p,D,b,c,W" \\
        --form sphere --light tl --rim --ao --out shaded.pix

This is the quality engine. Authoring volume pixel by pixel is what makes
LLM output look like a doodle; instead, block a flat silhouette (one base
color) with draw_pix, then let this apply directional shading so the shape
reads as a sphere, cylinder, or bevel - the difference between a flat blob
and finished pixel art.

It recolors every pixel of --region using --ramp (dark->light legend chars)
according to a per-pixel light value from the chosen --form and --light
direction. --rim adds a bright lit edge, --ao darkens shaded edges, --dither
checkerboards between ramp steps for smooth gradients. All output stays in
the locked palette.

Forms:   flat | sphere | cyl-v | cyl-h | round
Lights:  tl tr bl br t b l r

Exit codes: 0 = written, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, write_pix  # noqa: E402

LIGHTS = {"tl": (-1, -1), "tr": (1, -1), "bl": (-1, 1), "br": (1, 1),
          "t": (0, -1), "b": (0, 1), "l": (-1, 0), "r": (1, 0)}
NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def light_value(x, y, cx, cy, rx, ry, form, lx, ly, lz):
    """Return a 0..1 brightness for a pixel under the given form and light."""
    nx = (x - cx) / rx if rx else 0.0
    ny = (y - cy) / ry if ry else 0.0
    if form == "sphere":
        r2 = min(1.0, nx * nx + ny * ny)
        nz = math.sqrt(1.0 - r2)
        lam = nx * lx + ny * ly + nz * lz
    elif form == "cyl-v":            # vertical cylinder: varies across x
        cxn = min(1.0, abs(nx))
        nz = math.sqrt(1.0 - cxn * cxn)
        lam = nx * lx + nz * lz
    elif form == "cyl-h":            # horizontal cylinder: varies down y
        cyn = min(1.0, abs(ny))
        nz = math.sqrt(1.0 - cyn * cyn)
        lam = ny * ly + nz * lz
    else:                            # flat / round: directional gradient
        lam = (-nx) * (-lx) + (-ny) * (-ly)  # toward light = brighter
        lam = lam / math.sqrt(lx * lx + ly * ly + 1e-9)
    # map lambert [-1,1] -> [0,1]
    return max(0.0, min(1.0, 0.5 + 0.5 * lam))


def edge_distance(region, w, h):
    """Chebyshev distance from each region pixel to the nearest non-region."""
    INF = 10 ** 9
    dist = {}
    frontier = []
    for (x, y) in region:
        is_edge = any((x + dx, y + dy) not in region
                      for dx, dy in NEI4)
        if is_edge:
            dist[(x, y)] = 1
            frontier.append((x, y))
        else:
            dist[(x, y)] = INF
    i = 0
    while i < len(frontier):
        x, y = frontier[i]
        i += 1
        for dx, dy in NEI4:
            n = (x + dx, y + dy)
            if n in region and dist[n] > dist[(x, y)] + 1:
                dist[n] = dist[(x, y)] + 1
                frontier.append(n)
    return dist


def shade(grid, region_char, ramp, form, light, rim, ao, dither, rim_char,
          outline_char=None):
    h, w = len(grid), len(grid[0])
    region = {(x, y) for y in range(h) for x in range(w)
              if grid[y][x] == region_char}
    if not region:
        raise SpriteError(f"region char {region_char!r} not found in grid")
    xs = [p[0] for p in region]
    ys = [p[1] for p in region]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    rx = max(1.0, (max(xs) - min(xs)) / 2)
    ry = max(1.0, (max(ys) - min(ys)) / 2)
    lx, ly = LIGHTS[light]
    norm = math.sqrt(lx * lx + ly * ly) or 1.0
    lx3, ly3, lz3 = lx / norm * 0.78, ly / norm * 0.78, 0.62
    n = len(ramp)

    dist = edge_distance(region, w, h) if form == "round" else None
    maxd = max(dist.values()) if dist else 1

    for (x, y) in region:
        v = light_value(x, y, cx, cy, rx, ry, form, lx3, ly3, lz3)
        if form == "round":          # puffy: center bright, edges dark
            v = 0.45 * v + 0.55 * (dist[(x, y)] / maxd)
        # Tighten the highlight: a gamma curve keeps the brightest tone a
        # small specular instead of washing half the form white.
        f = (v ** 2.0) * (n - 1)
        idx = int(round(f))
        idx = max(0, min(n - 1, idx))
        # Reserve the top tone for a true specular (only the brightest pixels).
        if idx == n - 1 and v < 0.93:
            idx = n - 2
        ch = ramp[idx]
        if dither and 0 < idx < n - 1:
            frac = f - idx
            if abs(frac) > 0.25:
                hi = ramp[min(n - 1, idx + (1 if frac > 0 else -1))]
                ch = hi if (x + y) % 2 == 0 else ch
        grid[y][x] = ch

    # ambient occlusion: darken region edges away from the light
    if ao:
        for (x, y) in list(region):
            if any((x + dx, y + dy) not in region for dx, dy in NEI4):
                # only shade-side edges (not the lit edge)
                toward = (x + (1 if lx > 0 else -1 if lx < 0 else 0),
                          y + (1 if ly > 0 else -1 if ly < 0 else 0))
                if toward in region:   # this edge faces away from light
                    cur = grid[y][x]
                    if cur in ramp:
                        i = ramp.index(cur)
                        grid[y][x] = ramp[max(0, i - 1)]
    # reflected/rim light: lift the shadow-side edge by a subtle amount
    # (one step below the brightest tone, not pure highlight)
    if rim:
        rc = rim_char or ramp[max(0, n - 2)]
        for (x, y) in list(region):
            away = (x - (1 if lx > 0 else -1 if lx < 0 else 0),
                    y - (1 if ly > 0 else -1 if ly < 0 else 0))
            if away not in region:     # nothing toward the light = lit edge
                grid[y][x] = rc
    # solid outline: every region pixel touching the background becomes the
    # outline char - a clean, consistent 1px dark edge on every shaded form
    if outline_char:
        for (x, y) in region:
            if any((x + dx, y + dy) not in region for dx, dy in NEI4):
                grid[y][x] = outline_char
    return grid


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path, help="input .pix (flat silhouette)")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--region", required=True, help="base char to shade")
    p.add_argument("--ramp", help="dark->light legend chars, comma-separated")
    p.add_argument("--material", help="named ramp from the spec's shading block "
                                      "(e.g. gold, blue, default)")
    p.add_argument("--form", choices=("flat", "sphere", "cyl-v", "cyl-h",
                                      "round"), default="round")
    p.add_argument("--light", choices=tuple(LIGHTS), default=None)
    p.add_argument("--rim", action="store_true", help="bright lit edge")
    p.add_argument("--rim-char", help="char for the rim (default: ramp top)")
    p.add_argument("--ao", action="store_true", help="darken shaded edges")
    p.add_argument("--dither", action="store_true", help="dither ramp steps")
    p.add_argument("--outline", help="legend char for a clean 1px edge")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        sh = spec.get("shading", {})
        # ramp: --ramp wins, else --material from the spec's locked ramps
        if args.ramp:
            ramp = [c.strip() for c in args.ramp.split(",") if c.strip()]
        elif args.material:
            mats = sh.get("materials", {})
            if args.material not in mats:
                raise SpriteError(f"material {args.material!r} not in spec "
                                  f"shading.materials {sorted(mats)}")
            ramp = list(mats[args.material])
        else:
            raise SpriteError("provide --ramp or --material")
        if len(ramp) < 2:
            raise SpriteError("ramp needs at least 2 chars")
        # light/outline default from the spec's locked shading style
        light = args.light or sh.get("light", "tl")
        outline = args.outline if args.outline is not None else sh.get("outline")
        allowed = set(spec["legend"]) | {str(spec["transparent_char"])}
        extra = ([args.rim_char] if args.rim_char else []) \
            + ([outline] if outline else [])
        bad = [c for c in ramp + extra if c not in allowed]
        if bad:
            raise SpriteError(f"ramp/rim/outline chars not in legend: "
                              f"{sorted(set(bad))}")
        if len(args.region) != 1:
            raise SpriteError("--region must be a single char")
        rows = parse_pix(args.sprite)
        grid = [list(r) for r in rows]
        shade(grid, args.region, ramp, args.form, light,
              args.rim, args.ao, args.dither, args.rim_char, outline)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    out_rows = ["".join(r) for r in grid]
    write_pix(out_rows, args.out, header=f"shaded {args.form} from "
              f"{args.sprite.name}")
    print(f"wrote {args.out}  ({len(out_rows[0])}x{len(out_rows)} grid, "
          f"{args.form} light={light})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
