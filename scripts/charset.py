#!/usr/bin/env python3
"""Produce a CONSISTENT character set (poses / animation frames) end to end.

Usage:
    # 1) host agent generates the images itself: get the per-pose prompts
    charset.py --spec char.spec.json --character "a cute blue flame creature" \
        --poses front,back,left,walk_0,walk_1,walk_2,walk_3 --out-dir set/

    # 2) conform images you already generated (named <pose>.png in a dir)
    charset.py --spec char.spec.json --character "..." --poses front,back \
        --out-dir set/ --images-dir raw/

    # 3) fully automatic with a local img2img model (identity-chained)
    charset.py --spec char.spec.json --character "..." --poses front,back \
        --out-dir set/ --provider command \
        --cmd 'sd --prompt {prompt} --init {ref_png} --out {out_png}' \
        --ref hero.png

The set-consistency problem: generating pose 2 without conditioning on pose 1
drifts the character. This tool holds identity three ways:
  - ONE locked spec: every pose conforms to the same palette/canvas/cut-out;
  - ONE character block: every prompt embeds the same character description
    and style contract, plus a SAME-character clause when a --ref is given;
  - identity chaining: with a generating provider, the first pose's raw PNG
    becomes the {ref_png} for every later pose (img2img) unless --ref is set.
Then it GATES the result: set uniformity (consistency_report) and per-pose
retro-craft (craft_score), failing loudly with --strict.

Exit codes: 0 = ok, 1 = gate failed (--strict), 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid, write_pix  # noqa: E402
import generate_pixel  # noqa: E402
import consistency_report  # noqa: E402
import craft_score  # noqa: E402

POSE_PHRASES = {
    "front": "front view, facing the viewer, symmetrical stance",
    "back": "back view, seen from behind",
    "left": "side profile view, facing left",
    "right": "side profile view, facing right",
    "idle": "neutral idle stance",
}

# 8-way compass directions for a top-down / isometric game character - the
# no-3D-tools way to get a directional set: the image model draws each angle,
# charset keeps identity locked. (A real 3D rig is more geometrically exact,
# but this needs zero tools or skills.)
DIR_PHRASES = {
    "s": "facing toward the camera (south), seen from a high 3/4 top-down angle",
    "se": "facing down-right (southeast), high 3/4 top-down angle",
    "e": "facing right (east), high 3/4 top-down angle",
    "ne": "facing up-right (northeast), seen from behind at a top-down angle",
    "n": "facing away from the camera (north), seen from behind, top-down angle",
    "nw": "facing up-left (northwest), seen from behind at a top-down angle",
    "w": "facing left (west), high 3/4 top-down angle",
    "sw": "facing down-left (southwest), high 3/4 top-down angle",
}


def pose_phrase(pose: str, poses: list[str]) -> str:
    if pose in POSE_PHRASES:
        return POSE_PHRASES[pose]
    # bare compass direction, or <motion>_<dir> / dir_<d>
    for cand in (pose, pose.rpartition("_")[2]):
        if cand in DIR_PHRASES:
            return (DIR_PHRASES[cand]
                    + " - IDENTICAL character, only the facing direction "
                    "changes; consistent top-down camera height across the set")
    if "_" in pose:
        base, _, idx = pose.rpartition("_")
        if idx.isdigit():
            total = max(int(idx) + 1, sum(
                1 for q in poses
                if q.rpartition("_")[0] == base
                and q.rpartition("_")[2].isdigit()))
            n = int(idx) + 1
            if base in DIR_PHRASES:
                # direction x motion combo (s_0 = facing south, walk frame 1):
                # the no-3D way to get a full directions-x-frames sheet
                return (DIR_PHRASES[base] + f", walking cycle frame {n} of "
                        f"{total}, mid-stride - IDENTICAL character and "
                        "camera height across the whole set")
            if base == "walk":
                return (f"side view, walking cycle frame {n} of {total}, "
                        f"mid-stride, legs and arms mid-swing")
            return f"{base.replace('-', ' ')} animation frame {n} of {total}"
    return f"{pose.replace('_', ' ').replace('-', ' ')} pose"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--character",
                   help="the character description shared by every pose "
                        "(required with --poses)")
    p.add_argument("--poses",
                   help="comma list, e.g. front,back,left,walk_0,walk_1 "
                        "(character set: SAME subject, different poses)")
    p.add_argument("--subjects",
                   help="comma list of DIFFERENT subjects sharing one locked "
                        "template (style set: icons/badges), e.g. "
                        "'a sprouting plant,a pink heart,an open book'")
    p.add_argument("--template",
                   help="the shared scene every subject sits in, described "
                        "EXHAUSTIVELY (container, glow, floor, sparkles) - "
                        "injected into every prompt as identical-by-contract")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--provider", choices=("prompt-only", "openai", "hf",
                                          "command"), default="prompt-only")
    p.add_argument("--cmd", help="shell template ({prompt},{out_png},{ref_png})")
    p.add_argument("--ref", type=Path,
                   help="identity reference image (default: first pose's raw "
                        "PNG once generated)")
    p.add_argument("--images-dir", type=Path,
                   help="conform existing <pose>.png files from this dir "
                        "instead of generating")
    # conform pass-through (same defaults as generate_pixel)
    p.add_argument("--denoise", default="med",
                   choices=("none", "low", "med", "high", "max"))
    p.add_argument("--outline", metavar="CHAR")
    p.add_argument("--outline-mode", choices=("hard", "selout"), default="hard")
    p.add_argument("--dither", action="store_true")
    p.add_argument("--contain", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--min-uniformity", type=int, default=70)
    p.add_argument("--min-craft", type=int, default=0)
    p.add_argument("--animate", metavar="PREFIX",
                   help="after conforming, assemble poses named PREFIX_0.. "
                        "into <PREFIX>.gif + sprite sheet (+ json)")
    p.add_argument("--fps", type=int, default=8)
    p.add_argument("--export", choices=("aseprite", "css"),
                   help="with --animate: also export the sheet for an engine")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if bool(args.poses) == bool(args.subjects):
        print("error: give exactly one of --poses (character set) or "
              "--subjects (style set)", file=sys.stderr)
        return 2
    args.out_dir.mkdir(parents=True, exist_ok=True)

    prompts = {}
    if args.poses:
        poses = [s.strip() for s in args.poses.split(",") if s.strip()]
        for pose in poses:
            base = generate_pixel.build_prompt(
                f"{args.character}, {pose_phrase(pose, poses)}", spec)
            base += (" SAME character as the reference image: identical "
                     "colors, proportions, face, and design - only the pose "
                     "changes.")
            prompts[pose] = base
    else:
        # Style set: different subjects, ONE locked template. The lesson from
        # the field: a reference image alone makes the model borrow the vibe
        # but reinvent the structure per image - the shared scene must be a
        # written CONTRACT, repeated verbatim, with only the subject varying.
        sep = ";" if ";" in args.subjects else ","
        subjects = [s.strip() for s in args.subjects.split(sep) if s.strip()]
        poses = []
        for i, subj in enumerate(subjects):
            key = f"subject_{i}"
            poses.append(key)
            base = generate_pixel.build_prompt(subj, spec)
            if args.template:
                base += (f" Shared template, IDENTICAL in every image of "
                         f"this set (same geometry, line weight, and "
                         f"position): {args.template.strip()}")
            base += (" Exactly ONE subject, one composition - NOT a grid, "
                     "NOT a sheet, no repeated panels. Nothing hanging or "
                     "dangling from the container; no stray wires or "
                     "strings. Match the reference image's shading depth "
                     "(3-5 tone ramps with a soft ramped glow), not flat "
                     "fills.")
            prompts[key] = base
        # human-readable names for files/report
        names = {f"subject_{i}": s.split(",")[0].strip().replace(" ", "_")[:24]
                 or f"subject_{i}" for i, s in enumerate(subjects)}
        prompts = {names.get(k, k): v for k, v in prompts.items()}
        poses = list(prompts)

    if args.provider == "prompt-only" and not args.images_dir:
        kind = "Character set" if args.poses else "Style set"
        print(f"# {kind}: {len(poses)} item(s). Generate ONE image per "
              f"prompt (use the reference/first image as the img2img "
              f"reference), save as <name>.png, then re-run with "
              f"--images-dir DIR to conform + gate.\n")
        for pose in poses:
            print(f"## {pose}\n{prompts[pose]}\n")
        print(f"#   python scripts/charset.py --spec {args.spec} "
              f"{'--poses ' + args.poses if args.poses else '--subjects ...'}"
              f" --out-dir {args.out_dir} --images-dir RAW_DIR")
        return 0

    import imageify
    outline = args.outline
    if outline == "spec":
        outline = spec.get("shading", {}).get("outline") \
            or spec.get("outline", {}).get("char")

    ref = args.ref
    results = {}
    for i, pose in enumerate(poses):
        raw = args.out_dir / f"{pose}.png"
        try:
            if args.images_dir:
                src = args.images_dir / f"{pose}.png"
                if not src.exists():
                    raise SpriteError(f"missing {src}")
                raw = src
            elif args.provider == "command":
                if not args.cmd:
                    raise SpriteError("--provider command requires --cmd")
                generate_pixel.gen_command(prompts[pose], raw, args.cmd,
                                           ref if i > 0 or args.ref else None)
            elif args.provider == "hf":
                generate_pixel.gen_hf(prompts[pose], raw)
            elif args.provider == "openai":
                generate_pixel.gen_openai(prompts[pose], raw, "1024x1024")
            if ref is None:
                ref = raw                      # identity-chain on pose 0
            img = imageify.Image.open(raw)
            img.load()
            rows = imageify.conform(
                img, spec, dither=args.dither, bg_tol=42.0, resample="box",
                crop=True, contain=args.contain, clean=True,
                denoise=args.denoise, outline=outline,
                outline_mode=args.outline_mode)
            errs = validate_grid(rows, spec)
            if errs:
                raise SpriteError("; ".join(errs))
        except (SpriteError, OSError) as e:
            print(f"error: pose {pose}: {e}", file=sys.stderr)
            return 2
        out_pix = args.out_dir / f"{pose}.pix"
        write_pix(rows, out_pix, header=f"charset pose: {pose}")
        results[pose] = rows
        craft = craft_score.score(rows, spec)["overall"]
        print(f"  {pose}: wrote {out_pix.name} (craft {craft})")

    # set gates: uniformity + per-pose craft
    fail = False
    stats = {p_: consistency_report.asset_stats(r, spec)
             for p_, r in results.items()}
    if len(stats) >= 2:
        pals = [s["used"] for s in stats.values()]
        pairs = [consistency_report.jaccard(pals[i], pals[j])
                 for i in range(len(pals)) for j in range(i + 1, len(pals))]
        povl = sum(pairs) / len(pairs) if pairs else 1.0
        scores = [s["score"] for s in stats.values()]
        du = max(0.0, 1 - consistency_report.stdev(scores) / 30.0)
        uni = round(100 * (0.5 * povl + 0.5 * du))
        print(f"\nset: palette overlap {povl*100:.0f}%, uniformity {uni}/100")
        if uni < args.min_uniformity:
            print(f"  GATE: uniformity {uni} < {args.min_uniformity} - the "
                  f"poses drifted; regenerate the outliers with the first "
                  f"pose as --ref")
            fail = True
    crafts = {p_: craft_score.score(r, spec)["overall"]
              for p_, r in results.items()}
    low = [p_ for p_, c in crafts.items() if c < args.min_craft]
    if low:
        print(f"  GATE: craft below {args.min_craft}: {', '.join(low)}")
        fail = True

    # finish line: poses PREFIX_0.. -> gif + sheet (+ engine export)
    if args.animate:
        cycle = sorted(
            (p_ for p_ in results if p_.rpartition("_")[0] == args.animate
             and p_.rpartition("_")[2].isdigit()),
            key=lambda p_: int(p_.rpartition("_")[2]))
        if len(cycle) < 2:
            print(f"  animate: need 2+ poses named {args.animate}_0.. "
                  f"(found {len(cycle)})", file=sys.stderr)
            fail = True
        else:
            import animate
            frames = [str(args.out_dir / f"{p_}.pix") for p_ in cycle]
            out_base = args.out_dir / args.animate
            rc = animate.main(["--spec", str(args.spec), "--frames", *frames,
                               "--out", str(out_base), "--format", "all",
                               "--fps", str(args.fps)])
            if rc != 0:
                fail = True
            else:
                print(f"  animate: {args.animate}.gif + sheet "
                      f"({len(cycle)} frames @ {args.fps} fps)")
                if args.export:
                    import export_engine
                    ext = "json" if args.export == "aseprite" else "html"
                    rc = export_engine.main(
                        [str(args.out_dir / f"{args.animate}_sheet.json"),
                         "--engine", args.export, "--out",
                         str(args.out_dir / f"{args.animate}.{ext}"),
                         "--force"])
                    if rc == 0:
                        print(f"  export: {args.animate}.{ext} "
                              f"({args.export})")
                    else:
                        fail = True
    print("\nRESULT:", "FAIL" if (fail and args.strict) else "PASS")
    return 1 if (fail and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
