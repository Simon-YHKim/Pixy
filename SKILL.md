---
name: pixy-the-pixel-art
description: Use when the user wants to create, generate, animate, or maintain pixel-art assets with a consistent style — sprites, tiles, icons, avatars, animations. Triggers on "픽셀아트 만들어줘", "pixy로 에셋 만들어", "generate a pixel art sprite", "make a pixel asset", "이 스타일 따라서 픽셀아트", "pixel art from this image", "애니메이션 만들어", "animate this sprite", "sprite sheet". Locks a per-project style spec (canvas size, scale, palette, transparency/누끼 rules) so any agent — Claude, Codex, GPT, Gemini — renders identical, palette-locked, transparent PNGs from a character-grid (.pix) source via a deterministic Pillow renderer. Covers any target via use-case and game-engine presets, derives a spec from a reference image, and animates frames into GIF, APNG, and sprite sheets. Produces .png/.gif, pixy.spec.json, and .pix files. Use whenever a request involves pixel art, sprite sheets, animation, or game assets.
version: 0.4.0
compatibility:
  - python>=3.9
  - pillow>=9.0
---

# Pixy The Pixel Art

## Overview

Produce pixel-art assets that look the same every time, regardless of
which model draws them. Consistency does not come from the model's
drawing talent — it comes from a locked, per-project **style spec**
(`pixy.spec.json`) plus a **deterministic renderer**. The agent's only
creative job is authoring a character grid (`.pix`) using the project's
locked palette; the renderer enforces canvas size, pixel scale, the
exact palette, and the transparent background (누끼). Same grid → same
PNG, byte for byte. Vision-capable agents additionally look at the
rendered result and self-correct against the spec.

## Workflow

Dispatch on the request, then follow that path. Always interview the
user before creating the first spec — do not guess the canvas size,
palette, or transparency rule.

**No spec yet, or "set up Pixy" / "새 픽셀아트 프로젝트"** → Setup.
**"이 이미지 스타일로" / "pixel art from this image" + a file** → From sample.
**Spec exists, "make/draw an asset" / "에셋 만들어"** → Create asset.
**"이 스프라이트 수정" / "edit this asset"** → Edit asset.
**"애니메이션 만들어" / "animate" / "sprite sheet"** → Animate.

### Setup (interview → lock the spec)

Run the intake interview, then materialize the spec. Ask at most 4
questions at a time, in the user's language:

1. **Use / environment?** game sprite, tileset, UI icon, web avatar,
   emoji, marquee art — this sets canvas size and export scale.
2. **Native size & export scale?** the grid the art is drawn on (e.g.
   16×16, 32×32) and the upscale factor for the exported PNG (scale 8 →
   a 32×32 grid exports at 256×256). Smaller grid = chunkier, fewer cells.
3. **Transparency (누끼)?** transparent background (default for
   sprites/icons) or a solid background color.
4. **Palette?** a fixed color count (12 / 16 / 32) — Pixy proposes a
   balanced default the user can edit, or the user supplies hex colors.

Then run a preset (see `references/spec-schema.md` for the table):

    python scripts/init_spec.py --out pixy.spec.json --preset game-character

Override any field with flags, e.g. `--canvas 24x24 --scale 10
--background transparent`. Presets cover generic use cases, game engines
(`unity`, `godot`, `rpgmaker`), and palette-locked consoles (`gameboy`,
`pico8`); for any other target, read `references/engine-targets.md` and set
the canvas/background/palette directly. Show the resulting palette to the
user and adjust before locking. **Gate:** `pixy.spec.json` exists and the
user has approved the palette.

### From sample (derive a spec from a reference image)

1. Extract the hard data from the image:

       python scripts/analyze_sample.py reference.png --out pixy.spec.json --colors 16

   This detects the palette, the alpha/누끼 status, and estimates the
   native pixel size, writing a **draft** spec.
2. If the agent is vision-capable, open `reference.png` and read
   `references/style-from-sample.md` to refine the conventions
   (light source, outline style, shading, dithering) in prose.
3. Confirm the detected native size and palette with the user, then
   lock. **Gate:** the draft spec is reviewed, not blindly accepted.
4. To import the art itself (not just the style) as an editable grid, run
   `python scripts/trace_image.py reference.png --spec pixy.spec.json --out
   traced.pix`, then clean it up and validate. See `references/editing.md`.

### Create asset

Copy this checklist and tick off as you go:

    - [ ] 1. Read pixy.spec.json (canvas, scale, legend, transparent_char)
    - [ ] 2. Author the .pix grid using ONLY the spec legend characters
    - [ ] 3. Validate: python scripts/check_sprite.py asset.pix --spec pixy.spec.json
    - [ ] 4. Render:  python scripts/render_sprite.py asset.pix --spec pixy.spec.json --out asset.png
    - [ ] 5. If vision-capable: open asset.png, check silhouette/readability against the spec, edit grid, re-render
    - [ ] 6. Report the path, dimensions, and palette used

The grid is plain text: comment lines start with `#`, every other line
is one row of single characters. Each character maps to a palette color
via the spec legend; the `transparent_char` (default `.`) is the
background. See `references/authoring-format.md` for the format and
worked examples. To block in shapes quickly (circle/line/rect, symmetry,
auto-outline) use `scripts/draw_pix.py`, then refine by hand
(`references/editing.md`). For a craft-quality pass, run
`python scripts/lint_pix.py asset.pix --spec pixy.spec.json` to catch orphan
pixels and broken outlines — add `--tileable` for seamless map tiles and
`--max-colors N` for hardware color caps (`references/quality-lint.md`). For
many assets, `scripts/batch.py` runs check/lint/render/recolor over a glob.
**Gate:** `check_sprite.py` exits 0 before rendering — it rejects wrong
dimensions, off-palette characters, and silently missing transparency.

