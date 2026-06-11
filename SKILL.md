---
name: pixy-the-pixel-art
description: Use when the user wants to create, animate, or assemble pixel-art for games — sprites, tiles, icons, animations, maps, and UI screens — with the same fidelity on any LLM. Triggers on "픽셀아트 만들어줘", "pixy로 에셋 만들어", "generate a pixel sprite", "make a pixel asset", "애니메이션 만들어", "sprite sheet", "맵/타일맵 만들어", "build a HUD", "pixel art from this image", "아이콘 세트". Runs an END-TO-END gated pipeline: locks a per-project spec (size, scale, palette, transparency/누끼), generates or conforms art into it, gates every asset (craft score + lint + vision QA), self-corrects until it ships, and assembles animations/sheets/maps. Produces .png/.gif, pixy.spec.json, .pix, sheets and scene/tilemap JSON. Use whenever a request involves pixel art, animation, tilemaps, game UI, or game assets.
version: 0.32.1
compatibility:
  - python>=3.9
  - pillow>=9.0
---

# Pixy The Pixel Art

## What this skill is

A pixel-art **factory you must drive end to end** — not a toolbox to pick
from. The model (you, or an image model) supplies only the picture; locked
specs and deterministic gates supply size, palette, cut-out (누끼), craft,
and consistency. Your job is to run the pipeline below to a **SHIP verdict
before the user ever sees a result**. Quality complaints about this skill
have one root cause: an agent skipping the pipeline and improvising.

## Two tracks (both need ZERO user skills)

- **Track 1 — pure LLM + image model** (default): precise grid-locked
  generation. Single assets (P1), identity-locked sets and 8-way directions
  by words (P2/P3), animation (P4). Needs only an image model.
- **Track 2 — Blender via MCP** (when a blender-mcp server is connected):
  the AGENT drives Blender - builds a primitive blockout from the user's
  words (`blender_snippet --mode blockout`), renders directions x frames,
  then `frames_to_pixel` conforms. Exact geometric consistency across
  angles/frames; the user never opens Blender. See
  `references/blender-mcp-track.md`. (P7 also accepts renders from users who
  have their own 3D pipeline.)

Pick Track 2 for 4/8-way movement sets when the MCP is available; Track 1
for hero art, icons, and style sets - or when there is no Blender at all.

## Iron rules (every one of these is a learned field failure)

1. **Never deliver a raw model image as the result.** Every asset goes
   through conform (`imageify`/`pixyfly`) and the gates first. The raw
   image is an intermediate, not a deliverable.
2. **Never generate a set as one grid image.** One image per asset, always —
   a grid kills per-asset 누끼, conform, and gating, and the model reinvents
   shared structure per cell.
3. **Never hand-write an image-model prompt.** Prompts come from
   `generate_pixel.py` / `charset.py` — they embed the spec's palette,
   size, light, style contract, and anti-artifact guardrails. Ad-hoc
   prompts are how eyes turn alien and hanging wires appear.
4. **Never start without a locked spec.** If a reference image exists,
   derive from it (`analyze_sample` — a generic palette makes a specific
   character soulless); otherwise use a preset. Spec first, art second.
5. **Always gate, then self-correct to SHIP** (the Loop, below) before
   presenting. Present the evidence line (craft N/100, lint, verdict) with
   the result, phrased in the user's language.
6. **Sets stay identity-locked**: poses of one character → `charset
   --poses` (identity chaining); different subjects in one style →
   `charset --subjects --template` (the shared scene written as an
   identical-by-contract block). Never "same style please" + a reference.
7. **Match the look to the flags**: clean/cute/cel → NO dither + `--denoise
   med` + `--outline spec --outline-mode selout`; rich/painterly → `--dither`
   (ordered) + `--denoise none`; tiles → `--tileable`.

