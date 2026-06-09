#!/usr/bin/env python3
"""Scaffold a Pixy project style spec (pixy.spec.json).

Usage:
    init_spec.py --out pixy.spec.json [--preset NAME]
                 [--canvas WxH] [--scale N] [--name NAME]
                 [--background transparent|#RRGGBB]
                 [--transparent-char C] [--force]

Stdlib only - no Pillow needed. The spec is the single source of truth
for a project's pixel-art style: every .pix sprite and every agent reads
the same locked palette, canvas size, scale, and transparency rule.

Presets set sensible defaults for common use cases; individual flags
override any preset field. Run with --list to print the preset table.

Exit codes: 0 = spec written, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# A balanced, neutral 16-color default palette (dark -> light ramps plus
# warm/cool accents). Keys are the single characters used in .pix grids;
# values are #RRGGBB. The transparent character is configured separately
# and is never part of the legend.
DEFAULT_PALETTE: dict[str, str] = {
    "K": "#1a1c2c",  # near-black outline
    "D": "#333c57",  # dark shadow
    "B": "#566c86",  # mid blue-grey
    "L": "#94b0c2",  # light blue-grey
    "W": "#f4f4f4",  # near-white highlight
    "r": "#b13e53",  # red shadow
    "R": "#ef7d57",  # red / orange
    "o": "#ffcd75",  # warm light
    "g": "#38b764",  # green
    "G": "#a7f070",  # light green
    "b": "#3b5dc9",  # blue
    "c": "#41a6f6",  # cyan
    "p": "#5d275d",  # purple shadow
    "P": "#b55088",  # purple / magenta
    "n": "#73533a",  # brown
    "N": "#a08662",  # tan
}

# Fixed console palettes. These lock color to a platform so every asset
# stays inside that hardware's gamut - the strongest possible consistency.
PICO8_PALETTE: dict[str, str] = {
    "K": "#000000", "n": "#1d2b53", "p": "#7e2553", "g": "#008751",
    "N": "#ab5236", "D": "#5f574f", "L": "#c2c3c7", "W": "#fff1e8",
    "r": "#ff004d", "o": "#ffa300", "y": "#ffec27", "G": "#00e436",
    "c": "#29adff", "B": "#83769c", "P": "#ff77a8", "R": "#ffccaa",
}
GAMEBOY_PALETTE: dict[str, str] = {
    "K": "#0f380f",  # darkest
    "D": "#306230",  # dark
    "L": "#8bac0f",  # light
    "W": "#9bbc0f",  # lightest
}

# Use-case presets. canvas is the native pixel grid; scale is the export
# upscale factor (nearest-neighbor) so 32x32 @ scale 8 -> 256x256 PNG. A
# preset may carry its own 'palette' to lock color to a platform; otherwise
# the default 16-color palette is used. Generic presets cover any project;
# engine presets add the canvas/scale and import notes a specific engine
# expects. For an engine without a preset, see references/engine-targets.md.
PRESETS: dict[str, dict[str, Any]] = {
    # --- generic / universal ---
    "game-character": {"canvas": (32, 32), "scale": 8,
                       "background": "transparent",
                       "note": "Top-down/side character sprite."},
    "tileset": {"canvas": (16, 16), "scale": 8,
                "background": "transparent",
                "note": "Seamless map/world tile."},
    "ui-icon": {"canvas": (24, 24), "scale": 10,
                "background": "transparent",
                "note": "Crisp interface icon."},
    "web-avatar": {"canvas": (64, 64), "scale": 4,
                   "background": "transparent",
                   "note": "Profile / avatar art."},
    "emoji": {"canvas": (16, 16), "scale": 6,
              "background": "transparent",
              "note": "Small expressive glyph."},
    "marquee": {"canvas": (128, 64), "scale": 3,
                "background": "#1a1c2c",
                "note": "Wide banner / title art."},
    # --- high-resolution (room for shading/detail) ---
    "icon-hd": {"canvas": (48, 48), "scale": 6, "background": "transparent",
                "note": "Detailed icon; block then shade_form."},
    "portrait": {"canvas": (64, 64), "scale": 5, "background": "transparent",
                 "note": "Character portrait/bust with shading."},
    "emblem": {"canvas": (96, 96), "scale": 3, "background": "transparent",
               "note": "Detailed emblem/badge; shade forms, add rim light."},
    # --- engine targets (canvas/scale + import notes; default palette) ---
    "unity": {"canvas": (32, 32), "scale": 8, "background": "transparent",
              "note": "Unity 2D: import as Sprite, Filter Mode Point, "
                      "Compression None, set Pixels-Per-Unit to the canvas "
                      "size for 1 tile = 1 unit."},
    "godot": {"canvas": (16, 16), "scale": 8, "background": "transparent",
              "note": "Godot: TileSet/Sprite2D, texture filter Nearest, "
                      "import re-import with Filter off."},
    "rpgmaker": {"canvas": (48, 48), "scale": 6, "background": "transparent",
                 "note": "RPG Maker MZ: character cell is 48x48; a walk "
                         "sheet is 3 frames x 4 directions per character."},
    # --- console gamuts (palette locked) ---
    "gameboy": {"canvas": (16, 16), "scale": 8, "background": "transparent",
                "palette": GAMEBOY_PALETTE,
                "note": "Game Boy DMG 4-shade green gamut."},
    "pico8": {"canvas": (16, 16), "scale": 8, "background": "transparent",
              "palette": PICO8_PALETTE,
              "note": "PICO-8 fixed 16-color palette."},
}

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
CANVAS_RE = re.compile(r"^(\d+)x(\d+)$")


def parse_canvas(value: str) -> tuple[int, int]:
    m = CANVAS_RE.match(value.strip().lower())
    if not m:
        raise argparse.ArgumentTypeError(
            f"--canvas must look like 32x32, got {value!r}")
    w, h = int(m.group(1)), int(m.group(2))
    if not (1 <= w <= 1024 and 1 <= h <= 1024):
        raise argparse.ArgumentTypeError(
            "canvas dimensions must be between 1 and 1024")
    return w, h


def _lum(hexv: str) -> float:
    h = hexv.lstrip("#")
    return 0.299 * int(h[0:2], 16) + 0.587 * int(h[2:4], 16) + 0.114 * int(h[4:6], 16)


def build_shading(legend: dict[str, str]) -> dict[str, Any]:
    """A locked shading style so every asset shades the same way: one light
    direction, one outline color, and named material ramps."""
    ordered = sorted(legend, key=lambda c: _lum(legend[c]))
    materials: dict[str, list[str]] = {"default": ordered}
    families = {
        "gold": ["n", "N", "o", "W"], "grey": ["D", "B", "L", "W"],
        "blue": ["D", "b", "c", "W"], "green": ["D", "g", "G", "W"],
        "red": ["r", "R", "o", "W"], "purple": ["p", "P", "L", "W"],
        "brown": ["K", "n", "N", "o"],
    }
    for name, chars in families.items():
        if all(c in legend for c in chars):
            materials[name] = chars
    return {"light": "tl", "outline": ordered[0], "rim": True, "ao": True,
            "materials": materials}


def build_spec(args: argparse.Namespace) -> dict[str, Any]:
    preset = PRESETS.get(args.preset, {}) if args.preset else {}
    canvas = args.canvas or preset.get("canvas", (32, 32))
    scale = args.scale or preset.get("scale", 8)
    background = args.background or preset.get("background", "transparent")
    note = preset.get("note", "")

    if background != "transparent" and not HEX_RE.match(background):
        raise ValueError(
            f"--background must be 'transparent' or #RRGGBB, got {background!r}")

    legend = dict(preset.get("palette", DEFAULT_PALETTE))
    outline_char = "K" if "K" in legend else next(iter(legend))

    return {
        "name": args.name,
        "spec_version": 1,
        "use_case": args.preset or "custom",
        "canvas": {"width": canvas[0], "height": canvas[1]},
        "scale": scale,
        "background": background,
        "transparent_char": args.transparent_char,
        "legend": legend,
        "outline": {"char": outline_char, "style": "selective-1px"},
        "shading": build_shading(legend),
        "conventions": (
            "Light source top-left. Selective 1px outline (char 'K'). "
            "No anti-aliasing; hard pixel edges only. Shade with the "
            "palette ramps, not arbitrary colors. " + note
        ).strip(),
        "export": {"format": "png", "naming": "{name}.png"},
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, help="output spec path")
    p.add_argument("--preset", choices=sorted(PRESETS), help="use-case preset")
    p.add_argument("--canvas", type=parse_canvas, help="native grid WxH, e.g. 32x32")
    p.add_argument("--scale", type=int, help="export upscale factor (>=1)")
    p.add_argument("--name", default="my-pixel-asset", help="project/asset name")
    p.add_argument("--background", help="'transparent' or #RRGGBB")
    p.add_argument("--transparent-char", default=".",
                   help="character that renders to alpha 0 (nukki)")
    p.add_argument("--force", action="store_true", help="overwrite existing spec")
    p.add_argument("--list", action="store_true", help="print preset table and exit")
    args = p.parse_args(argv)

    if args.list:
        print(f"{'preset':<16} {'canvas':<10} {'scale':<6} {'background':<13} note")
        for name, cfg in PRESETS.items():
            c = cfg["canvas"]
            print(f"{name:<16} {f'{c[0]}x{c[1]}':<10} {cfg['scale']:<6} "
                  f"{cfg['background']:<13} {cfg['note']}")
        return 0

    if not args.out:
        print("error: --out is required (or use --list)", file=sys.stderr)
        return 2
    if args.scale is not None and args.scale < 1:
        print("error: --scale must be >= 1", file=sys.stderr)
        return 2
    if len(args.transparent_char) != 1:
        print("error: --transparent-char must be a single character",
              file=sys.stderr)
        return 2
    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force to overwrite",
              file=sys.stderr)
        return 2

    try:
        spec = build_spec(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    c = spec["canvas"]
    export_w, export_h = c["width"] * spec["scale"], c["height"] * spec["scale"]
    print(f"wrote {args.out}")
    print(f"  canvas {c['width']}x{c['height']} @ scale {spec['scale']} "
          f"-> {export_w}x{export_h} px export")
    print(f"  palette {len(spec['legend'])} colors, "
          f"background {spec['background']}, transparent_char "
          f"{spec['transparent_char']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
