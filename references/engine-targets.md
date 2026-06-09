# Engine and Platform Targets

Pixy covers any target because the spec is fully parametric: any canvas, any
scale, any palette, transparent or solid background. Presets are shortcuts
for common targets; for anything without a preset, set the fields directly
with `init_spec.py` flags using the table below.

## Presets

Run `python scripts/init_spec.py --list` for the live list. Generic presets
(`game-character`, `tileset`, `ui-icon`, `web-avatar`, `emoji`, `marquee`)
cover most projects. Engine presets add the canvas/scale and import notes a
specific engine expects; console presets also lock the palette.

## Per-target settings

| Target | Native canvas | Background | Palette | Notes |
|--------|---------------|------------|---------|-------|
| Generic sprite | 16-64 px | transparent | default 16 | Pick the smallest size that reads. |
| Unity 2D | match PPU (16/32/64) | transparent | default | Filter Mode Point, Compression None, Pixels-Per-Unit = canvas. |
| Godot | 16 or 32 | transparent | default | Texture filter Nearest; re-import with Filter off. |
| RPG Maker MZ | 48x48 cell | transparent | default | Walk sheet = 3 frames x 4 directions per character. |
| Game Boy (DMG) | 8 or 16 | transparent | 4-shade green (locked) | `--preset gameboy`. |
| PICO-8 | 8 or 16 | transparent | fixed 16 (locked) | `--preset pico8`. |
| NES-style | 8 or 16 | transparent | ≤4 per sprite | Use a 4-color custom palette per sprite. |
| Web / CSS | any | transparent | default | Export at an integer scale near the CSS size to avoid re-blurring. |
| Print / banner | wide | solid hex | default | `--background #RRGGBB`. |

## Configuring an unlisted engine

Three questions decide the spec for any engine:

1. **What native pixel size does the engine expect per sprite/tile?** → set
   `--canvas WxH`.
2. **Does it want transparency or a solid background?** → `--background
   transparent` or `--background #RRGGBB`.
3. **Is the palette constrained by the hardware/style?** → if yes, supply
   those colors (edit the spec `legend` after generating, or pick the
   matching console preset); if no, keep the default 16.

Example — a fantasy console expecting 24x24 sprites, transparent, free
palette:

    python scripts/init_spec.py --out pixy.spec.json --canvas 24x24 \
        --scale 8 --background transparent --name my-console-art

## Exporting animations to an engine

`scripts/export_engine.py` turns an animation's `_sheet.json` into a drop-in
format:

    python scripts/export_engine.py walk_sheet.json --engine aseprite --out walk.json
    python scripts/export_engine.py walk_sheet.json --engine css --out walk.html

- `aseprite` writes an Aseprite-style sheet JSON (frames + durations + a loop
  tag) that many tools and importers read.
- `css` writes a self-contained HTML page that plays the sheet with a CSS
  `steps()` animation - a zero-dependency web preview or embed.

For Unity and Godot, slice the sheet PNG by the cell size in the
`_sheet.json` (`frame_width` x `frame_height`): Unity via Sprite Mode
Multiple, Godot via a `SpriteFrames`/`AnimatedSprite2D` grid.

## Scale vs native size

`scale` never changes the art, only the exported pixel dimensions. Keep the
native canvas at the engine's expected size and let `scale` (nearest-
neighbor) produce a preview large enough to inspect. For engines that scale
sprites themselves, export at native size with `render_sprite.py
--no-upscale`.
