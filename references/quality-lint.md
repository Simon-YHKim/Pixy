# Pixel-Art Quality Lint

`check_sprite.py` enforces the hard rules (size, palette, transparency).
`lint_pix.py` goes one level deeper and flags craft issues that pass the hard
rules but read as sloppy.

    python scripts/lint_pix.py sprite.pix --spec pixy.spec.json
    python scripts/lint_pix.py sprite.pix --spec pixy.spec.json --strict

## What it flags

- **Orphan pixel** - a solid pixel whose four neighbors are all transparent.
  Usually stray noise or a misplaced dot. Intentional sparkles are the
  exception; judge in context.
- **Single-pixel hole** - a transparent pixel fully surrounded by solid
  pixels. Often an unfilled gap inside a shape.
- **Isolated outline pixel** - an outline-colored pixel with no adjacent
  outline pixel, i.e. a broken 1px outline. Only checked when the spec
  declares an `outline.char`.

Two opt-in checks:

- `--tileable` treats the grid as a repeating tile (wraps edges) and reports
  seam holes/orphans - use it on map tiles so the tile repeats without a
  visible seam.
- `--max-colors N` warns when a sprite uses more than N palette colors, for
  hardware caps (e.g. NES-style "4 colors per sprite").

## How to use it

By default lint prints findings and exits 0 (advisory). Run it after
`check_sprite.py` passes, as the last quality pass before rendering or
animating. With `--strict` it exits 1 on any finding, so it can gate a
pipeline or a batch.

Findings are heuristics, not hard errors - a deliberate floating glint or a
single-pixel eye will trip "orphan pixel". Read each finding and decide; the
goal is to catch accidental noise, not to forbid valid art. For a batch of
frames, lint each one so a stray pixel does not flicker through an animation.
