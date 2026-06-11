#!/usr/bin/env python3
"""One command: a generated/reference image -> a finished, gated game asset.

Usage:
    pixyfly.py flame.png --name flame --out-dir out/ \
        --colors 15 --canvas 64x64 --hue-shift \
        --denoise med --outline spec --outline-mode selout \
        --fx hover --gif

This is the factory's assembly line in one call. It chains the steps you'd
otherwise run by hand and ends with a release verdict:

    1. spec   - derive a character-true spec from the image (analyze_sample),
                or reuse --spec. Palette/canvas/cut-out get locked here.
    2. conform- imageify the raster into that spec (feature-preserving).
    3. render - the exact-size PNG.
    4. gate   - craft_score (retro discipline) + check/lint; with --strict and
                --min-craft it fails loudly, and always prints the ONE next
                action from the craft brief.
    5. animate- (optional) an animate_fx cycle -> GIF, so the asset moves.

Everything lands in --out-dir: <name>.spec.json, <name>.pix, <name>.png,
<name>_<fx>_*.pix, <name>_<fx>.gif. The asset stays in the locked spec, so it
animates, recolors, and composes like any other Pixy asset.

Exit codes: 0 = ok, 1 = gate failed (--strict), 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix  # noqa: E402
import analyze_sample, imageify, render_sprite, craft_score  # noqa: E402
import lint_pix, animate_fx, autofix  # noqa: E402
from collections import Counter  # noqa: E402


def _run(fn, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            return fn(argv), buf.getvalue()
        except SystemExit as e:
            return int(e.code or 0), buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", type=Path, help="generated/reference raster")
    p.add_argument("--name", help="asset name (default: image stem)")
    p.add_argument("--out-dir", type=Path, required=True)
    # spec: derive (default) or reuse
    p.add_argument("--spec", type=Path, help="reuse this spec (skip derive)")
    p.add_argument("--colors", type=int, default=16)
    p.add_argument("--canvas", help="native WxH, e.g. 64x64")
    p.add_argument("--background", default="transparent")
    p.add_argument("--hue-shift", action="store_true")
    p.add_argument("--include", help="force signature colors, e.g. '#ff77a8'")
    # conform pass-through
    p.add_argument("--denoise", default="med",
                   choices=("none", "low", "med", "high", "max"))
    p.add_argument("--dither", action="store_true")
    p.add_argument("--simplify", default="none",
                   choices=("none", "low", "med", "high"))
    p.add_argument("--outline", metavar="CHAR")
    p.add_argument("--outline-mode", choices=("hard", "selout"), default="hard")
    p.add_argument("--contain", action="store_true")
    # animation
    p.add_argument("--fx", choices=animate_fx.FX,
                   help="also produce a motion cycle from the asset")
    p.add_argument("--frames", type=int, default=6)
    p.add_argument("--amp", type=float, default=2.0)
    p.add_argument("--eye-char", help="eyes legend char (for --fx blink)")
    p.add_argument("--fps", type=int, default=8)
    p.add_argument("--gif", action="store_true", help="assemble the fx GIF")
    # gate
    p.add_argument("--min-craft", type=int, default=0)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if not args.image.exists():
        print(f"error: image not found: {args.image}", file=sys.stderr)
        return 2
    name = args.name or args.image.stem
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    spec_path = args.spec or (out / f"{name}.spec.json")
    pix_path = out / f"{name}.pix"
    png_path = out / f"{name}.png"

    # 1. spec
    if not args.spec:
        a = ["--out", str(spec_path), "--colors", str(args.colors),
             "--name", name, "--background", args.background, "--force"]
        if args.canvas:
            a += ["--canvas", args.canvas]
        if args.hue_shift:
            a += ["--hue-shift"]
        if args.include:
            a += ["--include", args.include]
        rc, log = _run(analyze_sample.main, [str(args.image), *a])
        if rc != 0:
            print(log, file=sys.stderr)
            return 2
        print(f"  spec   {spec_path.name}")
    else:
        print(f"  spec   {spec_path.name} (reused)")

    try:
        spec = load_spec(spec_path)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    # 2. conform
    ca = [str(args.image), "--spec", str(spec_path), "--out", str(pix_path),
          "--denoise", args.denoise, "--simplify", args.simplify, "--force"]
    if args.dither:
        ca += ["--dither"]
    if args.contain:
        ca += ["--contain"]
    if args.outline:
        ca += ["--outline", args.outline, "--outline-mode", args.outline_mode]
    rc, log = _run(imageify.main, ca)
    if rc != 0:
        print(log, file=sys.stderr)
        return 2
    rows = parse_pix(pix_path)
    used = sorted({c for r in rows for c in r if c != spec["transparent_char"]})
    print(f"  conform {pix_path.name}  ({len(used)} colors)")

    # 3. render
    rc, log = _run(render_sprite.main,
                   [str(pix_path), "--spec", str(spec_path), "--out",
                    str(png_path)])
    if rc == 0:
        print(f"  render {png_path.name}")

    # 5. animate (before the verdict so failures surface together)
    gif_path = None
    if args.fx:
        fa = [str(pix_path), "--spec", str(spec_path), "--fx", args.fx,
              "--frames", str(args.frames), "--amp", str(args.amp),
              "--out", str(out / f"{name}_{args.fx}"), "--force"]
        if args.eye_char:
            fa += ["--eye-char", args.eye_char]
        if args.gif:
            gif_path = out / f"{name}_{args.fx}.gif"
            fa += ["--gif", str(gif_path), "--fps", str(args.fps)]
        rc, log = _run(animate_fx.main, fa)
        if rc != 0:
            print("  animate FAILED:\n" + log, file=sys.stderr)
        else:
            print(f"  animate {args.fx} cycle"
                  + (f" -> {gif_path.name}" if gif_path else ""))

    # 4. gate / verdict - with ONE automatic repair pass first, so the Loop
    # cannot dead-end on mechanical findings (jaggies, isolated outline px)
    lints = lint_pix.lint(rows, spec)
    if lints:
        grid = [list(r) for r in rows]
        transparent = str(spec["transparent_char"])
        n = autofix.smooth_jaggies(grid, transparent)
        oc = spec.get("shading", {}).get("outline") \
            or spec.get("outline", {}).get("char")
        n += autofix.repair_isolated_outline(grid, transparent, oc)
        if n:
            autofix.fix(grid, transparent)
            rows = ["".join(r) for r in grid]
            from check_sprite import write_pix as _wp
            _wp(rows, pix_path, header=f"{name} (auto-repaired {n})")
            _run(render_sprite.main, [str(pix_path), "--spec", str(spec_path),
                                      "--out", str(png_path)])
            lints = lint_pix.lint(rows, spec)
            print(f"  repair {n} mechanical defect(s) auto-fixed")
    cr = craft_score.score(rows, spec)
    print(f"\n  craft {cr['overall']}/100 ({cr['grade']}), {len(lints)} lint")
    if lints:
        cats = Counter(f.split(" at ")[0].split(":")[0] for f in lints)
        print("  lint: " + ", ".join(f"{k} x{v}"
                                     for k, v in cats.most_common(3)))
    fail = cr["overall"] < args.min_craft
    verdict = "FAIL" if (fail and args.strict) else (
        "SHIP" if cr["overall"] >= 80 and not lints else "REVIEW")
    print(f"  VERDICT: {verdict}")
    if verdict != "SHIP":
        print("  next: " + cr["suggestions"][0])
    return 1 if (fail and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
