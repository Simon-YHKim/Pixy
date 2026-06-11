#!/usr/bin/env python3
"""Generate classic motion-cycle frames from ONE base .pix - no redrawing.

Usage:
    animate_fx.py base.pix --spec pixy.spec.json --fx hover --frames 6 \
        --out idle [--gif idle.gif --fps 8]

Most game animation is not redrawn limbs - it is a handful of deterministic
transforms applied to one sprite. This generates those cycles in-spec:

    bob     - up on the beat, settle back (idle; amp px, classic 2-frame at N=2)
    hover   - smooth +-amp sine float (ghosts, pickups, UI)
    breathe - the top half compresses 1px and releases (idle breathing)
    sway    - lean left/right, feet pinned (plants, flames, antennas)
    spin    - horizontal squash + mirrored back half (coins, pickups)
    shake   - fast horizontal jitter (hit reaction, earthquake)
    blink   - eyes close on one frame (--eye-char, blobs <=12px in the
              upper half are the eyes)
    flash   - frame 0 is a solid bright silhouette (damage flash)

Writes <out>_0.pix .. <out>_{N-1}.pix (all validated against the spec) and,
with --gif, assembles them via animate.py. Compose effects by chaining runs
(the output of one fx is a valid base for another).

Exit codes: 0 = written, 1 = a frame failed validation, 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid, write_pix  # noqa: E402

FX = ("bob", "hover", "breathe", "sway", "shake", "blink", "flash",
      "spin")
NEI4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def bbox(grid, transparent):
    ys = [y for y, row in enumerate(grid)
          for c in row if c != transparent]
    xs = [x for row in grid
          for x, c in enumerate(row) if c != transparent]
    if not ys:
        raise SpriteError("the base sprite is empty")
    return min(xs), min(ys), max(xs), max(ys)


def shift(grid, transparent, dx, dy):
    h, w = len(grid), len(grid[0])
    out = [[transparent] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c == transparent:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                out[ny][nx] = c
    return out


def shift_rows_partial(grid, transparent, y_from, y_to, dx, dy):
    """Move only rows [y_from, y_to) by (dx, dy), painting over what's
    underneath (squash/lean semantics)."""
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for y in range(y_from, y_to):
        for x in range(w):
            if grid[y][x] != transparent:
                out[y][x] = transparent
    for y in range(y_from, y_to):
        for x in range(w):
            c = grid[y][x]
            if c == transparent:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                out[ny][nx] = c
    return out


def eye_blobs(grid, transparent, eye_char, y_limit, max_size=12):
    """Connected blobs of eye_char in the upper region, small enough to be
    eyes (not an outline)."""
    h, w = len(grid), len(grid[0])
    seen = set()
    blobs = []
    for y in range(0, y_limit):
        for x in range(w):
            if grid[y][x] != eye_char or (x, y) in seen:
                continue
            comp = [(x, y)]
            seen.add((x, y))
            qi = 0
            while qi < len(comp):
                cx, cy = comp[qi]
                qi += 1
                for dx, dy in NEI4:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen \
                            and grid[ny][nx] == eye_char and ny < y_limit:
                        seen.add((nx, ny))
                        comp.append((nx, ny))
            if len(comp) <= max_size:
                blobs.append(comp)
    return blobs


def make_frames(base, spec, fx, n, amp, eye_char=None, flash_char=None):
    transparent = str(spec["transparent_char"])
    grid = [list(r) for r in base]
    x0, y0, x1, y1 = bbox(grid, transparent)
    content_h = max(1, y1 - y0)
    frames = []
    for i in range(n):
        t = i / n
        s = math.sin(2 * math.pi * t)
        if fx == "bob":
            g = shift(grid, transparent, 0, -round(amp * max(0.0, s)))
        elif fx == "hover":
            g = shift(grid, transparent, 0, -round(amp * s))
        elif fx == "breathe":
            off = round(amp * max(0.0, s))
            split = y0 + max(1, content_h // 2)
            g = shift_rows_partial(grid, transparent, y0, split, 0, off) \
                if off else [row[:] for row in grid]
        elif fx == "sway":
            lean = amp * s
            g = [row[:] for row in grid]
            for band in range(4):                  # top leans most, feet pinned
                by0 = y0 + content_h * band // 4
                by1 = y0 + content_h * (band + 1) // 4
                dx = round(lean * (4 - band) / 4)
                if dx:
                    g = shift_rows_partial(g, transparent, by0, by1, dx, 0)
            frames.append(g)
            continue
        elif fx == "spin":
            # classic coin spin: width scales with cos(2*pi*t); the back half
            # (cos < 0) is mirrored. Nearest-column resample around the
            # bbox center keeps it in-spec.
            s = math.cos(2 * math.pi * t)
            mag = max(0.12, abs(s))
            cxf = (x0 + x1) / 2.0
            h2, w2 = len(grid), len(grid[0])
            g = [[transparent] * w2 for _ in range(h2)]
            for yy in range(h2):
                for xx in range(w2):
                    c = grid[yy][xx]
                    if c == transparent:
                        continue
                    off = (xx - cxf) * mag
                    nx = int(round(cxf + (off if s >= 0 else -off)))
                    if 0 <= nx < w2:
                        g[yy][nx] = c
        elif fx == "shake":
            g = shift(grid, transparent,
                      round(amp * math.sin(2 * math.pi * t * 2)), 0)
        elif fx == "blink":
            if not eye_char:
                raise SpriteError("--fx blink requires --eye-char")
            g = [row[:] for row in grid]
            if i == max(0, n * 2 // 3):            # one closed-eyes frame
                limit = y0 + max(1, int(content_h * 0.55))
                blobs = eye_blobs(g, transparent, eye_char, limit)
                if not blobs:
                    raise SpriteError(f"--fx blink: no small {eye_char!r} "
                                      f"blobs found in the upper half")
                for comp in blobs:
                    for (bx, by) in comp:
                        neigh = [g[by + dy][bx + dx] for dx, dy in NEI4
                                 if 0 <= bx + dx < len(g[0])
                                 and 0 <= by + dy < len(g)
                                 and g[by + dy][bx + dx]
                                 not in (transparent, eye_char)]
                        g[by][bx] = Counter(neigh).most_common(1)[0][0] \
                            if neigh else transparent
        elif fx == "flash":
            if i == 0:
                fc = flash_char
                if not fc:
                    legend = {c: v for c, v in spec["legend"].items()
                              if str(v).startswith("#")}   # skip "transparent"
                    fc = max(legend, key=lambda c: (
                        0.299 * int(legend[c][1:3], 16)
                        + 0.587 * int(legend[c][3:5], 16)
                        + 0.114 * int(legend[c][5:7], 16)))
                g = [[fc if c != transparent else c for c in row]
                     for row in grid]
            else:
                g = [row[:] for row in grid]
        else:
            raise SpriteError(f"unknown fx {fx!r}")
        frames.append(g)
    return frames


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("base", type=Path, help="base .pix sprite")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--fx", choices=FX, required=True)
    p.add_argument("--frames", type=int, default=6, help="cycle length")
    p.add_argument("--amp", type=float, default=1.0, help="amplitude in px")
    p.add_argument("--eye-char", help="legend char of the eyes (blink)")
    p.add_argument("--flash-char", help="legend char for the flash frame")
    p.add_argument("--out", required=True,
                   help="frame prefix: writes <out>_0.pix ..")
    p.add_argument("--gif", type=Path, help="also assemble a looping GIF")
    p.add_argument("--fps", type=int, default=8)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.frames < 2:
        print("error: --frames must be >= 2", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        base = parse_pix(args.base)
        errs = validate_grid(base, spec)
        if errs:
            raise SpriteError(f"base is invalid: {'; '.join(errs)}")
        frames = make_frames(base, spec, args.fx, args.frames, args.amp,
                             args.eye_char, args.flash_char)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    paths = []
    for i, g in enumerate(frames):
        rows = ["".join(r) for r in g]
        errs = validate_grid(rows, spec)
        if errs:
            print(f"error: frame {i} invalid: {errs[0]}", file=sys.stderr)
            return 1
        fp = Path(f"{args.out}_{i}.pix")
        write_pix(rows, fp, header=f"{args.fx} frame {i}/{len(frames)} "
                                   f"from {args.base.name}")
        paths.append(fp)
    print(f"wrote {len(paths)} frame(s): {paths[0]} .. {paths[-1]}")

    if args.gif:
        import animate
        rc = animate.main(["--spec", str(args.spec), "--frames",
                           *[str(fp) for fp in paths], "--out",
                           str(args.gif.with_suffix("")), "--format", "gif",
                           "--fps", str(args.fps)])
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
