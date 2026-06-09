#!/usr/bin/env python3
"""Stamp assets with the spec fingerprint and detect style drift.

Usage:
    style_lock.py *.pix --spec pixy.spec.json            # stamp each .pix
    style_lock.py *.pix --spec pixy.spec.json --check    # detect drift

The spec has a `spec_id` fingerprint that changes whenever the locked style
(canvas, scale, palette, background, transparency, shading, frame) changes.
Stamping writes `# pixy-spec: <id>` into each .pix; --check then flags any
asset whose stamp does not match the CURRENT spec - i.e. it was made before
the spec was edited and should be re-validated/redone for consistency.

Exit codes: 0 = ok, 1 = drift found (--check), 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, spec_id  # noqa: E402

STAMP_RE = re.compile(r"^#\s*pixy-spec:\s*([0-9a-f]+)\s*$")


def read_stamp(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        m = STAMP_RE.match(line)
        if m:
            return m.group(1)
    return None


def write_stamp(path, sid):
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
             if not STAMP_RE.match(ln)]
    path.write_text(f"# pixy-spec: {sid}\n" + "\n".join(lines) + "\n",
                    encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprites", type=Path, nargs="+")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--check", action="store_true", help="report drift, do not write")
    args = p.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    cur = spec.get("spec_id") or spec_id(spec)

    if not args.check:
        for sp in args.sprites:
            if not sp.exists():
                print(f"error: {sp} not found", file=sys.stderr)
                return 2
            write_stamp(sp, cur)
        print(f"stamped {len(args.sprites)} file(s) with spec_id {cur}")
        return 0

    drift, unstamped, ok = [], [], 0
    for sp in args.sprites:
        sid = read_stamp(sp)
        if sid is None:
            unstamped.append(sp.name)
        elif sid != cur:
            drift.append(f"{sp.name} (made on {sid}, current {cur})")
        else:
            ok += 1
    print(f"spec_id {cur}: {ok} match, {len(drift)} drifted, "
          f"{len(unstamped)} unstamped")
    for d in drift:
        print(f"  DRIFT {d}")
    for u in unstamped:
        print(f"  unstamped {u}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
