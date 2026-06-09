#!/usr/bin/env python3
"""Assemble a tile grid into one map image.

Usage:
    tilemap.py level1.tmap.json --spec tiles.spec.json --out level1.png

The .tmap manifest is the "assembly instructions": it maps single characters
to tile .pix files and lays them out in a grid. Every tile is rendered
through the same spec, so they share one size and palette and the map lines
up perfectly.

Manifest:
    {
      "spec": "tiles.spec.json",          // optional; --spec overrides
      "tiles": { "g": "grass.pix", "w": "water.pix", ".": null },
      "map": [ "ggggg", "gwwwg", "ggggg" ]
    }

A char mapped to null (or the unmapped char ".") leaves a transparent gap.
Tile file paths are relative to the manifest. Output is one PNG sized
cols*tileW x rows*tileH (at the spec scale).

Exit codes: 0 = written, 1 = a tile failed validation, 2 = usage/IO error,
3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402

try:
    from PIL import Image
except ImportError:
    print("error: Pillow is required. Install: python -m pip install Pillow",
          file=sys.stderr)
    sys.exit(3)

from render_sprite import render  # noqa: E402


def load_manifest(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SpriteError(f"manifest not found: {path}")
    except json.JSONDecodeError as e:
        raise SpriteError(f"manifest is not valid JSON: {e}")
    for k in ("tiles", "map"):
        if k not in data:
            raise SpriteError(f"manifest missing '{k}'")
    if not isinstance(data["map"], list) or not data["map"]:
        raise SpriteError("'map' must be a non-empty list of rows")
    return data


def build_map(man, spec, base, scale):
    tw = int(spec["canvas"]["width"]) * scale
    th = int(spec["canvas"]["height"]) * scale
    rows = man["map"]
    width_chars = max(len(r) for r in rows)
    canvas = Image.new("RGBA", (width_chars * tw, len(rows) * th), (0, 0, 0, 0))

    cache = {}
    for ch, ref in man["tiles"].items():
        if ref is None:
            cache[ch] = None
            continue
        tile_path = base / ref
        tile_rows = parse_pix(tile_path)
        errs = validate_grid(tile_rows, spec)
        if errs:
            raise SpriteError(f"tile '{ch}' ({ref}): {'; '.join(errs)}")
        cache[ch] = render(tile_rows, spec, scale)

    for ry, row in enumerate(rows):
        for cx, ch in enumerate(row):
            if ch not in cache:
                raise SpriteError(f"map char {ch!r} at row {ry} not in tiles")
            tile = cache[ch]
            if tile is not None:
                canvas.alpha_composite(tile, (cx * tw, ry * th))
    return canvas, (width_chars, len(rows), tw, th)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("manifest", type=Path, help=".tmap.json")
    p.add_argument("--spec", type=Path, help="spec (overrides manifest 'spec')")
    p.add_argument("--out", type=Path, required=True, help="output PNG")
    p.add_argument("--scale", type=int, help="override spec scale")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    try:
        man = load_manifest(args.manifest)
        spec_path = args.spec or (
            (args.manifest.parent / man["spec"]) if man.get("spec") else None)
        if not spec_path:
            raise SpriteError("no spec: pass --spec or set 'spec' in manifest")
        spec = load_spec(spec_path)
        scale = args.scale or int(spec.get("scale", 1))
        canvas, (cols, rows, tw, th) = build_map(
            man, spec, args.manifest.parent, scale)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1 if ":" in str(e) and "tile" in str(e) else 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out, "PNG")
    print(f"wrote {args.out}  ({canvas.width}x{canvas.height} px, "
          f"{cols}x{rows} tiles @ {tw}x{th})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
