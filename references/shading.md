# Quality: Shading, Form, and Reaching Reference Level

## Contents

- [Why flat output looks like a doodle](#why-flat-output-looks-like-a-doodle)
- [Block then shade](#block-then-shade)
- [shade_form.py](#shade_formpy)
- [Forms and light](#forms-and-light)
- [Ramps make or break it](#ramps-make-or-break-it)
- [Resolution](#resolution)
- [Reaching a specific reference](#reaching-a-specific-reference)

## Why flat output looks like a doodle

Pixel art reads as "finished" because of **volume** (highlights, mid-tones,
shadows, rim light) and **clean form**, not outlines alone. Authoring that
volume one pixel at a time across thousands of cells is where output
collapses into a flat blob. The fix is to stop hand-placing shades: block a
flat silhouette, then let the light model shade it.

## Block then shade

1. Block the flat silhouette in a single base color with `draw_pix.py`
   (shapes, `--mirror`, `--fill-area`). Keep each material as its own char.
2. Shade each material region with `shade_form.py`, choosing the form that
   matches its geometry (a head is a sphere, a pole is a cylinder).
3. Validate and render as usual. Iterate: render, look, adjust the ramp or
   form, re-shade.

This is how clean pixel art is actually constructed - forms plus a
consistent light, not freehand pixels.

## shade_form.py

    python scripts/shade_form.py body.pix --spec spec.json --region g \
        --ramp "p,D,b,c,W" --form sphere --light tl --rim --ao --out body.pix

Recolors every pixel of `--region` using `--ramp` (dark->light legend chars)
by a per-pixel light value. Options:

- `--form` - the geometry (see below).
- `--light` - direction: `tl tr bl br t b l r` (top-left default).
- `--rim` - a bright reflected-light edge on the shadow side (big "pop").
- `--ao` - darken the shaded edges (ambient occlusion).
- `--dither` - checkerboard between ramp steps for smoother gradients.

Output stays in the locked palette, so `check_sprite.py`/`lint_pix.py` still
apply. Shade one region at a time for multi-material sprites.

## Forms and light

| Form | Use for |
|------|---------|
| `sphere` | heads, balls, gems, studs, fruit |
| `cyl-v` | vertical poles, bottles, tree trunks, frame bars |
| `cyl-h` | horizontal logs, pipes, rolled scrolls |
| `round` | puffy/organic blobs - center bright, edges fall off |
| `flat` | walls, cards, flat panels (pure directional gradient) |

Keep one light direction for the whole asset (and project). The light model
is deterministic, so the same silhouette and settings always shade the same.

## Ramps make or break it

A ramp is an ordered dark->light run of one hue. Use 3-5 steps; more reads
smoother but needs more pixels. Build ramps with `palette_tool.py --ramp`,
or pick from the default palette's families (cool greys `D B L W`, gold
`n N o W`, blues `D b c W`). Reusing the same ramp per material is what makes
a set look unified. Do not shade with arbitrary colors - stay on the ramp.

## Resolution

Detail needs pixels. A 16x16 grid cannot hold a shaded emblem. Match the
canvas to the ambition:

- 16-24: icons, tiles, small sprites
- 32-48: characters with simple shading (`icon-hd` preset)
- 64-96: portraits and detailed emblems (`portrait`, `emblem` presets)

Bigger canvases are why a reference badge looks rich and a 32px sprite looks
simple - it is room, not magic.

## Reaching a specific reference

A detailed reference (e.g. a shaded book-and-quill emblem) is expert/HD
pixel art. The realistic way to hit *that exact level* is not a text prompt -
it is to reproduce a reference:

    python scripts/trace_image.py reference.png --derive 32 \
        --out-spec emblem.spec.json --out emblem.pix

`--derive N` builds an N-color palette matched to the image and a spec sized
to its native grid, then traces it - a faithful, editable reproduction in one
command. Clean it up by hand, then it animates and stays consistent like any
other Pixy asset. Use shading for original work; use derive-trace when a
reference defines the bar.
