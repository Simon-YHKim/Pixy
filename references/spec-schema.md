# Pixy Spec Schema (pixy.spec.json)

The spec is the single source of truth for a project's pixel-art style.
Every `.pix` sprite and every agent reads the same file, so a project's
output stays uniform no matter who or what draws it.

## Fields

| Field | Type | Meaning |
|-------|------|---------|
| `name` | string | Project or asset name. Used in export naming. |
| `spec_version` | int | Schema version. Currently `1`. |
| `use_case` | string | Free label (e.g. `game-character`, `from-sample`). |
| `canvas.width` / `canvas.height` | int | Native pixel grid. Every `.pix` must match this exactly. |
| `scale` | int (≥1) | Export upscale factor, nearest-neighbor. 32×32 @ scale 8 → 256×256 PNG. |
| `background` | `"transparent"` or `#RRGGBB` | Transparent = cut-out (nukki). A hex fills the background opaquely. |
| `transparent_char` | single char | The grid character that renders to alpha 0 (or to the background color). Default `.`. |
| `legend` | object | The **locked palette**: `char → #RRGGBB`. The only colors any sprite may use. |
| `outline.char` | char | Which legend color is the outline (documentation for agents). |
| `outline.style` | string | Outline convention, e.g. `selective-1px`. |
| `shading` | object | Locked shading style for uniform output: `light` direction, `outline` char, `rim`/`ao` defaults, and named `materials` ramps. `shade_form.py --material NAME` reads it. |
| `frame` | object | Locked proportions/placement (fractions of canvas): `margin` safe-area, `baseline`, `center_axis`, `content_height` target, `pivot`, `symmetry`. `proportions.py` and `frame_guide.py` read it to keep size/placement uniform. |
| `conventions` | string | Prose style rules: light source, shading, dithering. Read by the agent before drawing. |
| `export.format` | string | Output format. `png`. |
| `export.naming` | string | Filename pattern, e.g. `{name}.png`. |

The renderer only requires `canvas`, `scale`, `legend`, `transparent_char`,
and `background`. The rest guides the agent's drawing.

## Use-case presets

`scripts/init_spec.py --preset NAME` sets canvas and scale defaults.
Override any field with flags (`--canvas 24x24 --scale 10`).

| Preset | Canvas | Scale | Background | Use |
|--------|--------|-------|------------|-----|
| `game-character` | 32×32 | 8 | transparent | Character sprite |
| `tileset` | 16×16 | 8 | transparent | Map tile |
| `ui-icon` | 24×24 | 10 | transparent | Interface icon |
| `web-avatar` | 64×64 | 4 | transparent | Profile art |
| `emoji` | 16×16 | 6 | transparent | Small glyph |
| `marquee` | 128×64 | 3 | `#1a1c2c` | Banner / title |

## Choosing canvas and scale by environment

- **Smaller canvas = chunkier art, fewer cells to author.** A 16×16 grid
  is faster for an agent to draw and reads clearly at small sizes.
- **Scale only affects export, not style.** Pick a scale so the exported
  PNG fits the target (icons ~240px, avatars ~256px, tiles for the
  engine's native tile size × an integer).
- **Game engines:** match the engine's expected sprite/tile pixel size as
  the native canvas; let the engine handle on-screen scaling, or export at
  scale 1 with `--no-upscale`.
- **Web/UI:** export at an integer scale that lands near the CSS render
  size to avoid the browser re-blurring the pixels.

## Locking discipline

Once a project's palette and canvas are agreed, do **not** change them
mid-project — that is what breaks consistency. Add colors only by editing
the spec deliberately, then re-validate existing sprites against the new
legend. See `palette-design.md` for palette construction.
