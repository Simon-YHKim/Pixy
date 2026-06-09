#!/usr/bin/env python3
"""Run a Pixy operation across many .pix files at once.

Usage:
    batch.py check  --spec pixy.spec.json --glob "sprites/*.pix"
    batch.py lint   --spec pixy.spec.json --glob "sprites/*.pix" --strict
    batch.py render --spec pixy.spec.json --glob "sprites/*.pix" --out-dir png
    batch.py recolor --spec pixy.spec.json --glob "red/*.pix" \\
        --recolor r:b,R:c,o:L --out-dir blue

Applies one operation to every matching .pix and prints a per-file result
plus a summary. Pass files directly and/or a --glob pattern. For projects
with many assets this keeps the whole set consistent in one command.

Ops: check | lint | render | recolor. render/recolor write to --out-dir
(default: alongside the input). Exit code is non-zero if any file fails.

Exit codes: 0 = all ok, 1 = one or more failed, 2 = usage/IO error,
3 = Pillow missing (render only).
"""
from __future__ import annotations

import argparse
import glob as globmod
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid, write_pix  # noqa: E402
import lint_pix  # noqa: E402
import transform_pix  # noqa: E402


def gather(files, glob):
    paths = list(files or [])
    if glob:
        # stdlib glob handles absolute and relative patterns (** recursive).
        paths += sorted(Path(p) for p in globmod.glob(glob, recursive=True))
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("op", choices=("check", "lint", "render", "recolor"))
    p.add_argument("files", type=Path, nargs="*", help="explicit .pix files")
    p.add_argument("--glob", help="glob pattern, e.g. 'sprites/*.pix'")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--out-dir", type=Path, help="output dir (render/recolor)")
    p.add_argument("--scale", type=int, help="render scale override")
    p.add_argument("--recolor", help="FROM:TO,... map (recolor op)")
    p.add_argument("--strict", action="store_true", help="lint: fail on finding")
    p.add_argument("--tileable", action="store_true", help="lint: seam check")
    p.add_argument("--max-colors", dest="max_colors", type=int,
                   help="lint: warn over N colors")
    p.add_argument("--force", action="store_true", help="overwrite outputs")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    paths = gather(args.files, args.glob)
    if not paths:
        print("error: no .pix files matched (use files or --glob)",
              file=sys.stderr)
        return 2

    render_mod = None
    if args.op == "render":
        try:
            import render_sprite as render_mod  # noqa: F811
        except SystemExit:
            return 3
    if args.op == "recolor" and not args.recolor:
        print("error: recolor needs --recolor FROM:TO,...", file=sys.stderr)
        return 2

    out_dir = args.out_dir
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    allowed = set(spec["legend"]) | {str(spec["transparent_char"])}
    scale = args.scale or int(spec.get("scale", 1))

    ok_count, fail_count = 0, 0
    for path in paths:
        try:
            rows = parse_pix(path)
            errors = validate_grid(rows, spec)
            if args.op == "check":
                if errors:
                    raise SpriteError("; ".join(errors))
                result = "valid"
            elif args.op == "lint":
                if errors:
                    raise SpriteError("fix check_sprite first: "
                                      + "; ".join(errors))
                findings = lint_pix.lint(rows, spec, tileable=args.tileable,
                                         max_colors=args.max_colors)
                if findings and args.strict:
                    raise SpriteError(f"{len(findings)} lint finding(s)")
                result = "clean" if not findings else f"{len(findings)} warning(s)"
            elif args.op == "render":
                if errors:
                    raise SpriteError("; ".join(errors))
                dest = (out_dir or path.parent) / (path.stem + ".png")
                if dest.exists() and not args.force:
                    raise SpriteError(f"{dest} exists (use --force)")
                img = render_mod.render(rows, spec, scale)
                img.save(dest, "PNG")
                result = f"-> {dest.name} ({img.width}x{img.height})"
            else:  # recolor
                mapping = transform_pix.parse_map(args.recolor)
                grid = [[mapping.get(c, c) for c in row] for row in rows]
                out_rows = ["".join(r) for r in grid]
                bad = sorted({c for row in out_rows for c in row
                              if c not in allowed})
                if bad:
                    raise SpriteError(f"recolor produced off-palette {bad}")
                dest = (out_dir or path.parent) / (path.stem + ".pix")
                if dest.exists() and not args.force and dest != path:
                    raise SpriteError(f"{dest} exists (use --force)")
                write_pix(out_rows, dest, header=f"recolored {path.name}")
                result = f"-> {dest.name}"
            print(f"  ok   {path}  {result}")
            ok_count += 1
        except SpriteError as e:
            print(f"  FAIL {path}  {e}", file=sys.stderr)
            fail_count += 1

    print(f"\n{args.op}: {ok_count} ok, {fail_count} failed "
          f"({len(paths)} files)")
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
