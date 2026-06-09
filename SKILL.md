---
name: pixy-the-pixel-art
description: Use when the user wants to create, animate, or assemble pixel-art for games — sprites, tiles, icons, animations, maps, and UI screens — with the same fidelity on any LLM. Triggers on "픽셀아트 만들어줘", "pixy로 에셋 만들어", "generate a pixel sprite", "make a pixel asset", "애니메이션 만들어", "sprite sheet", "맵/타일맵 만들어", "build a HUD", "pixel art from this image". Locks a per-project spec (size, scale, palette, transparency/누끼) so any agent — Claude, Codex, GPT, Gemini — renders identical PNGs from a .pix grid via a deterministic renderer; covers any target via engine/console presets; derives a spec from a reference image; animates frames to GIF/APNG/sheets; and composes tiles, sprites, and pixel text into finished maps and screens. Produces .png/.gif, pixy.spec.json, .pix, and scene/tilemap JSON. Use whenever a request involves pixel art, animation, tilemaps, game UI, or game assets.
version: 0.15.0
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

Pixy is a game-art *implementation* aid, not just an asset maker: it covers
the parts (sprites, tiles, icons), how they assemble (tilemaps, scenes), the
finished result (composed screens), and the UI/UX that packages it (scalable
frames, pixel text).

## Workflow

First understand the request (below), then dispatch on it and follow that
path. Always interview the user before creating the first spec — do not
guess the canvas size, palette, or transparency rule.

**No spec yet, or "set up Pixy" / "새 픽셀아트 프로젝트"** → Setup.
**"이 이미지 스타일로" / "pixel art from this image" + a file** → From sample.
**Spec exists, "make/draw an asset" / "에셋 만들어"** → Create asset.
**"이 스프라이트 수정" / "edit this asset"** → Edit asset.
**"애니메이션 만들어" / "animate" / "sprite sheet"** → Animate.
**"맵/타일맵 만들어" / "HUD" / "화면 구성" / "title screen"** → Compose.

### Understand the request (intent & direction)

Quality and consistency depend on getting the brief right, so do this before
generating anything — not just for the spec:

1. Restate the request in one line and infer the brief: subject and key
   features, style/mood, intended size/use, and any reference image.
2. **If the session is interactive and the request is underspecified, ask
   1–3 concise questions** (subject details, style/mood, reference?, target
   size) in the user's language. In a non-interactive/headless run, or if the
   user said "알아서 해" / "just do it", state your assumptions instead and
   proceed.
3. For a **set** of assets, agree the shared direction first (palette, light,
   outline, resolution) and lock it in the spec's `shading` block, so the
   whole set is coherent.
4. Produce a first result, **show it, and iterate on feedback** before
   batch-generating the rest. Do not silently mass-produce on the first pass.

A wrong brief produces consistent but wrong art — confirm intent first.
**Detail target:** point the user to `assets/calibrator.html` (pre-built, no
tokens; or regenerate with `scripts/detail_calibrator.py`) — they slide
resolution / colors / detail / frames against live Earth/Human examples and
copy a target-detail prompt. Use those 0–100 numbers to pick canvas, palette
size, and shading depth.

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
   For a faithful one-command reproduction of a detailed/HD reference (the
   realistic route to reference-level quality), use `--derive N`:
   `python scripts/trace_image.py reference.png --derive 32 --out-spec
   ref.spec.json --out ref.pix` builds an image-matched palette and spec.
   Check how close you got with `scripts/ref_similarity.py ref.pix
   reference.png --spec ref.spec.json`. See `references/shading.md`.

### Create asset

Copy this checklist and tick off as you go:

    - [ ] 1. Read pixy.spec.json (canvas, scale, legend, transparent_char)
    - [ ] 2. Author the .pix grid using ONLY the spec legend characters
    - [ ] 3. Validate: python scripts/check_sprite.py asset.pix --spec pixy.spec.json
    - [ ] 4. Render:  python scripts/render_sprite.py asset.pix --spec pixy.spec.json --out asset.png
    - [ ] 5. If vision-capable: open asset.png, check silhouette/readability against the spec, edit grid, re-render
    - [ ] 6. Score detail: python scripts/detail_score.py asset.pix --spec pixy.spec.json
    - [ ] 7. Report the path, dimensions, palette, and the detail score (so the user can direct any regeneration)

