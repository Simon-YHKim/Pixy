#!/usr/bin/env python3
"""Score how close a generated asset is to a reference (0-100).

Usage:
    ref_similarity.py generated.png reference.png
    ref_similarity.py generated.pix --spec pixy.spec.json reference.png

Pairs with trace --derive: after aiming for a reference, see how close you
got. Blends silhouette overlap (IoU), per-pixel color closeness, and
luminance-distribution match, then gives hints on what is off.

Exit codes: 0 = scored, 2 = usage/IO error, 3 = Pillow missing.
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
N = 48  # common comparison grid


def load_img(path, spec_path):
    if path.suffix.lower() == ".pix":
        if not spec_path:
            raise SpriteError(f"{path} is a .pix; pass --spec")
        from render_sprite import render
        spec = load_spec(spec_path)
        rows = parse_pix(path)
        errs = validate_grid(rows, spec)
        if errs:
            raise SpriteError("; ".join(errs))
        return render(rows, spec, int(spec.get("scale", 1))).convert("RGBA")
    img = Image.open(path)
    img.load()
    return img.convert("RGBA")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("generated", type=Path)
    p.add_argument("reference", type=Path)
    p.add_argument("--spec", type=Path, help="if generated is a .pix")
    args = p.parse_args(argv)

    try:
        a = load_img(args.generated, args.spec).resize((N, N), NEAREST)
        b = load_img(args.reference, None).resize((N, N), NEAREST)
    except (SpriteError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    pa, pb = a.load(), b.load()
    inter = union = 0
    dist_sum = overlap = 0.0
    histA = [0] * 8
    histB = [0] * 8
    for y in range(N):
        for x in range(N):
            ra, ga, ba, aa = pa[x, y]
            rb, gb, bb, ab = pb[x, y]
            oa, ob = aa >= 128, ab >= 128
            union += 1 if (oa or ob) else 0
            inter += 1 if (oa and ob) else 0
            if oa:
                histA[min(7, int((0.299*ra+0.587*ga+0.114*ba)/32))] += 1
            if ob:
                histB[min(7, int((0.299*rb+0.587*gb+0.114*bb)/32))] += 1
            if oa and ob:
                dist_sum += ((ra-rb)**2 + (ga-gb)**2 + (ba-bb)**2) ** 0.5
                overlap += 1
    iou = inter / union if union else 1.0
    color_sim = max(0.0, 1 - (dist_sum / overlap) / 180.0) if overlap else 0.0
    sa, sb = sum(histA) or 1, sum(histB) or 1
    lum = 1 - 0.5 * sum(abs(histA[i]/sa - histB[i]/sb) for i in range(8))
    score = round(100 * (0.5 * iou + 0.4 * color_sim + 0.1 * lum))

    print(f"similarity: {score}/100")
    print(f"  silhouette IoU {iou*100:.0f}%, color {color_sim*100:.0f}%, "
          f"luminance {lum*100:.0f}%")
    if iou < 0.6:
        print("  - shape differs: adjust the silhouette / size / framing.")
    if color_sim < 0.6:
        print("  - colors differ: derive the palette from the reference "
              "(analyze_sample / trace_image --derive).")
    if lum < 0.7:
        print("  - tonal balance differs: match shadow/highlight spread.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
