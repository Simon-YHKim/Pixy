# The .pix Character-Grid Format

A `.pix` file is the editable source for one sprite. It is plain text,
diff-friendly, and renders deterministically through the project spec.

## Rules

- Lines starting with `#` are comments / metadata — ignored by the tools.
- Blank lines are ignored.
- Every other line is one **grid row**: a string of single characters.
- Each character maps to a color via the spec `legend`. The
  `transparent_char` (default `.`) is the background / cut-out.
- The number of rows must equal `canvas.height`; each row's length must
  equal `canvas.width`. `check_sprite.py` enforces both.

## Minimal example (8×8 spec)

    # name: heart, 8x8
    ..RR.RR.
    .RRRRRRR
    .RRRRRRR
    .RRRRRRR
    ..RRRRR.
    ...RRR..
    ....R...
    ........

Here `R` is a legend color and `.` is transparent. With `scale` 8 this
exports a 64×64 PNG with a cut-out background.

## Authoring tips

- **Draw the silhouette first.** Block the overall shape in the base
  color, then add the outline character around the edge, then shade.
- **Use the ramp, not new colors.** Pick darker/lighter legend entries
  for shadow and highlight — never introduce an off-legend hex (the
  renderer rejects it anyway).
- **Keep one light source.** Match `conventions` (default: top-left), so
  every asset in the project is lit the same way.
- **Selective outline.** A 1px outline on the outer edge and major
  internal boundaries reads cleaner than outlining everything.
- **Count your columns.** If a row is off by one character the validator
  will tell you which row and by how much — fix and re-check.

## Vision QA (multimodal agents)

After `render_sprite.py` writes the PNG, a vision-capable agent should
open it and check against the spec:

- Is the silhouette readable at the intended size?
- Is the light source consistent with `conventions`?
- Are the outline and shading using only legend ramps?
- Is the background fully cut out (no stray opaque pixels)?

Then edit the `.pix` rows and re-render. Code-only agents skip the visual
pass and rely on `check_sprite.py` plus the spec conventions.

## Sprite sheets

For multiple frames, author one `.pix` per frame (e.g. `walk_0.pix`,
`walk_1.pix`) sharing the same spec, render each, and let the engine or a
packer assemble the sheet. Keeping frames as separate sources keeps each
one small and individually validatable.