## The Loop (gate → fix → retry; run it inside every pipeline)

    conform/generate the asset
    craft_score asset.pix --spec spec.json     # discipline 0-100 + fixes
    lint_pix asset.pix --spec spec.json        # craft defects
    if vision-capable: open the render, walk references/vision-qa.md
    -> SHIP (craft >= 80, no lint, QA pass): deliver with evidence
       (lint exits 0 on findings unless --strict - read the count, not
       the exit code; pixyfly auto-repairs mechanical findings first)
    -> else: apply the FIRST suggested fix (autofix --smooth, re-conform
       with --denoise high, --outline-mode selout, ...) OR regenerate with
       `craft_score --brief` appended to the prompt. Max 2 retries, then
       deliver best attempt WITH the failure evidence and what you'd change.

## Intake (before any pipeline)

Print this block first — it is the user's checkpoint, not optional:

    Brief: <one line restating the ask>
    Assumptions: subject=…, size/canvas=…, palette=…, style/mood=…,
                 detail≈…/100, animation=yes/no
    Reference: <file, or "none">
    → Tell me to change any of these; otherwise I proceed.

**Pick a track up front.** Run `python scripts/pixy_doctor.py` (or `--json`):
it reports which tracks are ready and the exact install command for what's
missing. Default to Track 1. Offer Track 2 only when 4/8-way movement is
wanted AND Blender is present (or the user agrees to install it - doctor
prints the platform command; with consent the agent may run it). A blender-mcp
server lets the agent drive an already-open Blender, but is NOT required:
headless `blender --background --python` works once Blender is on PATH.

If interactive and genuinely ambiguous, ask up to 3 questions. If the user
gave a *concept* but no detail/resolution target, point them at the
calibrator (`assets/calibrator.html`, regenerate via
`scripts/detail_calibrator.py`) — its sliders emit the exact `init_spec`
and `imageify` commands. In autonomous runs, proceed on stated assumptions.

## Dispatch: request → pipeline

| Request looks like | Pipeline |
|---|---|
| one sprite/icon/emblem, "퀄리티 높게", a reference image | P1 single asset |
| poses/views/8-way directions of ONE character, walk/run frames | P2 character set (no tools needed) |
| "아이콘 세트", DIFFERENT subjects in one style | P3 style set |
| "애니메이션", idle/hover/blink/hit, GIF/sheet | P4 animation |
| no image model available, simple sprite/tile/icon | P5 hand-authored |
| "맵/타일맵", HUD, title screen, 화면 구성 | P6 maps & screens |
| blender-mcp connected, OR user has a 3D model/render sequence | P7 3D track (agent-driven via MCP - no user skills; or user renders) |
| "이 스프라이트 수정" | edit the `.pix` rows, rerun the Loop |

## P1 — Single asset (image-first; the default for quality)

1. **Spec.** Reference image? →
   `analyze_sample ref.png --colors 15 --canvas 64x64 --background
   transparent --hue-shift --out char.spec.json` (canvas per the brief:
   16-48 icon, 64 GBA-grade sprite, 96-128 fine detail; see
   `references/spec-schema.md` presets, `init_spec --preset` when no
   reference). Show the palette; lock.
2. **Raster.** In order of preference:
   - Host has an image tool: `generate_pixel "<subject>" --spec ... --out
     x.pix --prompt-only`, generate from the printed prompt with your own
     tool, save the PNG.
   - Keys/local model: `--provider hf|openai|command` does generate+conform
     in one step.
3. **Conform + gate + animate in one command.** DEFAULT: let pixyfly
   DERIVE the palette from the generated raster itself (omit --spec) -
   `pixyfly raw.png --name hero --out-dir out/ --colors 15 --canvas 64x64
   --hue-shift --denoise med --outline spec --outline-mode selout
   [--fx hover --gif]`. Conforming into a generic preset legend silently
   destroys the subject's stated colors (a "purple cat" turns blue-grey:
   the preset has one purple). Reuse `--spec` only when the asset must join
   an existing project palette - and then verify the subject's colors exist
   in that legend first. Style flags per Iron Rule 7.
4. **Run the Loop** until SHIP. Deliver the PNG/GIF + evidence line.

