# Animating Pixy Assets

Animation is a sequence of frames that share one spec. Because every frame
is validated against the same locked canvas and palette, frames cannot drift
in size or color, so the sheet grid never misaligns and the playback never
flickers between palettes.

## Three ways to get frames

1. **Generate cycles from ONE sprite (`animate_fx.py`)** - most game motion
   is not redrawn limbs, it is a deterministic transform of one drawing:

       python scripts/animate_fx.py hero.pix --spec pixy.spec.json \
           --fx hover --frames 6 --amp 2 --out hero_idle \
           --gif hero_idle.gif --fps 8

   | fx | motion | classic use |
   |----|--------|-------------|
   | `bob` | up on the beat, settle | grounded idle (N=2 = the classic 2-frame idle) |
   | `hover` | smooth +-amp float | ghosts, pickups, UI icons |
   | `breathe` | top half compresses 1px and releases | idle breathing |
   | `sway` | lean left/right, feet pinned | plants, flames, antennae |
   | `shake` | fast horizontal jitter | hit reaction, earthquake |
   | `blink` | eyes close on one frame (`--eye-char`) | living idle |
   | `flash` | frame 0 = solid bright silhouette | damage flash |

   Effects compose: run one fx, use its frames as bases for another (e.g.
   hover + blink). All frames are validated in-spec.
2. **Hand-author in-betweens** - one `.pix` per frame (`walk_0.pix` ..),
   same canvas, only the drawing changes. This is the path for real limb
   animation (walks, attacks); author against `frame_guide.py`'s overlay and
   keep the feet on the spec baseline.
3. **Image-first frames (`charset.py`)** - have the image model draw the
   cycle, identity-locked, then conform every frame with the one spec:

       python scripts/charset.py --spec char.spec.json \
           --character "a cute blue flame creature" \
           --poses walk_0,walk_1,walk_2,walk_3 --out-dir walk/ \
           --images-dir raw/   # PNGs you generated from its prompts

   charset embeds the SAME character block + frame numbering ("frame 2 of
   4, mid-stride") in every prompt, chains the first image as the img2img
   reference for the rest (`--ref` / `{ref_png}` with a local model), and
   gates the set's palette overlap + craft. Add `--animate walk --fps 8
   --export aseprite` and it finishes the line in the same call: walk.gif +
   sprite sheet + engine export.

## Workflow

1. Get frames by one of the three paths above.
2. Validate each frame: `python scripts/check_sprite.py walk_0.pix --spec
   pixy.spec.json` (the animator also validates, but checking early is
   cheaper).
3. Animate:

       python scripts/animate.py --spec pixy.spec.json \
           --frames walk_0.pix walk_1.pix walk_2.pix walk_3.pix \
           --out walk --format all --fps 8

4. Gate the motion: `python scripts/anim_score.py walk_*.pix --spec
   pixy.spec.json --loop` scores smoothness, flags jumpy transitions that
   need an in-between, and flags a popping LOOP SEAM (last->first changing
   far more than the body of the cycle - fix with a settle frame or
   `--pingpong`).
5. If vision-capable, open `walk.gif` and check the motion: is the loop
   smooth, the timing right, the silhouette stable frame to frame? Adjust a
   frame's `.pix` and re-run.

## Frame-count and fps recipes

| motion | frames | fps | notes |
|--------|--------|-----|-------|
| idle (bob/breathe) | 2-4 | 2-6 | the classic NES idle is 2 frames |
| walk cycle | 4 / 6 / 8 | 8-12 | 4 = retro, 8 = smooth; keep contact frames |
| run cycle | 6-8 | 10-14 | exaggerate lean (sway) on top |
| hit flash | 2-4 | 10-15 | `flash` + `shake`, `--no-loop` |
| attack swing | 3-5 | 10-12 | hold the anticipation frame with per-frame `ms` |
| explosion / one-shot | 5-8 | 10-14 | `--no-loop`; end on transparency |

Easing without more frames: hold key poses longer via per-frame `ms` in the
manifest (anticipation long, action short, settle medium).

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
