#!/usr/bin/env python3
"""Derive a draft Pixy spec from a reference pixel-art image.

Usage:
    analyze_sample.py <reference.png> --out pixy.spec.json
                      [--colors N] [--name NAME] [--force]

Extracts the hard, measurable style data from a sample image:
    - palette      : the dominant colors, quantized to N (default 16)
    - transparency : whether the image has an alpha channel (nukki)
    - native size  : the underlying pixel grid, estimated from the
                     greatest-common-divisor of color run lengths

The result is a DRAFT spec to be reviewed - pixel-size estimation is a
heuristic and palette quantization can merge near-duplicate shades. A
vision-capable agent should open the image and refine the conventions
(outline, shading, light source) afterwards.

Exit codes: 0 = draft written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from functools import reduce
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:
    print("error: Pillow is required. Install it with:\n"
          "    python -m pip install Pillow", file=sys.stderr)
    sys.exit(3)

NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")

# Character pool for assigning legend keys to extracted colors, ordered so
# the first 16 match init_spec's default legend feel. '.' is reserved for
# transparency and never appears here.
CHAR_POOL = "KDBLWRogGbcpPnN0123456789abcdefhijklmqstuvwxyz"


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def estimate_native_scale(img: "Image.Image", max_scale: int = 32) -> int:
    """Estimate the upscale factor by GCD of horizontal/vertical run lengths."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    runs: list[int] = []

    def collect(line_len: int, getter) -> None:
        run = 1
        prev = getter(0)
        for i in range(1, line_len):
            cur = getter(i)
            if cur == prev:
                run += 1
            else:
                runs.append(run)
                run = 1
                prev = cur
        runs.append(run)

    # Sample up to 64 rows and 64 columns to keep it fast on big images.
    row_step = max(1, h // 64)
    col_step = max(1, w // 64)
    for y in range(0, h, row_step):
        collect(w, lambda x, _y=y: px[x, _y])
    for x in range(0, w, col_step):
        collect(h, lambda y, _x=x: px[_x, y])

    if not runs:
        return 1
    g = reduce(math.gcd, runs)
    g = max(1, min(g, max_scale))
    # The estimate must divide both dimensions to yield an integer grid.
    while g > 1 and (w % g or h % g):
        g -= 1
    return g


def extract_palette(native: "Image.Image", colors: int) -> list[tuple[int, int, int]]:
    rgba = native.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    opaque: dict[tuple[int, int, int], int] = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a >= 128:
                opaque[(r, g, b)] = opaque.get((r, g, b), 0) + 1

    if not opaque:
        return []
    if len(opaque) <= colors:
        palette = list(opaque)
    else:
        # Too many shades: median-cut quantize the opaque region.
        rgb = native.convert("RGB")
        # Image.Quantize is Pillow 9.1+; 9.0 exposes MEDIANCUT on the module
        mediancut = getattr(getattr(Image, "Quantize", Image), "MEDIANCUT")
        q = rgb.quantize(colors=colors, method=mediancut)
        pal = q.getpalette() or []
        # 'P'-mode index bytes (avoids the deprecated Image.getdata()).
        used = set(q.tobytes())
        palette = [(pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]) for i in used]
    return sorted(palette, key=luminance)


HUE_NAMES = ["red", "yellow", "green", "cyan", "blue", "magenta"]


def build_materials(legend: dict[str, str]) -> dict[str, list[str]]:
    """Group the derived palette into hue-family ramps (dark -> light) so
    shade_form --material works on a derived spec, same as preset specs."""
    import colorsys
    fams: dict[str, list[tuple[float, str]]] = {}
    everything: list[tuple[float, str]] = []
    for ch, hexv in legend.items():
        r, g, b = (int(hexv[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        hsv = colorsys.rgb_to_hsv(r, g, b)
        lumv = 0.299 * r + 0.587 * g + 0.114 * b
        everything.append((lumv, ch))
        fam = ("grey" if hsv[1] < 0.18 or hsv[2] < 0.12
               else HUE_NAMES[int((hsv[0] * 360 + 30) // 60) % 6])
        fams.setdefault(fam, []).append((lumv, ch))
    materials = {"default": [c for _, c in sorted(everything)]}
    for fam, members in fams.items():
        if len(members) >= 3:
            materials[fam] = [c for _, c in sorted(members)]
    return materials


def hue_shift_ramps(legend: dict[str, str],
                    materials: dict[str, list[str]]) -> int:
    """Retro color discipline: bend each colorful ramp's shadow end toward
    cool (blue, 240deg) and its highlight end toward warm (50deg) - straight
    same-hue ramps read flat/digital; period palettes always hue-shifted.
    Mutates legend hexes in place; returns how many colors moved."""
    import colorsys

    def shift(hexv: str, target_deg: float, amount: float) -> str:
        r, g, b = (int(hexv[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        hh, s, v = colorsys.rgb_to_hsv(r, g, b)
        cur = hh * 360
        delta = ((target_deg - cur + 180) % 360) - 180
        cur = (cur + max(-amount, min(amount, delta))) % 360
        r2, g2, b2 = colorsys.hsv_to_rgb(cur / 360, s, v)
        return "#%02x%02x%02x" % (round(r2 * 255), round(g2 * 255),
                                  round(b2 * 255))

    moved = 0
    for fam, ramp in materials.items():
        if fam in ("default", "grey") or len(ramp) < 3:
            continue
        dark, light = ramp[0], ramp[-1]
        new_dark = shift(legend[dark], 240, 15)
        new_light = shift(legend[light], 50, 10)
        if new_dark != legend[dark]:
            legend[dark] = new_dark
            moved += 1
        if new_light != legend[light]:
            legend[light] = new_light
            moved += 1
    return moved


def build_draft(img: "Image.Image", colors: int, name: str) -> dict[str, Any]:
    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
    scale = estimate_native_scale(img)
    w, h = img.size
    native_w, native_h = w // scale, h // scale
    native = img.resize((native_w, native_h), NEAREST)
    palette_rgb = extract_palette(native, colors)

    legend = {}
    for i, rgb in enumerate(palette_rgb):
        ch = CHAR_POOL[i] if i < len(CHAR_POOL) else f"#{i}"
        legend[ch] = "#%02x%02x%02x" % rgb

    return {
        "name": name,
        "spec_version": 1,
        "use_case": "from-sample",
        "canvas": {"width": native_w, "height": native_h},
        "scale": scale if scale > 1 else 8,
        "background": "transparent" if has_alpha else "#%02x%02x%02x" % (
            palette_rgb[0] if palette_rgb else (26, 28, 44)),
        "transparent_char": ".",
        "legend": legend,
        "outline": {"char": next(iter(legend), "K"), "style": "unknown-review"},
        "conventions": (
            "Light source top-left. Hard pixel edges, no anti-aliasing. "
            "Shade with the derived palette ramps, not arbitrary colors. "
            "Match the reference image's look."
        ),
        "review_note": (
            "DRAFT derived from a sample image: native size and palette are "
            "estimated - confirm visually before locking."
        ),
        "export": {"format": "png", "naming": "{name}.png"},
        "_analysis": {
            "source_size": [w, h],
            "estimated_scale": scale,
            "has_alpha": has_alpha,
            "palette_count": len(palette_rgb),
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", type=Path, help="reference image (png/gif/...)")
    p.add_argument("--out", type=Path, required=True, help="output draft spec")
    p.add_argument("--colors", type=int, default=16, help="palette size (default 16)")
    p.add_argument("--name", default="from-sample", help="project/asset name")
    p.add_argument("--canvas", metavar="WxH",
                   help="override the canvas (e.g. 64x64): keep the IMAGE's "
                        "palette but target a different native size - the "
                        "one-command path to a character-true conform spec")
    p.add_argument("--scale", type=int, help="override the export scale")
    p.add_argument("--background",
                   help="override: 'transparent' (cut-out) or #RRGGBB")
    p.add_argument("--include", metavar="HEX[,HEX..]",
                   help="force these colors into the legend (within --colors "
                        "total) - signature colors quantization must not drop")
    p.add_argument("--hue-shift", action="store_true",
                   help="retro color discipline: bend each colorful ramp's "
                        "shadow end toward cool (blue) and highlight end "
                        "toward warm - straight ramps read flat/digital")
    p.add_argument("--force", action="store_true", help="overwrite existing spec")
    args = p.parse_args(argv)

    if args.colors < 2 or args.colors > 256:
        print("error: --colors must be between 2 and 256", file=sys.stderr)
        return 2
    if not args.image.exists():
        print(f"error: image not found: {args.image}", file=sys.stderr)
        return 2
    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force to overwrite",
              file=sys.stderr)
        return 2

    try:
        img = Image.open(args.image)
        img.load()
    except OSError as e:
        print(f"error: cannot read image: {e}", file=sys.stderr)
        return 2

    include = []
    if args.include:
        for hexv in args.include.split(","):
            hexv = hexv.strip().lower()
            if not hexv.startswith("#"):
                hexv = "#" + hexv
            if len(hexv) != 7:
                print(f"error: --include color must be #RRGGBB, got {hexv!r}",
                      file=sys.stderr)
                return 2
            include.append(hexv)
    if len(include) >= args.colors:
        print("error: --include has as many colors as --colors; nothing left "
              "to extract", file=sys.stderr)
        return 2

    draft = build_draft(img, args.colors - len(include), args.name)
    if include:
        used = set(draft["legend"])
        pool = [c for c in CHAR_POOL if c not in used]
        for hexv in include:
            if hexv in draft["legend"].values():
                continue
            draft["legend"][pool.pop(0)] = hexv
    if args.canvas:
        try:
            cw, ch = (int(v) for v in args.canvas.lower().split("x"))
        except ValueError:
            print(f"error: --canvas must look like 64x64, got {args.canvas!r}",
                  file=sys.stderr)
            return 2
        draft["canvas"] = {"width": cw, "height": ch}
    if args.scale:
        draft["scale"] = args.scale
    if args.background:
        draft["background"] = args.background
    # ramps: group the (final) legend into hue families so shade_form
    # --material works on derived specs too; optional retro hue-shift
    materials = build_materials(draft["legend"])
    shifted = 0
    if args.hue_shift:
        shifted = hue_shift_ramps(draft["legend"], materials)
    darkest = materials["default"][0] if materials["default"] else "K"
    draft["shading"] = {"light": "tl", "outline": darkest,
                        "rim": True, "ao": True, "materials": materials}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")

    a = draft["_analysis"]
    print(f"wrote draft {args.out}")
    print(f"  source {a['source_size'][0]}x{a['source_size'][1]} px, "
          f"estimated scale {a['estimated_scale']}")
    print(f"  -> native {draft['canvas']['width']}x{draft['canvas']['height']}, "
          f"{a['palette_count']} colors, has_alpha={a['has_alpha']}")
    fams = [k for k in draft["shading"]["materials"] if k != "default"]
    print(f"  ramps: {len(fams)} hue famil{'y' if len(fams) == 1 else 'ies'} "
          f"({', '.join(sorted(fams)) or 'none'})"
          + (f", hue-shifted {shifted} ramp end(s)" if args.hue_shift else ""))
    print("  REVIEW: confirm native size and palette; refine conventions "
          "visually.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
