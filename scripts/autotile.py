#!/usr/bin/env python3
"""Auto-tile a fill mask into a seamless terrain map with uniform borders.

Usage:
    autotile.py mask.txt --spec tiles.spec.json --material green --out terrain.png

The mask is plain text: '#' = filled cell, '.' = empty. Every filled cell is
rendered from the same material ramp, with edges and corners auto-formed only
where it meets empty cells - so interior tiles are seamless and every boundary
gets the identical highlight/shadow border. This removes the most common map
inconsistency: hand-drawn edges that differ tile to tile.

Tile size = the spec canvas; output is the assembled map PNG at the spec
scale. Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec  # noqa: E402

try:
    from PIL import Image
except ImportError:
    print("error: Pillow is required. Install: python -m pip install Pillow",
          file=sys.stderr)
    sys.exit(3)

NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")


def hx(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mask", type=Path, help="text mask of '#'/'.'")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--material", default="default", help="ramp name from spec")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        legend = spec["legend"]
        mats = spec.get("shading", {}).get("materials", {})
        if args.material not in mats:
            raise SpriteError(f"material {args.material!r} not in spec "
                              f"shading.materials {sorted(mats)}")
        ramp = [hx(legend[c]) for c in mats[args.material] if c in legend]
        if len(ramp) < 2:
            raise SpriteError("material ramp needs >= 2 legend colors")
        rows = [ln.rstrip("\n") for ln in
                args.mask.read_text(encoding="utf-8").splitlines() if ln.strip("\n")]
        if not rows:
            raise SpriteError("mask is empty")
    except (SpriteError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    tw = int(spec["canvas"]["width"])
    th = int(spec["canvas"]["height"])
    scale = int(spec.get("scale", 1))
    cols = max(len(r) for r in rows)
    R = len(rows)
    dark, base, light = ramp[0], ramp[len(ramp) // 2], ramp[-1]
    edge2 = ramp[max(0, len(ramp) - 2)]

    def filled(cy, cx):
        return 0 <= cy < R and 0 <= cx < len(rows[cy]) and rows[cy][cx] == "#"

    canvas = Image.new("RGBA", (cols * tw, R * th), (0, 0, 0, 0))
    px = canvas.load()
    for cy in range(R):
        for cx in range(len(rows[cy])):
            if not filled(cy, cx):
                continue
            n, s = not filled(cy - 1, cx), not filled(cy + 1, cx)
            w, e = not filled(cy, cx - 1), not filled(cy, cx + 1)
            ox, oy = cx * tw, cy * th
            for y in range(th):
                for x in range(tw):
                    c = base
                    if n and y == 0:
                        c = light                    # grass-lit top edge
                    elif n and y == 1:
                        c = edge2
                    if s and y >= th - 1:
                        c = dark                     # shadowed bottom edge
                    if w and x == 0:
                        c = edge2 if not (n and y == 0) else c
                    if e and x == tw - 1:
                        c = dark if not (n and y == 0) else c
                    # outline at exposed corners
                    if (n and y == 0 and (w and x == 0 or e and x == tw - 1)) \
                            or (s and y == th - 1 and (w and x == 0 or e and x == tw - 1)):
                        c = dark
                    px[ox + x, oy + y] = c

    if scale > 1:
        canvas = canvas.resize((canvas.width * scale, canvas.height * scale),
                               NEAREST)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out, "PNG")
    print(f"wrote {args.out}  ({canvas.width}x{canvas.height} px, {cols}x{R} "
          f"tiles, material {args.material})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