### Edit asset

Read the existing `.pix`, modify rows, then re-run steps 3–6 above.
Never edit the `.png` directly — the `.pix` is the source of truth. To make
variants without redrawing, use `scripts/transform_pix.py`: `--flip h` for
the opposite facing, `--rotate` for square sprites, `--recolor FROM:TO` for a
palette swap (e.g. a red enemy into a blue one). See `references/editing.md`.

### Animate

Author one `.pix` per frame against the same spec (e.g. `walk_0.pix` ..
`walk_3.pix`), then produce the animation and sheet in one step:

    python scripts/animate.py --spec pixy.spec.json \
        --frames walk_0.pix walk_1.pix walk_2.pix walk_3.pix \
        --out walk --format all --fps 8

This writes `walk.gif` (looping, transparent), `walk.png` (APNG, full
alpha), `walk_sheet.png`, and `walk_sheet.json` (frame rects + fps for
engine slicing). Use `--format gif|apng|sheet` for one output, `--no-loop`
for one-shot effects, `--pingpong` to play forward then back, `--onion` for
a motion-arc preview, and `--layout grid:4x2` for grid sheets. Frames are
validated against the spec first, so every frame shares the canvas and
palette and the sheet never misaligns. A reusable `.anim.json` manifest
(template: `templates/walk.anim.json.tmpl`) can replace `--frames` and can
set per-frame timing. Export the sheet to Aseprite JSON or a CSS page with
`scripts/export_engine.py`. See `references/animation.md`. **Gate:** all
frames pass `check_sprite.py` before animating.

## The consistency contract

Three locks make every agent converge on the same output. Read
`references/consistency-rules.md` for the full rationale and the
vision-QA loop:

- **Palette lock** — the legend lives in the spec, shared by every
  `.pix` and every agent. The renderer refuses unknown characters.
- **Canvas lock** — the renderer refuses a grid whose size differs
  from the spec, so every asset exports at the same dimensions.
- **누끼 lock** — `transparent_char` always renders to alpha 0, so
  backgrounds are reliably cut out without manual masking.

## References

- `references/spec-schema.md` — every `pixy.spec.json` field, the
  preset table, and use-case → size/scale mapping.
- `references/authoring-format.md` — the `.pix` character-grid format,
  conventions, and worked sprite examples.
- `references/consistency-rules.md` — how cross-agent consistency is
  enforced and the multimodal vision-QA loop.
- `references/palette-design.md` — choosing and locking palettes,
  color ramps, outline and shading conventions.
- `references/style-from-sample.md` — deriving a spec from a reference
  image (code extraction + vision refinement).
- `references/animation.md` — animating frames into GIF, APNG, and sprite
  sheets; timing, looping, layout, and the `.anim.json` manifest.
- `references/engine-targets.md` — universal coverage: per-engine and
  per-platform settings, presets, configuring any unlisted target, and
  exporting sheets (Aseprite/CSS).
- `references/editing.md` — importing an image to editable art
  (`trace_image`), blocking with shapes (`draw_pix`), and flip/rotate/recolor
  (`transform_pix`).
- `references/quality-lint.md` — the craft-level lint (`lint_pix`): orphan
  pixels, holes, broken outlines.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/init_spec.py` | Scaffold a `pixy.spec.json` from a use-case preset and flags (stdlib only). |
| `scripts/check_sprite.py` | Validate a `.pix` grid against the spec — dimensions, palette, transparency (stdlib only). |
| `scripts/render_sprite.py` | Render a `.pix` grid to a transparent, exact-size PNG with nearest-neighbor upscale (Pillow). |
| `scripts/analyze_sample.py` | Derive a draft spec (palette, alpha, native size) from a reference image (Pillow). |
| `scripts/animate.py` | Combine `.pix` frames into a GIF, APNG, and sprite sheet + metadata JSON; ping-pong, per-frame timing, onion-skin (Pillow). |
| `scripts/trace_image.py` | Trace a reference image into an editable `.pix` against the spec palette (Pillow). |
| `scripts/draw_pix.py` | Block in a `.pix` with shapes, symmetry, and auto-outline (stdlib). |
| `scripts/transform_pix.py` | Flip, rotate, or recolor a `.pix` (palette variants, opposite facings) (stdlib). |
| `scripts/lint_pix.py` | Flag pixel-art craft issues — orphan pixels, holes, broken outlines (stdlib). |
| `scripts/palette_tool.py` | Generate color ramps or import `.hex`/`.gpl` (Lospec) palettes into a spec (stdlib). |
| `scripts/export_engine.py` | Export a sprite sheet to Aseprite JSON or a CSS `steps()` HTML page (stdlib). |
| `scripts/batch.py` | Run check/lint/render/recolor across many `.pix` via a glob (stdlib; Pillow for render). |

Run any script with `--help` for the full argument list.

## Templates

| Template | Purpose |
|----------|---------|
| `templates/pixy.spec.json.tmpl` | Starter project spec with a balanced 16-color palette. |
| `templates/sprite.pix.tmpl` | Starter character-grid sprite. |
| `templates/walk.anim.json.tmpl` | Starter animation manifest (frames + fps + loop). |

## Principles

- **Lock, don't trust.** The spec and renderer enforce regularity; the
  model only supplies the shapes. Never let an agent invent a new color
  or canvas size mid-asset.
- **Fail loud, succeed quiet.** `check_sprite.py` and `render_sprite.py`
  exit non-zero with a concrete message on any violation; silent on
  success.
- **The `.pix` is the source.** Assets are reproducible from text. Edit
  the grid, never the rendered PNG.
- **Grade the picture, not the prompt.** Vision-capable agents judge the
  rendered PNG against the spec; code-only agents rely on the check gate.