## P2 — Character set (same character, poses/frames)

    charset.py --spec char.spec.json --character "<one fixed description>" \
        --poses front,back,left,walk_0,walk_1,walk_2,walk_3 --out-dir set/
    # generate ONE image per printed prompt (first image = img2img --ref
    # for the rest), save as <pose>.png, then:
    charset.py ... --images-dir raw/ --strict --min-uniformity 70 \
        --animate walk --fps 8 --export aseprite

charset embeds the identity clause + frame numbering in every prompt,
conforms all poses with the one spec, gates palette-overlap/uniformity and
per-pose craft, and finishes walk_* into GIF + sheet + engine export. An
outlier pose → regenerate just that pose with the first pose as `--ref`.

**8-way directional sets need NO 3D tools** — pass `--poses s,se,e,ne,n,nw,w,sw`
(or combos `s_0,s_1,...` for directions x walk frames; each frame gets a
distinct stride phrase). charset turns each into a top-down facing prompt;
the image model draws the angles, identity stays locked. **Canonical path
for a directional SHEET:** prompts via charset (prompt-only), generate, then
run `frames_to_pixel raw/ --directions ... --frames N --name hero --register
--export godot|aseprite --strict --min-craft 75` ONCE - it conforms, gates,
registers, sheets, and exports in a single pass (don't conform twice via
--images-dir AND frames_to_pixel). Use charset --images-dir for non-grid
pose sets and `--animate walk` prefix cycles. (A real 3D rig — P7 — is more
geometrically exact but only worth it if the user already has one.)

## P3 — Style set (different subjects, one template)

    charset.py --spec ref.spec.json \
        --subjects "a sprouting plant;a pink heart;an open book" \
        --template "<the shared scene, EXHAUSTIVE: container geometry &
                    line weight, glow (ramped, 3 tones), floor, sparkles,
                    background>" \
        --out-dir set/
    # one image per prompt -> --images-dir raw/ --strict to conform + gate

The template is injected verbatim into every prompt as IDENTICAL-by-
contract, with guardrails (one subject, not a grid, nothing dangling,
reference shading depth). `;` separates comma-bearing subjects. This is
the only sanctioned way to make icon packs.

## P4 — Animation

Frames come from one of three sources, then one assembly+gate path:

1. `animate_fx base.pix --fx bob|hover|breathe|sway|shake|blink|flash
   --frames N --amp A --gif out.gif` — deterministic classic cycles from
   ONE sprite (idle/hit/UI need no redrawing; blink needs `--eye-char`).
2. Hand-authored `.pix` per frame (real limb animation) against
   `frame_guide.py`'s overlay; `proportions --fit` keeps feet grounded.
3. Image-first frames: P2 with `--poses walk_0..` `--animate walk`.

Assemble: `animate --frames ... --out walk --format all --fps 8`
(`--pingpong`, per-frame `ms` for easing, `--register` to pin the pivot;
**use `--scale 1` when the sheet is for an editor/engine import** - editors
want native pixels, not the export upscale). Gate: `anim_score walk_*.pix
--spec ... --loop` — fix flagged jumps with an in-between and a popping
LOOP SEAM with a settle frame or pingpong; high per-frame deltas are NORMAL
for spin/flash (40%+), so judge jumps relative to the cycle, and run
`consistency_report` over mixed-source frames to catch a stylistic
odd-one-out. Engine hand-off: `export_engine <out>_sheet.json --engine
aseprite|godot|css`. Recipes: `references/animation.md`.

## P5 — Hand-authored (offline / simple assets)

Block silhouette → shade → outline → Loop:
`draw_pix --circle/--rect/--mirror` → `shade_form --region X --material
gold --form sphere --rim --ao` (light/outline locked by the spec; **thin
regions: pass `--outline ''`** or the outline consumes them - shade_form
warns; **small icons: prefer `--form bevel`** - sphere/cyl gradients read
as speckle at 16-24px) → **`autofix --smooth --selout`** (THE P5 repair:
clears jaggies, isolated-outline findings, and converts to a selective
outline; `--outline K` dilates outward without eating shaded edges) → the
Loop. Ceiling: simple stylized sprites — escalate to P1 when the brief
wants more.

