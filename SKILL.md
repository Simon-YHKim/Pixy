---
name: pixy-the-pixel-art
description: Use when the user wants to create, animate, or assemble pixel-art for games — sprites, tiles, icons, animations, maps, and UI screens — with the same fidelity on any LLM. Triggers on "픽셀아트 만들어줘", "pixy로 에셋 만들어", "generate a pixel sprite", "make a pixel asset", "애니메이션 만들어", "sprite sheet", "맵/타일맵 만들어", "build a HUD", "pixel art from this image". Locks a per-project spec (size, scale, palette, transparency/누끼) so any agent — Claude, Codex, GPT, Gemini — renders identical PNGs from a .pix grid via a deterministic renderer; covers any target via engine/console presets; derives a spec from a reference image; animates frames to GIF/APNG/sheets; and composes tiles, sprites, and pixel text into finished maps and screens. Produces .png/.gif, pixy.spec.json, .pix, and scene/tilemap JSON. Use whenever a request involves pixel art, animation, tilemaps, game UI, or game assets.
version: 0.18.3
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

**Two ways to make the shapes — pick by how much quality you need.** An LLM
hand-authoring an ASCII grid is reliable and offline but tops out at simple,
stylized sprites: spatial detail and painterly shading are genuinely hard to
type pixel by pixel. For reference-level results (rich shading, gradients,
intricate forms), use the **image-first path**: an image model draws the
picture, then Pixy *deterministically conforms it* into the locked spec
(`generate_pixel.py` → `imageify.py`). The model supplies the art; the spec
still supplies the palette, canvas, and cut-out — so quality goes up without
the consistency contract going down. Reach for image-first whenever
hand-authored output looks flat or the user wants high fidelity.

## Workflow

First understand the request (below), then dispatch on it and follow that
path. Always interview the user before creating the first spec — do not
guess the canvas size, palette, or transparency rule.

**No spec yet, or "set up Pixy" / "새 픽셀아트 프로젝트"** → Setup.
**"이 이미지 스타일로" / "pixel art from this image" + a file** → From sample.
**Spec exists, "make/draw an asset" / "에셋 만들어"** → Create asset.
**"퀄리티 높게" / "리얼하게" / "이미지로 생성" / "high quality" / output looks flat** → Generate (image-first).
**"이 스프라이트 수정" / "edit this asset"** → Edit asset.
**"애니메이션 만들어" / "animate" / "sprite sheet"** → Animate.
**"맵/타일맵 만들어" / "HUD" / "화면 구성" / "title screen"** → Compose.

### Understand the request (intent & direction)

Quality and consistency depend on getting the brief right, so do this before
generating anything — not just for the spec.

**ALWAYS, before generating, print this brief-and-assumptions block** (even
in autonomous/headless runs like Codex CLI — this is the user's checkpoint to
intervene, and is not optional):

    Brief: <one line restating what they asked for>
    Assumptions: subject=…, size/canvas=…, palette=…, style/mood=…,
                 detail≈…/100, animation=yes/no
    Reference: <file, or "none">
    → Tell me to change any of these; otherwise I proceed.

Then:

1. **If the host allows interactive input and anything is genuinely
   ambiguous, ask 1–3 concise questions** (subject details, style/mood,
   reference?, target size) in the user's language and wait. If the run is
   autonomous/headless or the user said "알아서 해" / "just do it", do not
   block — proceed on the printed assumptions (the user can still correct
   them next turn).
2. For a **set** of assets, state and lock the shared direction (palette,
   light, outline, resolution) in the spec's `shading`/`frame` blocks first,
   so the whole set is coherent.
3. Produce a **first result, show it, and iterate on feedback** before
   batch-generating the rest. Do not silently mass-produce on the first pass.

Never generate without first emitting the brief-and-assumptions block. A
wrong brief produces consistent but wrong art — surface intent first.

**Detail target — surface the calibrator (do not silently assume).** When the
user gives a *concept* but no explicit detail/resolution/color target, your
checkpoint MUST point them to the calibrator instead of picking numbers for
them and starting. Print its path —
`~/.claude/skills/pixy-the-pixel-art/assets/calibrator.html` (or the repo's
`assets/calibrator.html`; regenerate with `scripts/detail_calibrator.py`) —
and say: open it, slide resolution / colors / detail / frames against the live
Earth/Human examples, and paste the four 0–100 numbers back. Map those numbers
to canvas, palette size, and shading depth. Only assume a detail target (and
say so) if the user declines, already gave numbers, or the run is autonomous.

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
presets) for anything detailed, and the high-res `hero` (128), `keyart` (192),
or `scene` (256) presets for reference-level fidelity — those are too dense to
hand-author and are meant for the image-first path. See `references/shading.md`. For a craft-quality pass, run
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
`scripts/consistency_report.py --strict --min N`, or run the full battery in
one command with `scripts/verify.py --glob "**/*.pix" --spec ... --strict`.
Stamp assets with `scripts/style_lock.py` so `--check` flags any that drift
when the spec is later edited. **Gate:** `check_sprite.py` exits 0 before
rendering — it rejects wrong
dimensions, off-palette characters, and silently missing transparency.

### Generate (image-first — high quality)

Use this when hand-authored grids look flat or the user wants reference-level
fidelity (rich shading, gradients, detailed forms). An image model draws the
picture; Pixy conforms it into the locked spec so it stays in-palette,
in-canvas, and cut-out. **The spec must already exist** (run Setup first) — the
prompt and the conform step both read it.

