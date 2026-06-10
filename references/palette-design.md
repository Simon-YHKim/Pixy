# Palette Design and Locking

The palette is the strongest consistency lever. A small, deliberate
palette shared across every asset is what makes a set look like one set.

## Size

- **12–16 colors** suit most projects: enough for a few ramps plus
  accents, small enough to stay coherent.
- **32 colors** only when the project genuinely needs many materials.
- More colors = more ways for assets to diverge. Prefer fewer.

## Build in ramps, not singletons

Group colors into **ramps** — a dark→light run of one hue used for
shadow → base → highlight. Shade by stepping along a ramp, never by
picking an arbitrary new color.

    shadow      base       highlight
    #333c57  →  #566c86  →  #94b0c2     (cool grey ramp)
    #b13e53  →  #ef7d57  →  #ffcd75     (warm ramp)

The default legend ships dark/mid/light neutrals (`K D B L W`), a warm
ramp (`r R o`), greens (`g G`), blues (`b c`), purples (`p P`), and
browns (`n N`). Reuse these roles consistently: `K` is always the
outline, `W` always the brightest highlight.

## Outline convention

- **Selective 1px outline** (default): outline the outer silhouette and
  major internal edges with the darkest color (`K`), not every boundary.
- Keep the outline color fixed across the whole project so silhouettes
  read uniformly.

## Shading and light

- **One light source** for the project (default top-left). Highlights go
  on the side facing the light; shadows opposite.
- **No anti-aliasing.** Pixel art uses hard edges; let the `scale`
  upscale stay nearest-neighbor. Selective hand-placed "anti-alias"
  pixels are an advanced choice, not a default.
- **Dithering** (checkerboard of two ramp colors) is optional for
  gradients; if used, document it in `conventions` so every asset
  dithers the same way.

## Locking and changing

- Agree the palette during setup and **freeze it** in the spec. Mid-
  project palette changes are the most common cause of an inconsistent
  set.
- To add a color: edit the spec `legend` deliberately, document its role
  in `conventions`, then re-run `check_sprite.py` on existing sprites so
  nothing silently fell off-palette.

## Building and importing palettes: palette_tool.py

`scripts/palette_tool.py` generates and imports palettes:

    python scripts/palette_tool.py --ramp 3b5dc9 --steps 5
    python scripts/palette_tool.py --import lospec.gpl --apply pixy.spec.json --force
    python scripts/palette_tool.py --from-spec pixy.spec.json --check

- `--ramp BASE --steps N` builds a dark-to-light ramp from one base color (an
  HSL lightness sweep with a slight warm shift toward the light).
- `--import FILE` reads a `.hex` (one RRGGBB per line) or `.gpl` (GIMP)
  palette - the formats Lospec exports - so any Lospec palette drops in.
- `--apply SPEC --force` replaces that spec's legend; otherwise the legend
  prints as JSON. `--check` lists each color's luminance to catch ramps whose
  steps are too close in value.

## From a sample image

When the palette comes from a reference, `scripts/analyze_sample.py`
extracts it (see style-from-sample). Review the result: quantization can
merge near-duplicate shades, and you may want to relabel colors into clean
ramps before locking.

## Hue-shifted ramps in derived palettes

Straight same-hue ramps read flat and digital; period palettes always bend
shadows toward cool (blue) and highlights toward warm. `analyze_sample`
groups a derived palette into hue-family ramps automatically (written to the
spec's `shading.materials`, so `shade_form --material` works on derived
specs), and `--hue-shift` applies the retro bend to each colorful ramp's end
colors. `palette_tool --ramp HEX --hue-shift` builds new ramps the same way.
