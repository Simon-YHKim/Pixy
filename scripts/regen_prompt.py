#!/usr/bin/env python3
"""Turn a detail score + target into concrete regeneration instructions.

Usage:
    regen_prompt.py asset.pix --spec pixy.spec.json --target 80

Scores the asset, compares it to the target detail (0-100), and prints the
specific next steps - which scripts to run and what to change - plus a
copy-paste brief for the LLM. Closes the loop: gauge the result, then know
exactly how to ask for a better one.

Exit codes: 0 = printed, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402
import detail_score  # noqa: E402


def steps_for(metrics, spec, target):
    out_char = spec.get("shading", {}).get("outline") \
        or spec.get("outline", {}).get("char") or "K"
    cw = int(spec["canvas"]["width"])
    s = []
    if metrics["shading"] < target / 100:
        s.append(f"Add volume: shade each region with shade_form.py "
                 f"(--form sphere/cyl-v/cyl-h/round, --rim --ao), or use a "
                 f"longer ramp / --material.")
    if metrics["range"] < 0.45:
        s.append("Widen tonal range: include a near-dark shadow and a "
                 "near-white highlight ramp step.")
    if metrics["outline"] < 0.6:
        s.append(f"Add a clean edge: shade_form.py --outline {out_char}.")
    if metrics["resolution"] < target / 100 and cw < 64:
        s.append(f"Go bigger: re-init at >= 64px (icon-hd/portrait/emblem "
                 f"presets) - {cw}px caps the achievable detail.")
    if metrics["clean"] < 0.85:
        s.append("Remove noise: lint_pix.py --strict, then autofix.py.")
    if not s:
        s.append("Already at/above target on the measured axes; refine by "
                 "hand or add content (more features).")
    return s


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--target", type=int, default=75, help="target detail 0-100")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
        rows = parse_pix(args.sprite)
        errs = validate_grid(rows, spec)
        if errs:
            raise SpriteError("; ".join(errs))
        r = detail_score.score(rows, spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    cur, tgt = r["overall"], max(0, min(100, args.target))
    print(f"{args.sprite.name}: detail {cur}/100 ({r['grade']}); "
          f"target {tgt}/100")
    if cur >= tgt:
        print("  at or above target - ship it, or push higher if you want.")
    print("  next steps:")
    for st in steps_for(r["metrics"], spec, tgt):
        print(f"   - {st}")
    cw = spec["canvas"]["width"]
    brief = (f"Improve this pixel-art asset from detail {cur} to ~{tgt}/100: "
             f"keep the locked palette and {cw}px-class canvas, add shaded "
             f"volume (shade_form), a clean 1px outline, and more content/"
             f"features; show the re-scored result.")
    print("\n  LLM brief (copy):")
    print(f"   {brief}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