The grid is plain text: comment lines start with `#`, every other line
is one row of single characters. Each character maps to a palette color
via the spec legend; the `transparent_char` (default `.`) is the
background. See `references/authoring-format.md` for the format and
worked examples. To block in shapes quickly (circle/line/rect, symmetry,
auto-outline) use `scripts/draw_pix.py`, then refine by hand
(`references/editing.md`). **For finished-looking art instead of flat
blobs:** block the silhouette in flat base colors, then add volume with
`scripts/shade_form.py` (sphere/cylinder/bevel forms + rim light + AO +
dither) — do not hand-place shading pixel by pixel. For a **uniform set**,
shade with `--material NAME` (e.g. gold, blue): the light direction, outline,
and ramp come from the spec's locked `shading` block, so every asset and
every agent matches. Use a 48px+ canvas (`icon-hd`, `portrait`, `emblem`
presets) for anything detailed. See `references/shading.md`. For a craft-quality pass, run
`python scripts/lint_pix.py asset.pix --spec pixy.spec.json` to catch orphan
pixels and broken outlines — add `--tileable` for seamless map tiles and
`--max-colors N` for hardware color caps (`references/quality-lint.md`). For
many assets, `scripts/batch.py` runs check/lint/render/recolor over a glob,
and `scripts/gallery.py` builds an HTML scorecard gallery. `scripts/autofix.py`
auto-cleans orphans/holes; `scripts/regen_prompt.py` turns a target score into
next steps; `scripts/consistency_report.py` scores a set's uniformity. Keep size and
placement uniform too: author against `scripts/frame_guide.py`'s overlay and
run `scripts/proportions.py` (`--fit` recenters and drops to the baseline) so
every asset sits in the same frame. Gate a whole set with
`scripts/consistency_report.py --strict --min N`. **Gate:** `check_sprite.py`
exits 0 before rendering — it rejects wrong
dimensions, off-palette characters, and silently missing transparency.

### Edit asset

Read the existing `.pix`, modify rows, then re-run steps 3–6 above.
Never edit the `.png` directly — the `.pix` is the source of truth. To make
variants without redrawing, use `scripts/transform_pix.py`: `--flip h` for
the opposite facing, `--rotate` for square sprites, `--recolor FROM:TO` for a
palette swap (e.g. a red enemy into a blue one). For a whole set of color
variants in one go, use `scripts/variants.py --materials ...`. See
`references/editing.md`.

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
a motion-arc preview, `--register` to keep frames grounded on the spec pivot,
and `--layout grid:4x2` for grid sheets. Frames are
validated against the spec first, so every frame shares the canvas and
palette and the sheet never misaligns. A reusable `.anim.json` manifest
(template: `templates/walk.anim.json.tmpl`) can replace `--frames` and can
set per-frame timing. Export the sheet to Aseprite JSON or a CSS page with
`scripts/export_engine.py`. Rate smoothness with `scripts/anim_score.py`
(flags jumpy frames). See `references/animation.md`. **Gate:** all frames pass
`check_sprite.py` before animating.

### Compose (assemble parts into a finished screen)

Turn parts into a map, HUD, menu, or title screen. The manifests are the
assembly instructions; the rendered PNG is the finished result.

- **Map** — map characters to tile `.pix` files and lay them in a grid:
  `python scripts/tilemap.py level.tmap.json --spec tiles.spec.json --out
  level.png` (template: `templates/tilemap.json.tmpl`).
- **UI frame** — scale a small frame to any size, corners intact:
  `python scripts/nine_slice.py panel.png --insets 4,4,4,4 --size 200x120
  --out hud.png`.
- **Text** — render labels with the built-in pixel font:
  `python scripts/text_pix.py --text "SCORE 100" --png --color "#fff"
  --scale 4 --out score.png` (or a `.pix` grid by default).
