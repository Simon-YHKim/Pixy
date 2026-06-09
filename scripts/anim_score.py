#!/usr/bin/env python3
"""Score an animation's smoothness (0-100) and flag jumpy frames.

Usage:
    anim_score.py walk_0.pix walk_1.pix walk_2.pix --spec pixy.spec.json

Looks at two things: how many frames there are (more reads smoother) and how
even the motion is between frames (a frame that changes far more than the rest
is a visible jump). Reports the score plus any frame transitions that spike,
so you know where to add an in-between.

Exit codes: 0 = scored, 1 = a frame failed validation, 2 = usage/IO error,
3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("error: Pillow is required. Install: python -m pip install Pillow",
          file=sys.stderr)
    sys.exit(3)

from render_sprite import render  # noqa: E402


def frame_delta(a, b):
    """Fraction of differing pixels between two equal-size RGBA frames."""
    pa, pb = a.load(), b.load()
    w, h = a.size
    diff = sum(1 for y in range(h) for x in range(w) if pa[x, y] != pb[x, y])
    return diff / (w * h)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("frames", type=Path, nargs="+", help="ordered .pix frames")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--loop", action="store_true",
                   help="also measure the last->first transition")
    args = p.parse_args(argv)

    if len(args.frames) < 2:
        print("error: need 2+ frames to score an animation", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        scale = int(spec.get("scale", 1))
        imgs = []
        for f in args.frames:
            rows = parse_pix(f)
            errs = validate_grid(rows, spec)
            if errs:
                raise SpriteError(f"{f} is invalid: {'; '.join(errs)}")
            imgs.append(render(rows, spec, scale).convert("RGBA"))
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1 if "invalid" in str(e) else 2

    n = len(imgs)
    pairs = list(zip(range(n - 1), range(1, n)))
    if args.loop:
        pairs.append((n - 1, 0))
    deltas = [frame_delta(imgs[i], imgs[j]) for i, j in pairs]
    mean = sum(deltas) / len(deltas)
    # frame-count score: 2 frames ~ choppy, 12+ ~ smooth
    fc_score = max(0.0, min(1.0, (n - 1) / 11.0))
    # evenness: penalize transitions far above the mean (jumps)
    worst = max(deltas)
    evenness = 1.0 if mean == 0 else max(0.0, 1 - (worst - mean) / (mean + 1e-6) / 3)
    score = round(100 * (0.6 * fc_score + 0.4 * evenness))

    print(f"animation: {score}/100  ({n} frames, mean change "
          f"{mean*100:.1f}%/frame)")
    for (i, j), d in zip(pairs, deltas):
        flag = "  <-- jump" if d > mean * 1.8 and d > 0.04 else ""
        print(f"  frame {i}->{j}: {d*100:.1f}% changed{flag}")
    if n < 4:
        print("  add frames for a smoother cycle (walk cycles read best at 6-12).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