## P6 — Maps & screens

Tiles: conform with `--tileable`, verify `lint_pix --tileable`. Terrain
from a mask: `autotile mask.txt --material green`. Map: `tilemap
level.tmap.json`. UI frame: `nine_slice`. Text: `text_pix`. Final screen:
`compose_scene scene.json` (layers, `"anchor": "pivot"`). Parts must pass
the Loop BEFORE assembly; vision-QA the composite.
See `references/composition.md`.

## P7 — 3D track (Track 2: agent-driven Blender, or user renders)

Two entry points, NEITHER requires the user to know 3D:

**7a — Blender MCP connected (the no-skills 3D path).** The agent does it:
emit a script with `blender_snippet.py --mode blockout --parts "sphere,body,
0 0 0.55,0.55,#2b52c0;..."` (translate the user's character into 3-8 flat-
colored primitives from the spec palette), run it via the MCP's
`execute_blender_code`, wait for `PIXY_RENDER_DONE`, then conform the PNGs
(step below). Full procedure + motion keyframes + honest limits:
`references/blender-mcp-track.md`. No MCP but Blender installed? The same
script is copy-paste into the Scripting tab. Without Blender entirely ->
Track 1 (P2). **Never tell a non-3D user to learn Blender.**

**7b — the user already has a 3D pipeline** (Dead Cells-style). Their tool
renders `raw/<direction>_<frame>.png` (transparent bg, orthographic, flat
shading near the palette; headless recipe in
`references/three-d-to-pixel.md`). Either way, Pixy is not a 3D engine - a
rendered frame is just another raster source. (blender_snippet assumes the
subject sits at the world origin and fits ~3m; tune `--ortho-scale`/`--cam-*`
otherwise.) Conform it:

    python scripts/analyze_sample.py one_render.png --colors 15 --canvas 64x64 \
        --background transparent --hue-shift --out hero.spec.json
    python scripts/frames_to_pixel.py raw/ --spec hero.spec.json --out-dir out/ \
        --directions s,se,e,ne,n,nw,w,sw --frames 6 \
        --denoise med --outline spec --outline-mode selout \
        --per-direction-gifs --export aseprite --strict --min-craft 75

This conforms every frame into ONE spec, assembles a directions x frames
sheet (+ JSON), per-direction GIFs, and an engine export, and gates set
uniformity + per-frame craft. `--directions s` alone = a plain motion cycle.
The Blender headless render recipe and "when NOT to use this" are in
`references/three-d-to-pixel.md`.

## Asset library (find things as the project grows)

`python scripts/pixy_index.py PROJECT_DIR --out pixy-library.html --json
pixy-catalog.json` scans every `.pix`, resolves its spec, and builds a
searchable HTML library + JSON catalog: thumbnail, set, canvas, colors, craft
score, and a `drift` badge per asset, filterable by name / set / min craft.
Run it after a batch so the user can browse, and re-Loop anything flagged
low-craft or drifted.

## Project consistency (sets that stay sets)

One spec per project — never change it mid-project. `style_lock` stamps
assets and `--check` flags drift; `verify --glob "**/*.pix" --strict
--min-craft 75 --min-uniformity 70` is the one-command project gate;
`consistency_report` ranks outliers (note: `--min-uniformity` is for
same-character/material sets - a multi-material icon set fails palette
overlap BY DESIGN, gate it on craft only); `variants`/`transform_pix` make
recolors without redrawing. Three locks do the rest: legend (palette),
canvas, `transparent_char` → alpha 0 (누끼) — the renderer refuses
violations, byte-identical output for identical input.

## Tool index (one line each; `--help` for details)

