#!/usr/bin/env python3
"""Reskin one .pix into several palette/material variants.

Usage:
    variants.py hero.pix --spec pixy.spec.json --materials blue,green,red \\
        --out-dir variants

Maps the asset's colors (ordered by luminance) onto each target material ramp
(also ordered by luminance), so a red enemy becomes a blue/green/etc. one
while keeping the same shapes and the locked palette. Writes one .pix per
material. Great for enemy color-swaps and item rarities, all consistent.

Materials come from the spec's shading.materials (e.g. gold, blue, green,
red, purple, brown, grey). Exit codes: 0 = written, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid, write_pix  # noqa: E402


def lum(hexv):
    h = hexv.lstrip("#")
    return 0.299 * int(h[0:2], 16) + 0.587 * int(h[2:4], 16) + 0.114 * int(h[4:6], 16)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--materials", required=True, help="comma-separated names")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
        rows = parse_pix(args.sprite)
        errs = validate_grid(rows, spec)
        if errs:
            raise SpriteError("; ".join(errs))
        mats = spec.get("shading", {}).get("materials", {})
        outline = spec.get("shading", {}).get("outline") \
            or spec.get("outline", {}).get("char")
        transparent = str(spec["transparent_char"])
        legend = spec["legend"]
        names = [m.strip() for m in args.materials.split(",") if m.strip()]
        for m in names:
            if m not in mats:
                raise SpriteError(f"material {m!r} not in spec shading.materials "
                                  f"{sorted(mats)}")
        # source colors actually used (exclude transparent + outline), by lum
        used = sorted({c for row in rows for c in row
                       if c != transparent and c != outline and c in legend},
                      key=lambda c: lum(legend[c]))
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for m in names:
        ramp = sorted(mats[m], key=lambda c: lum(legend[c]) if c in legend else 0)
        # map each source color (by luminance rank) to a ramp color
        mapping = {}
        for i, src in enumerate(used):
            j = round(i / max(1, len(used) - 1) * (len(ramp) - 1)) if used else 0
            mapping[src] = ramp[j]
        out_rows = ["".join(mapping.get(c, c) for c in row) for row in rows]
        dest = args.out_dir / f"{args.sprite.stem}_{m}.pix"
        if dest.exists() and not args.force:
            print(f"skip {dest} (exists; --force to overwrite)", file=sys.stderr)
            continue
        write_pix(out_rows, dest, header=f"{m} variant of {args.sprite.name}")
        written += 1
        print(f"  wrote {dest}")
    print(f"{written}/{len(names)} variants written to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
