#!/usr/bin/env python3
"""Build or import a Pixy palette (legend) - ramps and external formats.

Usage:
    palette_tool.py --ramp 3b5dc9 --steps 5            # generate a ramp
    palette_tool.py --import pal.gpl                    # import GIMP palette
    palette_tool.py --import pal.hex --apply pixy.spec.json --force
    palette_tool.py --from-spec pixy.spec.json --check  # luminance report

Stdlib only. Generates a dark->light ramp from a base color (HSL lightness
sweep with a slight hue warm/cool shift), or imports a palette from common
formats (.hex one RRGGBB per line, .gpl GIMP palette). Lospec exports .hex
and .gpl, so this covers Lospec palettes.

With --apply SPEC the palette replaces that spec's legend (needs --force);
otherwise the legend is printed as JSON. --check prints each color's
luminance to spot ramps that are too close in value.

Exit codes: 0 = ok, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec  # noqa: E402

CHAR_POOL = "KDBLWRogGbcpPnN0123456789acdefhijklmqstuvwxyz"
HEX6 = re.compile(r"#?([0-9a-fA-F]{6})")


def to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def luminance(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def make_ramp(base_hex, steps, shift=0.04):
    r, g, b = (c / 255 for c in hex_to_rgb(base_hex))
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    out = []
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0.5
        light = 0.22 + t * 0.62  # dark shadow -> bright highlight
        sat = min(1.0, s * (1.15 - 0.3 * t))  # a touch less saturated in light
        # hue shift: cooler in shadow, warmer toward the light (a pro touch).
        hue = (h + shift * (t - 0.5) * 2) % 1.0
        rr, gg, bb = colorsys.hls_to_rgb(hue, light, sat)
        out.append(to_hex((rr * 255, gg * 255, bb * 255)))
    return out


def parse_palette_file(path: Path):
    text = path.read_text(encoding="utf-8")
    colors = []
    if path.suffix.lower() == ".gpl" or text.lstrip().startswith("GIMP Palette"):
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" in line \
                    or line.startswith("GIMP"):
                continue
            parts = line.split()
            if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
                colors.append(to_hex((int(parts[0]), int(parts[1]),
                                      int(parts[2]))))
    else:  # .hex or anything with hex tokens
        for line in text.splitlines():
            m = HEX6.search(line.strip())
            if m:
                colors.append("#" + m.group(1).lower())
    if not colors:
        raise SpriteError(f"no colors parsed from {path}")
    return colors


def assign_legend(hex_list):
    ordered = sorted(set(hex_list), key=lambda h: luminance(hex_to_rgb(h)))
    legend = {}
    for i, hx in enumerate(ordered):
        ch = CHAR_POOL[i] if i < len(CHAR_POOL) else f"x{i}"
        legend[ch] = hx
    return legend


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ramp", help="base #RRGGBB to build a ramp from")
    p.add_argument("--steps", type=int, default=5, help="ramp steps (>=2)")
    p.add_argument("--hue-shift", action="store_true",
                   help="stronger cool-shadow / warm-highlight hue shift")
    p.add_argument("--import", dest="imp", type=Path, help=".hex/.gpl palette")
    p.add_argument("--from-spec", type=Path, help="read legend from a spec")
    p.add_argument("--check", action="store_true", help="print luminances")
    p.add_argument("--apply", type=Path, help="write legend into this spec")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    try:
        if args.from_spec:
            spec = load_spec(args.from_spec)
            legend = spec["legend"]
        elif args.ramp:
            if args.steps < 2:
                raise SpriteError("--steps must be >= 2")
            if not HEX6.fullmatch(args.ramp.lstrip("#")):
                raise SpriteError("--ramp must be #RRGGBB")
            legend = assign_legend(make_ramp(args.ramp, args.steps,
                                             0.12 if args.hue_shift else 0.04))
        elif args.imp:
            if not args.imp.exists():
                raise SpriteError(f"file not found: {args.imp}")
            legend = assign_legend(parse_palette_file(args.imp))
        else:
            raise SpriteError("choose --ramp, --import, or --from-spec")
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.check:
        print(f"{len(legend)} colors (by luminance):")
        for ch, hx in sorted(legend.items(),
                             key=lambda kv: luminance(hex_to_rgb(kv[1]))):
            print(f"  {ch} {hx}  L={luminance(hex_to_rgb(hx)):.0f}")
        return 0

    if args.apply:
        if not args.apply.exists():
            print(f"error: spec not found: {args.apply}", file=sys.stderr)
            return 2
        if not args.force:
            print("error: --apply rewrites the spec legend; pass --force",
                  file=sys.stderr)
            return 2
        spec = load_spec(args.apply)
        spec["legend"] = legend
        if spec.get("outline", {}).get("char") not in legend:
            spec.setdefault("outline", {})["char"] = next(iter(legend))
        args.apply.write_text(json.dumps(spec, indent=2) + "\n",
                              encoding="utf-8")
        print(f"applied {len(legend)}-color palette to {args.apply}")
        return 0

    print(json.dumps(legend, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