**Size the canvas to the ambition.** Reference-level art (fine eyes, glow,
intricate forms) is ~96–128px native, not 32–64; conforming it into too small a
canvas is the #1 cause of "the quality looks lower than my reference." Use the
high-res presets for this path — `hero` (128), `keyart` (192), `scene` (256),
`poster` (512), `mural` (1024) — or pass `--canvas`. When unsure, conform the
same raster at 64/96/128 and keep the smallest that still holds the detail.

**Keep flat areas flat — this is the usual "not clean" complaint.** Stray
pixels scattered across a surface that should be one color come from two things:
`--dither` (off by default — it *deliberately* scatters pixels to fake tones;
use it ONLY for smooth painterly gradients, never for clean/cute/cel art), and
quantization speckle (cleaned by `--denoise`, default `low`, a line-preserving
majority filter — raise to `med`/`high` for poster-flat surfaces). Rule of
thumb: clean/cute → no dither + `--denoise med`; rich/painterly → `--dither`.
Separately, `--simplify low|med|high` reduces tones/colors and chunks the grid,
and a small canvas (48-64) upscaled large is itself a cuteness lever.

The flow has two halves: **generate** a raster, then **conform** it.

1. **Compose the prompt from the spec** (bakes in native size, the exact
   palette hexes, light direction, and the cut-out rule):

       python scripts/generate_pixel.py "a wizard frog with a staff" \
           --spec pixy.spec.json --out frog.pix --dither --prompt-only

2. **Get the raster.** Three ways, by what the host can do:
   - **Host has its own image tool** (this agent's image generation, or
     GPT/Gemini image) — generate from the printed prompt, save the PNG, then
     run the conform step (step 3) on it. This is the default, offline-safe
     route and needs no API key.
   - **Direct provider** — `--provider openai` (needs `OPENAI_API_KEY`) calls
     the image API and conforms in one command.
   - **Local model** — `--provider command --cmd '<your-sd-or-comfy> {prompt}
     {out_png}'` runs any local generator, then conforms.
3. **Conform** the raster into the spec (the deterministic, in-spec step):

       python scripts/imageify.py frog.png --spec pixy.spec.json \
           --out frog.pix --dither

   `imageify` area-averages on downscale (gradients survive), Floyd–Steinberg
   **dithers to the LOCKED palette** (so shading reads smoothly with only the
   spec's colors — this is the big quality lever), keys out a solid background
   into the cut-out, and removes orphan noise. Add `--contain` so a non-square
   subject is fitted, not stretched.
4. **Then treat it like any other `.pix`:** `check_sprite.py` → `render_sprite.py`
   → look at it → `detail_score.py` → clean up by hand or with `autofix.py`,
   `lint_pix.py`, `proportions.py --fit`. It animates, recolors, and composes
   exactly like a hand-authored asset, and stays consistent via the same locks.

**Gate:** the conformed `.pix` passes `check_sprite.py`; a vision-capable agent
opens the render and confirms the silhouette, palette, and cut-out. See
`references/image-generation.md` for prompt design, providers, dithering, and
how this preserves the consistency contract. Use image-first for the hero
asset, then derive variants/animation frames from it for a coherent set.

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
  level.png` (template: `templates/tilemap.json.tmpl`). For terrain with
  uniform edges everywhere, draw a fill mask and run
  `python scripts/autotile.py mask.txt --spec tiles.spec.json --material green
  --out terrain.png` (borders auto-form only at boundaries).
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
- `references/image-generation.md` — the image-first path: prompt design,
  providers (host tool / OpenAI / local command), dithering to the locked
  palette, background cut-out, and how it keeps the consistency contract.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/init_spec.py` | Scaffold a `pixy.spec.json` from a use-case preset and flags (stdlib only). |
| `scripts/generate_pixel.py` | Image-first generation: build a spec-tuned prompt, call an image model (host tool / OpenAI / local command), and conform the result into the locked spec (Pillow). |
| `scripts/imageify.py` | Conform any raster (generated art, photo) into a clean in-spec `.pix`: area-average downscale, locked-palette quantize, solid-background cut-out, line-preserving `--denoise` of flat-area speckle, optional `--dither`, and a `--simplify` tone/grid dial (Pillow). |
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
| `scripts/style_lock.py` | Stamp assets with the spec fingerprint and detect style drift when the spec changes (stdlib). |
| `scripts/verify.py` | One-command project gate: runs check/lint/proportions/detail/uniformity/drift over a whole set (stdlib). |
| `scripts/palette_tool.py` | Generate color ramps (`--hue-shift` for cool shadows/warm highlights) or import `.hex`/`.gpl` (Lospec) palettes into a spec (stdlib). |
| `scripts/export_engine.py` | Export a sprite sheet to Aseprite JSON or a CSS `steps()` HTML page (stdlib). |
| `scripts/batch.py` | Run check/lint/render/recolor across many `.pix` via a glob (stdlib; Pillow for render). |
| `scripts/tilemap.py` | Assemble tile `.pix` files into one map PNG from a `.tmap.json` grid (Pillow). |
| `scripts/autotile.py` | Turn a fill mask into a seamless terrain map with uniform auto-formed borders (Pillow). |
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
