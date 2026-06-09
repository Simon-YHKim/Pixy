#!/usr/bin/env python3
"""Stretch a small frame into any size with 9-slice scaling.

Usage:
    nine_slice.py panel.png --insets 4,4,4,4 --size 200x120 --out big.png
    nine_slice.py frame.pix --spec ui.spec.json --insets 3,3,3,3 \\
        --size 160x48 --mode tile --out button.png

Takes a small frame (a PNG, or a .pix rendered via --spec) and resizes it to
a target size while keeping the corners intact - the standard technique for
UI panels, buttons, dialog boxes, and health bars that must scale without
distorting their borders.

--insets L,T,R,B are the fixed border widths (pixels of the source). The
center and edges are repeated (--mode tile, default, keeps pixels crisp) or
scaled (--mode stretch, nearest-neighbor). Corners are always copied as-is.

Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
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

NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")


def fill_region(dst, src, sbox, dbox, mode):
    """Copy src[sbox] into dst[dbox], tiling or stretching to fit."""
    sx, sy, sw, sh = sbox
    dx, dy, dw, dh = dbox
    if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
        return
    crop = src.crop((sx, sy, sx + sw, sy + sh))
    if mode == "stretch":
        dst.alpha_composite(crop.resize((dw, dh), NEAREST), (dx, dy))
        return
    # tile: repeat the source crop, clipping at the destination edges
    for oy in range(0, dh, sh):
        for ox in range(0, dw, sw):
            piece = crop
            pw, ph = min(sw, dw - ox), min(sh, dh - oy)
            if (pw, ph) != (sw, sh):
                piece = crop.crop((0, 0, pw, ph))
            dst.alpha_composite(piece, (dx + ox, dy + oy))


def nine_slice(src, insets, size, mode):
    w, h = src.size
    l, t, r, b = insets
    W, H = size
    if l + r > W or t + b > H:
        raise SpriteError(f"insets ({l},{t},{r},{b}) exceed target {W}x{H}")
    if l + r > w or t + b > h:
        raise SpriteError(f"insets ({l},{t},{r},{b}) exceed source {w}x{h}")
    msw, msh = w - l - r, h - t - b   # source middle
    mdw, mdh = W - l - r, H - t - b   # dest middle
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # corners (copied 1:1)
    out.alpha_composite(src.crop((0, 0, l, t)), (0, 0))
    out.alpha_composite(src.crop((w - r, 0, w, t)), (W - r, 0))
    out.alpha_composite(src.crop((0, h - b, l, h)), (0, H - b))
    out.alpha_composite(src.crop((w - r, h - b, w, h)), (W - r, H - b))
    # edges
    fill_region(out, src, (l, 0, msw, t), (l, 0, mdw, t), mode)            # top
    fill_region(out, src, (l, h - b, msw, b), (l, H - b, mdw, b), mode)    # bottom
    fill_region(out, src, (0, t, l, msh), (0, t, l, mdh), mode)            # left
    fill_region(out, src, (w - r, t, r, msh), (W - r, t, r, mdh), mode)    # right
    # center
    fill_region(out, src, (l, t, msw, msh), (l, t, mdw, mdh), mode)
    return out


def load_frame(path, spec_path, scale):
    if path.suffix.lower() == ".pix":
        if not spec_path:
            raise SpriteError("a .pix frame needs --spec")
        from render_sprite import render  # noqa: E402
        spec = load_spec(spec_path)
        rows = parse_pix(path)
        errs = validate_grid(rows, spec)
        if errs:
            raise SpriteError("; ".join(errs))
        return render(rows, spec, scale or int(spec.get("scale", 1)))
    img = Image.open(path)
    img.load()
    return img.convert("RGBA")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("frame", type=Path, help="frame .png or .pix")
    p.add_argument("--spec", type=Path, help="spec if frame is a .pix")
    p.add_argument("--scale", type=int, help="render scale if frame is a .pix")
    p.add_argument("--insets", required=True, help="L,T,R,B border widths")
    p.add_argument("--size", required=True, help="target WxH")
    p.add_argument("--mode", choices=("tile", "stretch"), default="tile")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    try:
        insets = tuple(int(v) for v in args.insets.split(","))
        if len(insets) != 4 or any(v < 0 for v in insets):
            raise ValueError
    except ValueError:
        print("error: --insets must be L,T,R,B non-negative ints",
              file=sys.stderr)
        return 2
    try:
        sw, sh = (int(v) for v in args.size.lower().split("x"))
    except ValueError:
        print("error: --size must look like 200x120", file=sys.stderr)
        return 2

    try:
        src = load_frame(args.frame, args.spec, args.scale)
        out = nine_slice(src, insets, (sw, sh), args.mode)
    except (SpriteError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out, "PNG")
    print(f"wrote {args.out}  ({out.width}x{out.height} px, {args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
