#!/usr/bin/env python3
"""Conform any raster image into a clean, in-spec .pix grid.

Usage:
    imageify.py generated.png --spec pixy.spec.json --out asset.pix --dither

This is the deterministic back half of the image-first generation path:
generate (or hand off) a richly shaded pixel-art *raster* with
generate_pixel.py or any image tool, then imageify forces it into the locked
spec - native canvas, locked palette, cut-out background (nukki) - so a
detailed generated image becomes a valid Pixy asset that still obeys the
consistency contract.

Why not trace_image.py? trace_image *point-samples* at native resolution and
maps the nearest color, which is right for a clean integer-upscaled sprite but
turns an AI-generated raster (gradients, soft edges, anti-aliasing) into
speckle. imageify is built for non-pixel-perfect sources:

  - area-averages on downscale (BOX), so gradients survive instead of aliasing
  - optional Floyd-Steinberg dithering to the LOCKED palette, so shaded
    gradients read smoothly with only the spec's colors
  - keys out a solid background by border flood-fill (not just alpha), so an
    opaque generated image still gets a clean nukki
  - removes orphan/noise pixels

The palette, canvas size, and transparency are never invented - they come
from the spec, so two agents conforming the same raster get the same .pix.

Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, validate_grid, write_pix  # noqa: E402
from autofix import fix as clean_orphans  # noqa: E402

try:
    from PIL import Image, ImageFilter
except ImportError:
    print("error: Pillow is required. Install it with:\n"
          "    python -m pip install Pillow", file=sys.stderr)
    sys.exit(3)

BOX = getattr(getattr(Image, "Resampling", Image), "BOX")
LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")
RESAMPLE = {"box": BOX, "lanczos": LANCZOS, "nearest": NEAREST}
FS = getattr(getattr(Image, "Dither", Image), "FLOYDSTEINBERG", 3)
NODITHER = getattr(getattr(Image, "Dither", Image), "NONE", 0)


# Simplicity levels trade detail for a cleaner, cuter, more "designed" read.
# Fine detail is what makes a kawaii subject look noisy; the cute look is a
# small effective grid, few flat colors, and no dither. Each level sets:
#   coarsen     - shrink to native/coarsen then nearest back up (chunkier shapes)
#   max_colors  - keep only the N most-used palette colors (flatter)
#   flat        - force dithering off (solid regions, not speckle)
#   smooth      - median-filter the source first (kills stray pixels)
SIMPLIFY = {
    "none": {"coarsen": 1, "max_colors": None, "flat": False, "smooth": 0},
    "low":  {"coarsen": 1, "max_colors": 12, "flat": False, "smooth": 1},
    "med":  {"coarsen": 2, "max_colors": 8, "flat": True, "smooth": 1},
    "high": {"coarsen": 3, "max_colors": 6, "flat": True, "smooth": 2},
}


# Denoise cleans "impurity" pixels off areas that should read as one flat
# color, WITHOUT eating thin lines. Two complementary passes:
#   1. majority filter (per-pixel) - snaps a pixel to the dominant 8-neighbour
#      color when it has at most `iso` like-neighbours (a stray speck) and some
#      other color has at least `maj` of the 8. A 1px line keeps >=2 like-
#      neighbours along its length, so lines survive.
#   2. cluster cleanup (per-blob) - absorbs a whole connected same-color blob
#      into its surrounding color when the blob is smaller than `area` pixels.
#      This catches 2-4px clumps the per-pixel filter cannot (each clump pixel
#      has a like-neighbour). A line is a long blob, so it survives a modest
#      `area`. Raising `area` is the real strength knob.
DENOISE = {
    "none": None,
    "low":  {"iso": 0, "maj": 6, "passes": 1, "area": 0},
    "med":  {"iso": 1, "maj": 5, "passes": 2, "area": 2},
    "high": {"iso": 1, "maj": 5, "passes": 3, "area": 4},
    "max":  {"iso": 1, "maj": 5, "passes": 4, "area": 8},
}
NEI8 = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
             if not (dx == 0 and dy == 0))
NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _majority_pass(grid, transparent, iso, maj, passes):
    h, w = len(grid), len(grid[0])
    for _ in range(passes):
        new = [row[:] for row in grid]
        changed = 0
        for y in range(h):
            row = grid[y]
            for x in range(w):
                c = row[x]
                if c == transparent:
                    continue
                cnt: dict[str, int] = {}
                same = 0
                for dx, dy in NEI8:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        n = grid[ny][nx]
                        if n == transparent:
                            continue
                        cnt[n] = cnt.get(n, 0) + 1
                        if n == c:
                            same += 1
                if not cnt:
                    continue
                mc = max(cnt, key=cnt.get)
                if same <= iso and mc != c and cnt[mc] >= maj:
                    new[y][x] = mc
                    changed += 1
        grid[:] = new
        if not changed:
            break


def _cluster_pass(grid, transparent, min_area):
    """Absorb every connected same-color blob smaller than `min_area` into the
    color that most surrounds it. Line-preserving: a thin line is a long blob."""
    if min_area <= 1:
        return
    h, w = len(grid), len(grid[0])
    seen = [[False] * w for _ in range(h)]
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0][x0]:
                continue
            c = grid[y0][x0]
            seen[y0][x0] = True
            if c == transparent:
                continue
            comp = [(x0, y0)]
            border: dict[str, int] = {}
            qi = 0
            while qi < len(comp):
                cx, cy = comp[qi]
                qi += 1
                for dx, dy in NEI4:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        n = grid[ny][nx]
                        if n == c and not seen[ny][nx]:
                            seen[ny][nx] = True
                            comp.append((nx, ny))
                        elif n != c and n != transparent:
                            border[n] = border.get(n, 0) + 1
            if len(comp) < min_area and border:
                repl = max(border, key=border.get)
                for (px, py) in comp:
                    grid[py][px] = repl


def denoise_regions(grid, transparent, level, area=None):
    """Clean stray pixels/blobs off flat areas (line-preserving). `level` sets
    the strength; `area` overrides the cluster-size threshold when given."""
    cfg = DENOISE.get(level)
    if not cfg and area is None:
        return
    cfg = cfg or {"iso": 1, "maj": 5, "passes": 2, "area": 0}
    _majority_pass(grid, transparent, cfg["iso"], cfg["maj"], cfg["passes"])
    _cluster_pass(grid, transparent, area if area is not None else cfg["area"])


def cap_colors(grid, transparent, legend_rgb, k):
    """Keep only the k most-used colors; remap the rest to the nearest kept
    one. Fewer flat colors reads cleaner and cuter than many shaded tones."""
    from collections import Counter
    freq = Counter(c for row in grid for c in row if c != transparent)
    if len(freq) <= k:
        return
    keep = {c for c, _ in freq.most_common(k)}
    remap = {}
    for c in freq:
        if c not in keep:
            remap[c] = min(keep, key=lambda kc: sum(
                (a - b) ** 2 for a, b in zip(legend_rgb[c], legend_rgb[kc])))
    for y, row in enumerate(grid):
        grid[y] = [remap.get(c, c) for c in row]


def detect_bg(src: "Image.Image") -> tuple[int, int, int]:
    """The background color of an opaque image, taken as the per-channel median
    of the four corners (robust to a single odd corner)."""
    w, h = src.size
    px = src.convert("RGB").load()
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    out = []
    for i in range(3):
        vals = sorted(c[i] for c in corners)
        out.append((vals[1] + vals[2]) // 2)
    return (out[0], out[1], out[2])


def key_background(src: "Image.Image", bg, tol: float) -> "Image.Image":
    """Border flood-fill: every pixel within `tol` color distance of `bg` and
    connected to the image edge becomes transparent. A border flood (not a
    global color match) so a subject that happens to share the bg color is not
    punched full of holes."""
    rgba = src.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    br, bgc, bb = bg
    tol2 = tol * tol

    def is_bg(x, y):
        r, g, b, _a = px[x, y]
        return (r - br) ** 2 + (g - bgc) ** 2 + (b - bb) ** 2 <= tol2

    seen = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()

    def seed(x, y):
        if not seen[y * w + x] and is_bg(x, y):
            seen[y * w + x] = 1
            q.append((x, y))

    for x in range(w):
        seed(x, 0)
        seed(x, h - 1)
    for y in range(h):
        seed(0, y)
        seed(w - 1, y)
    while q:
        x, y = q.popleft()
        r, g, b, _a = px[x, y]
        px[x, y] = (r, g, b, 0)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                seed(nx, ny)
    return rgba


def crop_to_content(rgba: "Image.Image") -> "Image.Image":
    """Crop to the opaque bounding box so the subject fills the frame."""
    bbox = rgba.split()[-1].getbbox()
    return rgba.crop(bbox) if bbox else rgba


def _resize(img, w, h, resample):
    """Downscale with the chosen area filter; upscale with NEAREST so pixels
    stay crisp (BOX/LANCZOS upscale blurs, and the quantizer then mushes it)."""
    if w >= img.width and h >= img.height:
        return img.resize((w, h), NEAREST)
    return img.resize((w, h), resample)


def fit_contain(rgba, w, h, margin):
    """Resize-to-contain into a w*h canvas, aspect preserved, centered, with a
    margin - so a non-square subject is not stretched."""
    iw, ih = rgba.size
    avail_w = max(1, int(round(w * (1 - 2 * margin))))
    avail_h = max(1, int(round(h * (1 - 2 * margin))))
    scale = min(avail_w / iw, avail_h / ih)
    nw, nh = max(1, round(iw * scale)), max(1, round(ih * scale))
    small = _resize(rgba, nw, nh, BOX)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(small, ((w - nw) // 2, (h - nh) // 2), small)
    return canvas


def quantize_to_palette(rgb_img, pal_chars, pal_rgb, dither):
    """Quantize an RGB image to the locked palette (optionally Floyd-Steinberg
    dithered) and return a flat list of legend chars, one per pixel."""
    palimg = Image.new("P", (1, 1))
    flat: list[int] = []
    for rgb in pal_rgb:
        flat += list(rgb)
    # Pad the 256-slot palette by cycling real colors, so no quantizer slot
    # maps to an invented color (e.g. black) the spec does not contain.
    i = 0
    while len(flat) < 256 * 3:
        flat += list(pal_rgb[i % len(pal_rgb)])
        i += 1
    palimg.putpalette(flat[:256 * 3])

    q = rgb_img.quantize(palette=palimg, dither=FS if dither else NODITHER)
    qpx = q.convert("RGB").load()
    by_rgb = {rgb: ch for ch, rgb in zip(pal_chars, pal_rgb)}

    def nearest(rgb):
        return min(zip(pal_chars, pal_rgb),
                   key=lambda cr: sum((a - b) ** 2 for a, b in zip(rgb, cr[1])))[0]

    w, h = rgb_img.size
    out = []
    for y in range(h):
        for x in range(w):
            rgb = qpx[x, y]
            out.append(by_rgb.get(rgb) or nearest(rgb))
    return out


def conform(img, spec, *, dither, bg_tol, resample, crop, contain, clean,
            simplify="none", denoise="low", denoise_area=None, outline=None):
    width = int(spec["canvas"]["width"])
    height = int(spec["canvas"]["height"])
    transparent = str(spec["transparent_char"])
    bg_transparent = spec.get("background", "transparent") == "transparent"
    legend = spec["legend"]
    pal_chars = list(legend.keys())
    pal_rgb = [hex_to_rgb(legend[c]) for c in pal_chars]
    legend_rgb = dict(zip(pal_chars, pal_rgb))
    sx = SIMPLIFY[simplify]
    if sx["flat"]:
        dither = False                       # solid flat regions read cuter

    src = img.convert("RGBA")
    if sx["smooth"]:                         # remove stray pixels before scaling
        src = src.filter(ImageFilter.MedianFilter(2 * sx["smooth"] + 1))
    alo, _ahi = src.getchannel("A").getextrema()
    has_alpha = alo < 16

    if bg_transparent and not has_alpha:
        src = key_background(src, detect_bg(src), bg_tol)
    if crop:
        src = crop_to_content(src)

    if contain:
        native = fit_contain(src, width, height,
                             float(spec.get("frame", {}).get("margin", 0.06)))
    else:
        native = _resize(src, width, height, RESAMPLE[resample])

    if sx["coarsen"] > 1:                    # chunkier shapes, less fine detail
        cw = max(1, width // sx["coarsen"])
        ch = max(1, height // sx["coarsen"])
        native = native.resize((cw, ch), BOX).resize((width, height), NEAREST)

    alpha = native.split()[-1].load()
    chars = quantize_to_palette(native.convert("RGB"), pal_chars, pal_rgb, dither)

    grid = [[transparent] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if bg_transparent and alpha[x, y] < 128:
                grid[y][x] = transparent
            else:
                grid[y][x] = chars[y * width + x]

    if sx["max_colors"]:
        cap_colors(grid, transparent, legend_rgb, sx["max_colors"])
    denoise_regions(grid, transparent, denoise, denoise_area)
    if clean:
        clean_orphans(grid, transparent)
    # finishing pass: close the silhouette with a clean 1px outline, same
    # craft rule hand-authored assets follow (autofix --outline)
    if outline:
        for y in range(height):
            for x in range(width):
                if grid[y][x] == transparent:
                    continue
                for dx, dy in NEI4:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < width and 0 <= ny < height) \
                            or grid[ny][nx] == transparent:
                        grid[y][x] = outline
                        break
    return ["".join(r) for r in grid]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", type=Path, help="raster image to conform")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--out", type=Path, required=True, help="output .pix")
    p.add_argument("--dither", action="store_true",
                   help="Floyd-Steinberg dither to the locked palette. Adds "
                        "scattered pixels (busy) - use ONLY for smooth shaded "
                        "gradients, never for clean flat regions.")
    p.add_argument("--denoise", choices=tuple(DENOISE), default="low",
                   help="clean stray 'impurity' pixels off flat areas, "
                        "line-preserving (none/low/med/high/max; default low)")
    p.add_argument("--denoise-area", type=int, default=None, metavar="N",
                   help="override: absorb same-color blobs smaller than N px "
                        "into their surround (push cleanup past 'max'; "
                        "line-preserving). Try 6-16.")
    p.add_argument("--simplify", choices=tuple(SIMPLIFY), default="none",
                   help="reduce tones/colors and chunk the grid: fewer flat "
                        "colors, coarser shapes (none/low/med/high)")
    p.add_argument("--bg-tolerance", type=float, default=42.0,
                   help="color distance for solid-background keying (default 42)")
    p.add_argument("--resample", choices=tuple(RESAMPLE), default="box",
                   help="downscale filter (box=area-average, default); "
                        "upscaling always uses nearest to keep pixels crisp")
    p.add_argument("--no-crop", action="store_true",
                   help="do not crop to the opaque subject before fitting")
    p.add_argument("--contain", action="store_true",
                   help="aspect-preserving fit into the canvas with the spec "
                        "frame margin (avoids stretching a non-square subject)")
    p.add_argument("--no-clean", action="store_true",
                   help="skip orphan/hole cleanup")
    p.add_argument("--outline", metavar="CHAR",
                   help="finish with a clean 1px outline in this legend char "
                        "(pass 'spec' to use the spec's outline color)")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    if not args.image.exists():
        print(f"error: image not found: {args.image}", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        if not spec["legend"]:
            raise SpriteError("spec legend is empty; nothing to map to")
        outline = args.outline
        if outline == "spec":
            outline = spec.get("shading", {}).get("outline") \
                or spec.get("outline", {}).get("char")
        if outline and outline not in spec["legend"]:
            raise SpriteError(f"--outline {outline!r} not in the spec legend")
        img = Image.open(args.image)
        img.load()
        rows = conform(img, spec, dither=args.dither, bg_tol=args.bg_tolerance,
                       resample=args.resample, crop=not args.no_crop,
                       contain=args.contain, clean=not args.no_clean,
                       simplify=args.simplify, denoise=args.denoise,
                       denoise_area=args.denoise_area, outline=outline)
        errs = validate_grid(rows, spec)
        if errs:
            raise SpriteError("conformed grid invalid: " + "; ".join(errs))
    except (SpriteError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    write_pix(rows, args.out,
              header=f"imageified from {args.image.name} "
                     f"({spec['canvas']['width']}x{spec['canvas']['height']}"
                     f"{', dithered' if args.dither else ''}"
                     f"{', simplify=' + args.simplify if args.simplify != 'none' else ''})")
    transparent = str(spec["transparent_char"])
    used = sorted({c for row in rows for c in row if c != transparent})
    opaque = sum(1 for row in rows for c in row if c != transparent)
    total = len(rows) * len(rows[0])
    print(f"wrote {args.out}  ({len(rows[0])}x{len(rows)} grid, "
          f"{len(used)} colors, {opaque * 100 // total}% coverage)")
    print("  next: render_sprite.py to view, detail_score.py to grade, "
          "edit the .pix by hand to refine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
