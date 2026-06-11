#!/usr/bin/env python3
"""Conform a rendered 3D frame sequence into a pixel-art directional set.

Usage:
    # frames rendered by Blender/Godot/etc., named <dir>_<frame>.png in raw/:
    #   s_0.png s_1.png ... e_0.png ... (8 directions x N motion frames)
    frames_to_pixel.py raw/ --spec hero.spec.json --out-dir out/ \
        --directions s,se,e,ne,n,nw,w,sw --frames 6 \
        --denoise med --outline spec --outline-mode selout

This is the 2D back half of the modern "model in 3D, ship in 2D" pipeline
(Dead Cells-style). Pixy does NOT do 3D - the model, rig, motion, and render
live in a real 3D tool (see references/three-d-to-pixel.md for a Blender
headless recipe). A rendered frame is just another raster source, like an
image model's output; this conforms every frame into ONE locked spec
(palette/canvas/cut-out), gates set consistency, and assembles the canonical
game output: a directions x frames sprite sheet (+ JSON), per-direction GIFs,
and an engine export. 3D renders are palette/scale/alignment-consistent
frame-to-frame, so they conform far more cleanly than generated art.

Naming: each file is `<direction>_<frame>.png` (e.g. `s_0.png`). With one
direction (`--directions s`) it is a plain motion cycle. Missing frames are
reported, not fatal, unless --strict.

Exit codes: 0 = ok, 1 = gate failed (--strict), 2 = usage/IO error,
3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid, write_pix  # noqa: E402
import consistency_report  # noqa: E402
import craft_score  # noqa: E402

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("error: Pillow is required. Install: python -m pip install Pillow",
          file=sys.stderr)
    sys.exit(3)

import imageify  # noqa: E402
import animate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("frames_dir", type=Path, help="dir of rendered <dir>_<f>.png")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--directions", default="s",
                   help="comma list of direction labels (row order), e.g. "
                        "s,se,e,ne,n,nw,w,sw; default 's' (single direction)")
    p.add_argument("--frames", type=int, required=True,
                   help="motion frames per direction (columns)")
    p.add_argument("--fps", type=int, default=8)
    p.add_argument("--export", choices=("aseprite", "css"),
                   help="also export the directional sheet for an engine")
    p.add_argument("--per-direction-gifs", action="store_true",
                   help="also write one looping GIF per direction")
    # conform pass-through
    p.add_argument("--denoise", default="med",
                   choices=("none", "low", "med", "high", "max"))
    p.add_argument("--dither", action="store_true")
    p.add_argument("--outline", metavar="CHAR")
    p.add_argument("--outline-mode", choices=("hard", "selout"), default="hard")
    p.add_argument("--contain", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--min-uniformity", type=int, default=70)
    p.add_argument("--min-craft", type=int, default=0)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if not args.frames_dir.is_dir():
        print(f"error: not a directory: {args.frames_dir}", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    dirs = [d.strip() for d in args.directions.split(",") if d.strip()]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    outline = args.outline
    if outline == "spec":
        outline = spec.get("shading", {}).get("outline") \
            or spec.get("outline", {}).get("char")

    # 1. conform every rendered frame into the locked spec
    grid_files: list[list[Path]] = []   # [direction][frame] -> .pix path
    rows_by_file: dict[Path, list[str]] = {}
    fail = False
    missing = 0
    for d in dirs:
        row: list[Path] = []
        for f in range(args.frames):
            src = args.frames_dir / f"{d}_{f}.png"
            if not src.exists():
                print(f"  missing {src.name}", file=sys.stderr)
                missing += 1
                fail = True
                continue
            try:
                img = imageify.Image.open(src)
                img.load()
                rows = imageify.conform(
                    img, spec, dither=args.dither, bg_tol=42.0,
                    resample="box", crop=False, contain=args.contain,
                    clean=True, denoise=args.denoise, outline=outline,
                    outline_mode=args.outline_mode)
                errs = validate_grid(rows, spec)
                if errs:
                    raise SpriteError("; ".join(errs))
            except (SpriteError, OSError) as e:
                print(f"  error {src.name}: {e}", file=sys.stderr)
                return 2
            out_pix = args.out_dir / f"{d}_{f}.pix"
            write_pix(rows, out_pix, header=f"3D frame {d} {f}")
            row.append(out_pix)
            rows_by_file[out_pix] = rows
        grid_files.append(row)
        print(f"  {d}: {len(row)}/{args.frames} frames conformed")

    complete = [r for r in grid_files if len(r) == args.frames]
    if not complete:
        print("error: no complete direction rows to assemble", file=sys.stderr)
        return 2

    # 2. directions x frames sheet (row-major: dir0 f0..fN, dir1 ...)
    ordered = [str(fp) for row in complete for fp in row]
    sheet_base = args.out_dir / "sheet"
    rc = animate.main(["--spec", str(args.spec), "--frames", *ordered,
                       "--out", str(sheet_base), "--format", "sheet",
                       "--fps", str(args.fps),
                       "--layout", f"grid:{args.frames}x{len(complete)}"])
    if rc != 0:
        return rc
    print(f"  sheet: {len(complete)} directions x {args.frames} frames "
          f"-> sheet_sheet.png + json")
    if args.export:
        import export_engine
        ext = "json" if args.export == "aseprite" else "html"
        export_engine.main([str(args.out_dir / "sheet_sheet.json"),
                            "--engine", args.export, "--out",
                            str(args.out_dir / f"sheet.{ext}"), "--force"])
        print(f"  export: sheet.{ext} ({args.export})")
    if args.per_direction_gifs:
        for d, row in zip(dirs, grid_files):
            if len(row) == args.frames:
                animate.main(["--spec", str(args.spec), "--frames",
                              *[str(fp) for fp in row], "--out",
                              str(args.out_dir / d), "--format", "gif",
                              "--fps", str(args.fps)])
        print(f"  gifs: one per direction")

    # 3. gates: set uniformity + per-frame craft
    all_rows = list(rows_by_file.values())
    if len(all_rows) >= 2:
        stats = [consistency_report.asset_stats(r, spec) for r in all_rows]
        pals = [s["used"] for s in stats]
        pairs = [consistency_report.jaccard(pals[i], pals[j])
                 for i in range(len(pals)) for j in range(i + 1, len(pals))]
        povl = sum(pairs) / len(pairs) if pairs else 1.0
        uni = round(100 * povl)
        print(f"\n  set uniformity: {uni}/100 (palette overlap)")
        if uni < args.min_uniformity:
            print(f"  GATE: uniformity {uni} < {args.min_uniformity}")
            fail = True
    crafts = [craft_score.score(r, spec)["overall"] for r in all_rows]
    if crafts:
        lo = min(crafts)
        print(f"  craft: min {lo}, mean {sum(crafts)//len(crafts)}")
        if lo < args.min_craft:
            print(f"  GATE: a frame scored craft {lo} < {args.min_craft}")
            fail = True
    if missing:
        print(f"  note: {missing} frame(s) were missing")
    print("\nRESULT:", "FAIL" if (fail and args.strict) else "PASS")
    return 1 if (fail and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