| Tool | Job |
|---|---|
| `pixyfly` | image → spec → conform → render → gate verdict → fx GIF, one command |
| `frames_to_pixel` | a rendered 3D frame sequence → conform all → directions×frames sheet + per-direction GIFs + engine export + gates |
| `blender_snippet` | emit ready-to-run Blender Python (MCP `execute_blender_code` / paste / headless): pixel-art camera+light rig, words→primitive blockout, directions×frames render loop |
| `pixy_doctor` | environment check: which track is ready + the exact platform install command for what's missing |
| `pixy_index` | scan a project → searchable HTML asset library + JSON catalog (thumbnails, sets, craft, drift) |
| `charset` | sets: `--poses` (character) / `--subjects --template` (style); conform+gates; `--animate --export` |
| `generate_pixel` | spec-tuned prompt → provider (prompt-only/hf/openai/command/file) → conform |
| `analyze_sample` | reference → character-true spec (palette, ramps, `--hue-shift`, `--include`, `--canvas`) |
| `init_spec` | preset specs (generic, engines, consoles: gameboy/nes/gba-battle/gba-overworld/pico8) |
| `imageify` | conform raster → `.pix`: denoise/guard, feature re-injection, dither modes, sel-out outline, `--tileable` |
| `craft_score` | retro-craft 0-100 + fix commands + `--brief` regeneration brief |
| `lint_pix` | orphans, holes, outline gaps, jaggies, banding, wrong-side light |
| `autofix` | orphans/holes, `--smooth` jaggies, `--outline` |
| `check_sprite` / `render_sprite` | hard validity gate / deterministic PNG |
| `animate` / `animate_fx` / `anim_score` | assemble GIF/APNG/sheet / fx cycles (incl. spin) / smoothness+seam gate |
| `detail_score` / `consistency_report` / `verify` / `style_lock` | finish signals / set uniformity / project gate / drift |
| `draw_pix` / `shade_form` / `proportions` / `frame_guide` | block shapes / light-model shading / frame fit / overlay |
| `transform_pix` / `variants` / `palette_tool` | flip/rotate/recolor / material reskins / ramps & palette import |
| `tilemap` / `autotile` / `compose_scene` / `nine_slice` / `text_pix` | maps, terrain, screens, UI frames, pixel text |
| `export_engine` / `batch` / `gallery` / `regen_prompt` / `ref_similarity` / `trace_image` / `detail_calibrator` | sheet exports (aseprite/godot .tres/css) / glob ops / review page / regen steps / reference match / import art / calibrator |

## References (read when the pipeline touches the topic)

- `references/image-generation.md` — image-first details: providers,
  denoise/dither/feature-preservation, style sets, headless self-QA.
- `references/vision-qa.md` — the seeing judge's checklist (use in the Loop).
- `references/animation.md` — frame sources, fx table, frames/fps recipes.
- `references/three-d-to-pixel.md` — model in 3D, ship in 2D: the bridge, the Blender headless render recipe, when to use it.
- `references/blender-mcp-track.md` — Track 2: the agent drives Blender through MCP (blockout from words, render, conform); track comparison table.
- `references/spec-schema.md` — spec fields + preset table.
- `references/shading.md` — ramps, forms, resolution ladder.
- `references/palette-design.md` — ramps, hue-shift discipline.
- `references/quality-lint.md` — lint findings and what they mean.
- `references/consistency-rules.md` — the three locks, cross-agent rationale.
- `references/composition.md` — tilemaps, scenes, 9-slice, text.
- `references/engine-targets.md` — per-engine/console settings.
- `references/editing.md` / `references/authoring-format.md` /
  `references/style-from-sample.md` — editing, `.pix` format, deriving style.

## Principles

- **Lock, don't trust.** Specs and gates enforce regularity; models only
  supply shapes.
- **The pipeline IS the product.** Skipping it is how every documented
  failure happened.
- **Fail loud, ship quiet.** Gates exit non-zero with concrete messages;
  deliver only SHIP, with evidence.
- **The `.pix` is the source.** Edit grids, never rendered PNGs.
