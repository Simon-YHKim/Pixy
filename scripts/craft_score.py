#!/usr/bin/env python3
"""Score how much an asset reads as hand-made retro pixel CRAFT (0-100).

Usage:
    craft_score.py asset.pix --spec pixy.spec.json [--json] [--brief]

detail_score measures *finish signals* (tones, range, size); this measures
*discipline* - the rules a period pixel artist follows. It exists so a
code-only (no vision) agent can self-QA a conform/authored asset and decide
what to fix or how to regenerate, headlessly:

    jaggy_free   - pixel-perfect contours (no 1px wobbles)
    band_free    - no double-thick outline bands on straight edges
    flat_purity  - flat areas are flat (no low-contrast speckle)
    edge_def     - the silhouette is defined: outline char OR a darker
                   self-tone (sel-out) on nearly every edge pixel
    light_ok     - highlights sit toward the spec's light direction
    dither_disc  - any dithering is a regular checker weave, not noise
    on_ramp      - colors used belong to the spec's material ramps

Each metric prints with a concrete fix command. --brief emits a short
regeneration brief for an LLM/image-model retry. Exit 0 = scored,
2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402
import lint_pix  # noqa: E402

WEIGHTS = {"jaggy_free": 0.18, "band_free": 0.12, "flat_purity": 0.20,
           "edge_def": 0.16, "light_ok": 0.12, "dither_disc": 0.12,
           "on_ramp": 0.10}
NEI8 = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
             if not (dx == 0 and dy == 0))


def _lum(legend, ch):
    v = legend.get(ch)
    if not v or not str(v).startswith("#"):   # old specs: ".": "transparent"
        return None
    return (0.299 * int(v[1:3], 16) + 0.587 * int(v[3:5], 16)
            + 0.114 * int(v[5:7], 16))


def _dist2(legend, a, b):
    va, vb = legend.get(a), legend.get(b)
    if not va or not vb:
        return 10 ** 9
    return sum((int(va[i:i + 2], 16) - int(vb[i:i + 2], 16)) ** 2
               for i in (1, 3, 5))


def _perimeter(rows, transparent):
    h, w = len(rows), len(rows[0])
    per = 0
    for y in range(h):
        for x in range(w):
            if rows[y][x] == transparent:
                continue
            if any(not (0 <= x + dx < w and 0 <= y + dy < h)
                   or rows[y + dy][x + dx] == transparent
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                per += 1
    return per


def _speckle_and_weave(rows, spec):
    """Count true speckle pixels (lonely low-contrast strays on flat areas)
    and weave pixels (part of a regular ABAB checker run >=4)."""
    h, w = len(rows), len(rows[0])
    transparent = str(spec["transparent_char"])
    legend = spec["legend"]
    speckle = 0
    weave = set()
    for y in range(h):
        row = rows[y]
        for x in range(w):
            c = row[x]
            if c == transparent:
                continue
            # weave membership: horizontal or vertical ABAB run of length 4
            for ax, ay in ((1, 0), (0, 1)):
                ok = True
                pair = None
                for k in range(4):
                    xx, yy = x + ax * k, y + ay * k
                    if not (0 <= xx < w and 0 <= yy < h):
                        ok = False
                        break
                    v = rows[yy][xx]
                    if v == transparent:
                        ok = False
                        break
                    if k == 0:
                        a = v
                    elif k == 1:
                        if v == a:
                            ok = False
                            break
                        pair = v
                    elif v != (a if k % 2 == 0 else pair):
                        ok = False
                        break
                if ok:
                    for k in range(4):
                        weave.add((x + ax * k, y + ay * k))
            # speckle: <=1 like-neighbour, a dominant other color (>=5 of 8)
            # within ramp distance (low contrast = quantization stray)
            cnt: dict[str, int] = {}
            same = 0
            for dx, dy in NEI8:
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    n = rows[yy][xx]
                    if n == transparent:
                        continue
                    cnt[n] = cnt.get(n, 0) + 1
                    if n == c:
                        same += 1
            if cnt:
                mc = max(cnt, key=cnt.get)
                if same <= 1 and mc != c and cnt[mc] >= 5 \
                        and _dist2(legend, c, mc) <= 150 * 150 \
                        and (x, y) not in weave:
                    speckle += 1
    return speckle, len(weave)


def _edge_definition(rows, spec):
    """Fraction of silhouette-edge pixels that are 'defined': the outline
    char, or darker than their inward neighbour (sel-out). Covers both
    outline modes with one number."""
    h, w = len(rows), len(rows[0])
    transparent = str(spec["transparent_char"])
    legend = spec["legend"]
    outline = spec.get("shading", {}).get("outline") \
        or spec.get("outline", {}).get("char")
    edge = defined = 0
    for y in range(h):
        for x in range(w):
            c = rows[y][x]
            if c == transparent:
                continue
            open_dirs = [(dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1),
                                                 (0, -1))
                         if not (0 <= x + dx < w and 0 <= y + dy < h)
                         or rows[y + dy][x + dx] == transparent]
            if not open_dirs:
                continue
            edge += 1
            if outline and c == outline:
                defined += 1
                continue
            dx, dy = open_dirs[0]
            ix, iy = x - dx, y - dy
            if 0 <= ix < w and 0 <= iy < h and rows[iy][ix] != transparent:
                cl, il = _lum(legend, c), _lum(legend, rows[iy][ix])
                if cl is not None and il is not None and cl < il - 8:
                    defined += 1
    return (defined / edge) if edge else 1.0, edge


def score(rows, spec):
    transparent = str(spec["transparent_char"])
    legend = spec["legend"]
    per = max(1, _perimeter(rows, transparent))

    jags = lint_pix.find_jaggies(rows, transparent)
    outline = spec.get("shading", {}).get("outline") \
        or spec.get("outline", {}).get("char")
    band = lint_pix.find_outline_banding(rows, transparent, outline) \
        if outline else []
    speckle, weave = _speckle_and_weave(rows, spec)
    edge_def, edge_n = _edge_definition(rows, spec)
    agree = lint_pix.light_agreement(rows, spec)
    opaque = sum(1 for r in rows for c in r if c != transparent)

    used = {c for r in rows for c in r if c != transparent}
    mats = spec.get("shading", {}).get("materials", {})
    on_ramp_set = {c for ramp in mats.values() for c in ramp}
    on_ramp = (len(used & on_ramp_set) / len(used)) if used and on_ramp_set \
        else 1.0

    m = {
        "jaggy_free": max(0.0, 1 - len(jags) / max(1.0, per * 0.04)),
        "band_free": max(0.0, 1 - len(band) / max(1.0, per * 0.06)),
        "flat_purity": max(0.0, 1 - speckle / max(1.0, opaque * 0.02)),
        "edge_def": min(1.0, edge_def / 0.85),
        "light_ok": 0.75 if agree is None
        else max(0.0, min(1.0, (agree + 1) / 1.4)),
        # only judge dither REGULARITY when dithering is actually present
        # (weave>0); stray speckle without any weave is flat_purity's domain,
        # not "noisy dither" - accusing a no-dither cel sprite of bad
        # dithering contradicts Iron Rule 7
        "dither_disc": 1.0 if weave == 0
        else weave / (weave + speckle * 4),
        "on_ramp": on_ramp,
    }
    outline_share = (sum(r.count(outline) for r in rows) / opaque) \
        if (outline and opaque) else 0.0
    overall = round(100 * sum(WEIGHTS[k] * m[k] for k in WEIGHTS))
    if outline_share > 0.5:
        # an "asset" that is mostly outline char is a destroyed silhouette
        # (e.g. shade_form's outline consumed a thin region) - never let the
        # per-axis metrics call that solid
        overall = min(overall, 55)
    grade = ("craft" if overall >= 88 else "solid" if overall >= 72
             else "rough" if overall >= 50 else "machine-y")

    sug = []
    if outline_share > 0.5:
        sug.append(f"outline char is {outline_share*100:.0f}% of the sprite "
                   f"- the fill was consumed (re-shade with --outline '' "
                   f"or chunkier geometry)")
    if m["jaggy_free"] < 0.85:
        sug.append(f"{len(jags)} contour wobble(s): autofix --smooth")
    if m["band_free"] < 0.85 and len(band) >= 3:
        # same bar as lint_pix: 1-2 doubled px on a small sprite is noise,
        # not a band - do not suggest a repair lint will never report
        sug.append(f"{len(band)}px double outline: autofix --selout "
                   f"(.pix) / imageify --outline-mode selout (re-conform)")
    if m["flat_purity"] < 0.85:
        sug.append(f"{speckle} speckle px on flat areas: imageify --denoise "
                   f"med|high (re-conform) or autofix")
    if m["edge_def"] < 0.8:
        sug.append(f"only {edge_def*100:.0f}% of the edge is defined: "
                   f"autofix --outline (adds outward) then --selout, or "
                   f"re-conform with imageify --outline spec")
    if m["light_ok"] < 0.5 and agree is not None:
        sug.append("highlights oppose the spec light: shade_form --light "
                   + str(spec.get("shading", {}).get("light", "tl"))
                   + " or flip")
    if m["dither_disc"] < 0.7 and weave > 0:
        sug.append("noisy (FS-like) dither: re-conform with --dither-mode "
                   "ordered, or --denoise to flatten")
    if m["on_ramp"] < 0.7 and on_ramp_set:
        sug.append("colors stray off the material ramps: recolor toward the "
                   "spec ramps (transform_pix --recolor)")
    if not sug:
        sug.append("Disciplined across the board.")
    return {"overall": overall, "grade": grade, "metrics": m,
            "suggestions": sug,
            "counts": {"jaggies": len(jags), "banding": len(band),
                       "speckle": speckle, "weave": weave,
                       "edge_defined": round(edge_def, 3),
                       "light_agreement": None if agree is None
                       else round(agree, 3)}}


def brief(result, spec):
    """A short regeneration brief a code-only agent can hand to the image
    model / its own next attempt."""
    lines = [f"Retro-craft {result['overall']}/100 ({result['grade']}). "
             f"Regenerate with these constraints:"]
    light = spec.get("shading", {}).get("light", "tl")
    lines.append(f"- one light source from {light}; flat color planes; "
                 f"no noisy dithering (checker weave only)")
    lines.append("- crisp 1px silhouette (selective outline ok); no stray "
                 "pixels on flat areas; pixel-perfect curves")
    for s in result["suggestions"]:
        if not s.startswith("Disciplined"):
            lines.append(f"- fix: {s}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprites", type=Path, nargs="+")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--json", action="store_true")
    p.add_argument("--brief", action="store_true",
                   help="emit a regeneration brief instead of the card")
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
        except SpriteError as e:
            print(f"error: {sp}: {e}", file=sys.stderr)
            return 2
        results[str(sp)] = score(rows, spec)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    for path, r in results.items():
        if args.brief:
            print(brief(r, spec))
            continue
        print(f"{path}: {r['overall']}/100 ({r['grade']})")
        print("  " + "  ".join(f"{k} {r['metrics'][k]*100:.0f}"
                               for k in WEIGHTS))
        for s in r["suggestions"]:
            print(f"  - {s}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
