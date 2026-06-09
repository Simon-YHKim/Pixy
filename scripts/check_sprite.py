#!/usr/bin/env python3
"""Validate a .pix character grid against a Pixy spec.

Usage:
    check_sprite.py <sprite.pix> --spec <pixy.spec.json>

Stdlib only - runs anywhere, no Pillow. This is the consistency gate:
it rejects a sprite whose dimensions differ from the spec canvas, whose
characters are not in the locked legend, or that has no transparency
when the spec calls for a transparent background. Code-only agents and
CI rely on this; render_sprite.py runs the same checks before drawing.

A .pix file is plain text:
    - lines starting with '#' are comments / metadata (ignored)
    - blank lines are ignored
    - every other line is one grid row of single characters

Exit codes: 0 = valid, 1 = validation failed, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class SpriteError(Exception):
    """Raised when a spec or sprite is malformed or inconsistent."""


def load_spec(path: Path) -> dict[str, Any]:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SpriteError(f"spec not found: {path}")
    except json.JSONDecodeError as e:
        raise SpriteError(f"spec is not valid JSON: {e}")
    for key in ("canvas", "legend", "transparent_char"):
        if key not in spec:
            raise SpriteError(f"spec missing required key '{key}'")
    if "width" not in spec["canvas"] or "height" not in spec["canvas"]:
        raise SpriteError("spec.canvas must have width and height")
    if len(str(spec["transparent_char"])) != 1:
        raise SpriteError("spec.transparent_char must be a single character")
    return spec


def parse_pix(path: Path) -> list[str]:
    """Return the grid rows of a .pix file (comments/blanks stripped)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SpriteError(f"sprite not found: {path}")
    rows: list[str] = []
    for line in raw.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        # Preserve internal spaces only if they are the transparent char;
        # trailing newline already removed. Keep the row verbatim.
        rows.append(line.rstrip("\n"))
    if not rows:
        raise SpriteError("sprite has no grid rows (only comments/blanks)")
    return rows


def validate_grid(rows: list[str], spec: dict[str, Any]) -> list[str]:
    """Return a list of human-readable error strings (empty == valid)."""
    errors: list[str] = []
    width = int(spec["canvas"]["width"])
    height = int(spec["canvas"]["height"])
    legend = spec["legend"]
    transparent = str(spec["transparent_char"])
    allowed = set(legend) | {transparent}

    if len(rows) != height:
        errors.append(
            f"row count {len(rows)} != canvas height {height}")

    for i, row in enumerate(rows, start=1):
        if len(row) != width:
            errors.append(
                f"row {i}: width {len(row)} != canvas width {width} "
                f"(row content: {row!r})")
        bad = sorted({ch for ch in row if ch not in allowed})
        if bad:
            errors.append(
                f"row {i}: off-palette characters {bad} "
                f"(allowed: {sorted(allowed)})")

    # Transparency sanity: if the spec wants a transparent background but
    # the grid never uses the transparent char, the nukki was likely missed.
    if spec.get("background", "transparent") == "transparent":
        if not any(transparent in row for row in rows):
            errors.append(
                f"background is transparent but transparent_char "
                f"{transparent!r} never appears - the cut-out (nukki) is "
                f"missing; mark background pixels with {transparent!r}")
    return errors


def rows_to_text(rows: list[str], header: str | None = None) -> str:
    """Serialize grid rows back into .pix text (optional '# header' line)."""
    lines: list[str] = []
    if header:
        lines.append(f"# {header}")
    lines.extend(rows)
    return "\n".join(lines) + "\n"


def write_pix(rows: list[str], path: Path, header: str | None = None) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(rows_to_text(rows, header), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprite", type=Path, help="path to .pix file")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
        rows = parse_pix(args.sprite)
        errors = validate_grid(rows, spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if errors:
        print(f"FAIL: {args.sprite} ({len(errors)} issue(s))", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    used = sorted({ch for row in rows for ch in row
                   if ch != str(spec["transparent_char"])})
    print(f"OK: {args.sprite} valid against {args.spec}")
    print(f"  {spec['canvas']['width']}x{spec['canvas']['height']} grid, "
          f"{len(used)} palette color(s) used: {used}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
