#!/usr/bin/env python3
"""Verify a whole asset set against the spec in one command (the CI gate).

Usage:
    verify.py --spec pixy.spec.json --glob "**/*.pix"
    verify.py a.pix b.pix --spec pixy.spec.json --strict --min-detail 55 --min-uniformity 70

Runs the full consistency + quality battery over every asset and prints one
report: per-asset validity (check_sprite), craft lint, proportion fit, and
detail score; then set-level uniformity and style-drift (stamped spec_id vs
current). With --strict it exits non-zero if anything is invalid, drifted, or
below the thresholds - so a project's pixel art stays uniform and on-spec.

Exit codes: 0 = pass, 1 = failed gate (--strict), 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import glob as globmod
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid, spec_id  # noqa: E402
import lint_pix, proportions, detail_score, consistency_report, style_lock  # noqa: E402
import craft_score  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", type=Path, nargs="*")
    p.add_argument("--glob")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--min-detail", type=int, default=0)
    p.add_argument("--min-craft", type=int, default=0,
                   help="gate on the retro-craft discipline score")
    p.add_argument("--min-uniformity", type=int, default=0)
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    paths = list(args.files) + (
        sorted(Path(p) for p in globmod.glob(args.glob, recursive=True))
        if args.glob else [])
    paths = sorted(set(paths))
    if not paths:
        print("error: no .pix files (use files or --glob)", file=sys.stderr)
        return 2

    cur_id = spec.get("spec_id") or spec_id(spec)
    frame = spec.get("frame", {})
    fail = False
    valid_rows = {}
    print(f"verifying {len(paths)} asset(s) against {args.spec.name} "
          f"(spec_id {cur_id})\n")
    for sp in paths:
        try:
            rows = parse_pix(sp)
            errs = validate_grid(rows, spec)
        except SpriteError as e:
            print(f"  FAIL {sp.name}: {e}")
            fail = True
            continue
        if errs:
            print(f"  FAIL {sp.name}: invalid ({errs[0]})")
            fail = True
            continue
        valid_rows[sp] = rows
        lints = len(lint_pix.lint(rows, spec))
        prop = proportions.measure(rows, spec)
        pissues = len(proportions.check(prop, frame)) if prop else 0
        det = detail_score.score(rows, spec)["overall"]
        craft = craft_score.score(rows, spec)["overall"]
        stamp = style_lock.read_stamp(sp)
        drift = stamp is not None and stamp != cur_id
        notes = []
        if det < args.min_detail:
            notes.append(f"detail {det}<{args.min_detail}")
            fail = True
        if craft < args.min_craft:
            notes.append(f"craft {craft}<{args.min_craft}")
            fail = True
        if drift:
            notes.append(f"drift {stamp}")
            fail = True
        flag = "FAIL" if notes else "ok  "
        print(f"  {flag} {sp.name}: detail {det}, craft {craft}, {lints} lint, "
              f"{pissues} proportion issue(s)"
              + (", " + "; ".join(notes) if notes else ""))

    if len(valid_rows) >= 2:
        stats = {sp: consistency_report.asset_stats(r, spec)
                 for sp, r in valid_rows.items()}
        scores = [s["score"] for s in stats.values()]
        outs = [s["outline"] for s in stats.values()]
        pals = [s["used"] for s in stats.values()]
        pairs = [consistency_report.jaccard(pals[i], pals[j])
                 for i in range(len(pals)) for j in range(i + 1, len(pals))]
        povl = sum(pairs) / len(pairs) if pairs else 1.0
        du = max(0.0, 1 - consistency_report.stdev(scores) / 30.0)
        chs = consistency_report.stdev([s["content_h"] for s in stats.values()])
        cxs = consistency_report.stdev([s["center_x"] for s in stats.values()])
        bts = consistency_report.stdev([s["bottom"] for s in stats.values()])
        pu = max(0.0, 1 - (chs / 0.12 + cxs / 0.06 + bts / 0.05) / 3)
        uni = round(100 * (0.3 * du + 0.2 * (sum(outs) / len(outs))
                           + 0.2 * povl + 0.3 * pu))
        print(f"\nset uniformity: {uni}/100")
        if uni < args.min_uniformity:
            print(f"  FAIL uniformity {uni} < {args.min_uniformity}")
            fail = True

    print("\nRESULT:", "FAIL" if (fail and args.strict) else "PASS"
          + ("" if not fail else " (warnings; not strict)"))
    return 1 if (fail and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
