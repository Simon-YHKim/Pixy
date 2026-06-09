# Editing and Authoring Tools

Three scripts speed up making and changing `.pix` art without hand-counting
every cell. All keep the locked palette: results are validated against the
spec.

## Import an image as editable art: trace_image.py

`analyze_sample.py` recovers the *style* (palette, size) from a reference;
`trace_image.py` recovers the *art* so you can edit it:

    python scripts/trace_image.py reference.png --spec pixy.spec.json --out traced.pix

It maps each pixel to the nearest legend color (transparent/low-alpha
pixels become the transparent_char). By default it first detects the
reference's native pixel size and drops the image to that grid before
fitting the spec canvas, so a clean upscaled source traces without edge
blur; pass `--no-detect` to resize the source directly. The output is a
draft - nearest-color mapping is approximate, so clean it up by hand and run
`check_sprite.py`. Pair with `analyze_sample.py` when both the style and the
art come from the same reference.

## Batch operations: batch.py

Apply one operation across many files (a glob) to keep a whole asset set
consistent:

    python scripts/batch.py check  --spec pixy.spec.json --glob "sprites/*.pix"
    python scripts/batch.py render --spec pixy.spec.json --glob "sprites/*.pix" --out-dir png
    python scripts/batch.py recolor --spec pixy.spec.json --glob "red/*.pix" \
        --recolor r:b,R:c --out-dir blue --force

Ops are `check`, `lint`, `render`, and `recolor`. The command prints a
per-file result and exits non-zero if any file fails - good for a project
sweep or a pre-commit check.

## Block in shapes: draw_pix.py

Reduce off-by-one errors when blocking a sprite. Ops use grid coordinates
(x, y from top-left, 0-based) and a legend char; `,fill` fills a rect or
circle. Ops apply in order.

    python scripts/draw_pix.py --spec pixy.spec.json --out body.pix \
        --circle 16,16,10,g,fill --dot 12,13,W --line 2,20,29,20,K \
        --mirror x --outline K

- `--dot x,y,CHAR` / `--line x1,y1,x2,y2,CHAR`
- `--rect x,y,w,h,CHAR[,fill]` / `--circle cx,cy,r,CHAR[,fill]`
- `--fill-area x,y,CHAR` flood-fills (bucket) the connected region at x,y.
- `--mirror x|y` mirrors the half you drew across the center axis - draw one
  side, get a symmetric sprite.
- `--outline CHAR` adds a 1px outline around all solid pixels.
- `--in existing.pix` edits an existing grid instead of a blank canvas.

Hand-authoring is still best for fine detail; use `draw_pix` for the blocking
pass, then refine the grid directly.

## Flip, rotate, recolor: transform_pix.py

    python scripts/transform_pix.py hero.pix --flip h --out hero_left.pix
    python scripts/transform_pix.py hero.pix --rotate 90 --out hero_r.pix
    python scripts/transform_pix.py red.pix --recolor r:b,R:c,o:L \
        --out blue.pix --spec pixy.spec.json

- `--flip h|v` mirrors the sprite. `flip h` makes the opposite-facing sprite
  (right-facing from left-facing) for free.
- `--rotate 90|180|270` rotates clockwise; 90/270 require a square canvas.
- `--recolor FROM:TO,...` remaps legend chars to make palette variants (a
  red enemy into a blue one) while staying inside the locked palette.

### Directional sprites

Left and right facings come directly from `--flip h`. Up- and down-facing
views show different anatomy (back vs front), so author those as separate
`.pix` grids against the same spec rather than rotating - rotation would
smear a side view into nonsense. The spec lock keeps all four facings the
same size and palette.