- **Finished screen** — place layers (images, sprites, text) at coordinates:
  `python scripts/compose_scene.py scene.json --out screen.png` (template:
  `templates/scene.json.tmpl`). A layer can set `"anchor": "pivot"` to land at
  its registration point (e.g. feet) so placement stays consistent across
  different-sized assets.

See `references/composition.md`. **Gate:** the parts pass `check_sprite.py`
before assembly; the composite is reviewed against the design (vision QA).

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
- `references/composition.md` — assembling parts into finished screens:
  tilemaps, scene composition, 9-slice UI frames, and pixel text.
- `references/shading.md` — quality: shading flat silhouettes into forms,
  ramps, resolution, and reaching reference-level via derive-trace.

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
| `scripts/shade_form.py` | Shade a flat region into a 3D form (sphere/cylinder/bevel) with light, rim, AO, dither (stdlib). |
| `scripts/transform_pix.py` | Flip, rotate, or recolor a `.pix` (palette variants, opposite facings) (stdlib). |
| `scripts/lint_pix.py` | Flag pixel-art craft issues — orphan pixels, holes, broken outlines (stdlib). |
| `scripts/detail_score.py` | Score an asset's detail/finish 0–100 with sub-metrics and fix suggestions; set-consistency summary (stdlib). |
| `scripts/gallery.py` | Build a self-contained HTML review gallery of a set: thumbnails + detail scores + consistency summary (Pillow). |
| `scripts/detail_calibrator.py` | Build the interactive detail-calibrator HTML (sliders → target-detail prompt; pre-built at `assets/calibrator.html`) (Pillow). |
| `scripts/consistency_report.py` | Score a SET's uniformity 0–100 (detail spread, outline, palette overlap) and flag outliers (stdlib). |
| `scripts/regen_prompt.py` | Turn a detail score + target into concrete next steps and an LLM regeneration brief (stdlib). |
| `scripts/ref_similarity.py` | Score how close an asset is to a reference (silhouette IoU, color, luminance) (Pillow). |
| `scripts/autofix.py` | Safely clean a `.pix` (remove orphans, fill holes) and re-score (stdlib). |
| `scripts/variants.py` | Reskin one `.pix` into material/palette variants (enemy color-swaps) (stdlib). |
| `scripts/anim_score.py` | Score animation smoothness 0–100 and flag jumpy frame transitions (Pillow). |
| `scripts/proportions.py` | Measure/check an asset against the spec `frame` (size, centering, baseline, symmetry); `--fit` recenters + baseline-aligns (stdlib). |
| `scripts/frame_guide.py` | Render the spec `frame` as a guide overlay (margin, baseline, axis, pivot) to author against (Pillow). |
| `scripts/palette_tool.py` | Generate color ramps (`--hue-shift` for cool shadows/warm highlights) or import `.hex`/`.gpl` (Lospec) palettes into a spec (stdlib). |
| `scripts/export_engine.py` | Export a sprite sheet to Aseprite JSON or a CSS `steps()` HTML page (stdlib). |
| `scripts/batch.py` | Run check/lint/render/recolor across many `.pix` via a glob (stdlib; Pillow for render). |
| `scripts/tilemap.py` | Assemble tile `.pix` files into one map PNG from a `.tmap.json` grid (Pillow). |
| `scripts/compose_scene.py` | Layer images/sprites/text at coordinates into a finished screen (Pillow). |
| `scripts/nine_slice.py` | Scale a UI frame to any size with 9-slice (corners intact) (Pillow). |
| `scripts/text_pix.py` | Render UI text with a built-in 3x5 pixel font to a `.pix` or PNG (stdlib; Pillow for PNG). |

Run any script with `--help` for the full argument list.

## Templates

| Template | Purpose |
|----------|---------|
| `templates/pixy.spec.json.tmpl` | Starter project spec with a balanced 16-color palette. |
| `templates/sprite.pix.tmpl` | Starter character-grid sprite. |
| `templates/walk.anim.json.tmpl` | Starter animation manifest (frames + fps + loop). |
| `templates/tilemap.json.tmpl` | Starter tilemap (tile char → file + grid). |
| `templates/scene.json.tmpl` | Starter scene manifest (layered finished screen). |

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
