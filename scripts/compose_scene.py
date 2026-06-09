#!/usr/bin/env python3
"""Compose parts into one finished scene or screen.

Usage:
    compose_scene.py scene.json --out scene.png

This is the "assembled result" step: a scene manifest places parts (rendered
PNGs, .pix sprites, and pixel text) at pixel coordinates on a canvas, layered
back to front. Use it to drop a character onto a map, or to lay out a HUD /
menu / title screen from panels, icons, and labels.

Manifest:
    {
      "canvas": [320, 180],
      "background": "transparent",         // or "#RRGGBB"
      "layers": [
        { "image": "level1.png", "at": [0, 0] },
        { "pix": "hero.pix", "spec": "tiles.spec.json", "scale": 8, "at": [40, 96] },
        { "image": "panel.png", "at": [4, 4] },
        { "text": "SCORE 100", "at": [10, 8], "scale": 2, "color": "#ffffff" }
      ]
    }

Layers render back-to-front (first = bottom). `image` = a PNG; `pix` = a sprite
(needs `spec`, optional `scale`); `text` = pixel text (optional `scale`,
`color`, `char`). Coordinates and the canvas are in final pixels. Paths are
relative to the manifest.

Exit codes: 0 = written, 1 = a layer failed, 2 = usage/IO error,
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
from text_pix import text_to_image  # noqa: E402


def hex_to_rgba(value):
    h = value.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def load_manifest(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SpriteError(f"scene not found: {path}")
    except json.JSONDecodeError as e:
        raise SpriteError(f"scene is not valid JSON: {e}")
    if "canvas" not in data or "layers" not in data:
        raise SpriteError("scene needs 'canvas' and 'layers'")
    if len(data["canvas"]) != 2:
        raise SpriteError("'canvas' must be [width, height]")
    return data


def layer_image(layer, base):
    if "image" in layer:
        img = Image.open(base / layer["image"])
        img.load()
        return img.convert("RGBA")
    if "pix" in layer:
        if "spec" not in layer:
            raise SpriteError(f"pix layer {layer['pix']} needs 'spec'")
        spec = load_spec(base / layer["spec"])
        rows = parse_pix(base / layer["pix"])
        errs = validate_grid(rows, spec)
        if errs:
            raise SpriteError(f"{layer['pix']}: {'; '.join(errs)}")
        return render(rows, spec, layer.get("scale", int(spec.get("scale", 1))))
    if "text" in layer:
        return text_to_image(layer["text"], layer.get("color", "#ffffff"),
                             layer.get("scale", 1))
    raise SpriteError(f"layer has none of image/pix/text: {layer}")


def compose(man, base):
    w, h = int(man["canvas"][0]), int(man["canvas"][1])
    bg = man.get("background", "transparent")
    fill = (0, 0, 0, 0) if bg == "transparent" else hex_to_rgba(bg)
    canvas = Image.new("RGBA", (w, h), fill)
    for i, layer in enumerate(man["layers"]):
        try:
            img = layer_image(layer, base)
        except (SpriteError, OSError) as e:
            raise SpriteError(f"layer {i}: {e}")
        at = layer.get("at", [0, 0])
        # anchor: place by a registration point instead of the top-left, so an
        # asset lands at `at` by its pivot (e.g. feet) regardless of its size.
        piv = layer.get("pivot")
        if piv is None and layer.get("anchor") == "pivot" and "spec" in layer:
            try:
                piv = load_spec(base / layer["spec"]).get("frame", {}).get("pivot")
            except SpriteError:
                piv = None
        if piv or layer.get("anchor") == "pivot":
            piv = piv or [0.5, 1.0]
            ox = int(at[0] - piv[0] * img.width)
            oy = int(at[1] - piv[1] * img.height)
        else:
            ox, oy = int(at[0]), int(at[1])
        canvas.alpha_composite(img, (ox, oy))
    return canvas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("scene", type=Path, help="scene manifest JSON")
    p.add_argument("--out", type=Path, required=True, help="output PNG")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    try:
        man = load_manifest(args.scene)
        canvas = compose(man, args.scene.parent)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1 if "layer" in str(e) else 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out, "PNG")
    print(f"wrote {args.out}  ({canvas.width}x{canvas.height} px, "
          f"{len(man['layers'])} layers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
