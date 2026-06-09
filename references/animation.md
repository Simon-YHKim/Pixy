# Animating Pixy Assets

Animation is a sequence of frames that share one spec. Because every frame
is validated against the same locked canvas and palette, frames cannot drift
in size or color, so the sheet grid never misaligns and the playback never
flickers between palettes.

## Workflow

1. Author one `.pix` per frame against the project spec, e.g. `walk_0.pix`
   .. `walk_3.pix`. Keep the same canvas; only the drawing changes.
2. Validate each frame: `python scripts/check_sprite.py walk_0.pix --spec
   pixy.spec.json` (the animator also validates, but checking early is
   cheaper).
3. Animate:

       python scripts/animate.py --spec pixy.spec.json \
           --frames walk_0.pix walk_1.pix walk_2.pix walk_3.pix \
           --out walk --format all --fps 8

4. If vision-capable, open `walk.gif` and check the motion: is the loop
   smooth, the timing right, the silhouette stable frame to frame? Adjust a
   frame's `.pix` and re-run.

## Outputs

`--format all` writes four files from basename `<out>`:

| File | Use |
|------|-----|
| `<out>.gif` | Looping animated GIF. Binary transparency (alpha 0 background). Best for quick preview, chat, web. |
| `<out>.png` | Animated PNG (APNG). Preserves full alpha; higher quality than GIF. |
| `<out>_sheet.png` | Single sprite sheet, frames tiled. What most game engines import. |
| `<out>_sheet.json` | Frame rectangles (x, y, w, h), grid, and fps for slicing the sheet. |

Pick a single format with `--format gif|apng|sheet` when you only need one.

## Timing and looping

- `--fps N` sets frames per second (default 8). Walk cycles read well at
  6-12 fps; idle breathing at 2-4 fps.
- Looping is on by default; `--no-loop` plays once (good for one-shot
  effects like an explosion).
- `--pingpong` plays forward then back (e.g. an idle that eases out and in).
  It appends the reversed middle frames, so 4 frames become a 6-step loop.
- Per-frame timing: a manifest frame may be an object with its own
  milliseconds, `{"frame": "f0.pix", "ms": 120}`, mixed with plain strings.
  Frames without `ms` fall back to the `fps` rate. Use this to hold a key
  pose longer than the in-betweens.
- `--onion` also writes `<out>_onion.png`, all frames overlaid with rising
  opacity, to preview the motion arc and check spacing while authoring
  in-betweens.

## Sheet layout

- Default `horizontal` tiles all frames in one row.
- `--layout grid:COLSxROWS` tiles into a grid, e.g. `grid:4x2` for an
  8-frame sheet. The grid must hold every frame or the animator errors.

## Reproducible animations: the manifest

Instead of listing frames on the command line, store them in an
`.anim.json` manifest (template: `templates/walk.anim.json.tmpl`):

    {
      "name": "hero-walk",
      "fps": 8,
      "loop": true,
      "frames": ["walk_0.pix", "walk_1.pix", "walk_2.pix", "walk_3.pix"]
    }

Then: `python scripts/animate.py --spec pixy.spec.json --manifest
hero-walk.anim.json --out hero-walk`. Frame paths in the manifest are
relative to the manifest file. Command-line `--fps`/`--no-loop` override
the manifest.

## Engine import

The `_sheet.json` carries everything an engine needs to slice the sheet:
equal `frame_width`/`frame_height` and per-frame rectangles. In Unity use
Sprite Mode: Multiple and slice by the cell size; in Godot feed the grid
into a `SpriteFrames`/`AnimatedSprite2D`. See engine-targets for per-engine
notes.

For drop-in formats, `scripts/export_engine.py` converts the `_sheet.json`
into an Aseprite-style sheet JSON or a self-contained CSS `steps()` HTML page:

    python scripts/export_engine.py walk_sheet.json --engine aseprite --out walk.json
    python scripts/export_engine.py walk_sheet.json --engine css --out walk.html
