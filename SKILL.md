---
name: pixy-the-pixel-art
description: Use when the user wants to create, animate, or assemble pixel-art for games — sprites, tiles, icons, animations, maps, and UI screens — with the same fidelity on any LLM. Triggers on "픽셀아트 만들어줘", "pixy로 에셋 만들어", "generate a pixel sprite", "make a pixel asset", "애니메이션 만들어", "sprite sheet", "맵/타일맵 만들어", "build a HUD", "pixel art from this image", "아이콘 세트". Runs an END-TO-END gated pipeline: locks a per-project spec (size, scale, palette, transparency/누끼), generates or conforms art into it, gates every asset (craft score + lint + vision QA), self-corrects until it ships, and assembles animations/sheets/maps. Produces .png/.gif, pixy.spec.json, .pix, sheets and scene/tilemap JSON. Use whenever a request involves pixel art, animation, tilemaps, game UI, or game assets.
version: 0.29.0
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
   the result.
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

If interactive and genuinely ambiguous, ask up to 3 questions. If the user
gave a *concept* but no detail/resolution target, point them at the
calibrator (`assets/calibrator.html`, regenerate via
`scripts/detail_calibrator.py`) — its sliders emit the exact `init_spec`
and `imageify` commands. In autonomous runs, proceed on stated assumptions.

## Dispatch: request → pipeline

| Request looks like | Pipeline |
|---|---|
| one sprite/icon/emblem, "퀄리티 높게", a reference image | P1 single asset |
| poses/views of ONE character, walk/run frames | P2 character set |
| "아이콘 세트", DIFFERENT subjects in one style | P3 style set |
| "애니메이션", idle/hover/blink/hit, GIF/sheet | P4 animation |
| no image model available, simple sprite/tile/icon | P5 hand-authored |
| "맵/타일맵", HUD, title screen, 화면 구성 | P6 maps & screens |
| "3D로 만들어 픽셀로", a rendered 3D frame sequence, 8-way/turntable | P7 3D-to-pixel |
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
3. **Conform + gate + animate in one command:**
   `pixyfly raw.png --spec char.spec.json --name hero --out-dir out/
   --denoise med --outline spec --outline-mode selout [--fx hover --gif]`
   (style flags per Iron Rule 7).
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
(`--pingpong`, per-frame `ms` in a manifest for easing, `--register` to
pin the pivot). Gate: `anim_score walk_*.pix --spec ... --loop` — fix
flagged jumps with an in-between and a popping LOOP SEAM with a settle
frame or pingpong. Recipes (frames/fps per motion):
`references/animation.md`.

## P5 — Hand-authored (offline / simple assets)

Block silhouette → shade → outline → Loop:
`draw_pix --circle/--rect/--mirror` → `shade_form --region X --material
gold --form sphere --rim --ao` (light/outline locked by the spec) →
`autofix --smooth --outline K` → the Loop. Ceiling: simple stylized
sprites — escalate to P1 when the brief wants more.

## P6 — Maps & screens

Tiles: conform with `--tileable`, verify `lint_pix --tileable`. Terrain
from a mask: `autotile mask.txt --material green`. Map: `tilemap
level.tmap.json`. UI frame: `nine_slice`. Text: `text_pix`. Final screen:
`compose_scene scene.json` (layers, `"anchor": "pivot"`). Parts must pass
the Loop BEFORE assembly; vision-QA the composite.
See `references/composition.md`.

## P7 — 3D-to-pixel (model once, ship many frames)

Modern pipelines (Dead Cells-style) model+animate in 3D and render to 2D.
**Pixy is not a 3D engine** - the model/rig/motion/render live in Blender,
Godot, Maya, etc. A rendered frame is just another raster source. The 3D tool
writes a frame sequence `raw/<direction>_<frame>.png` (transparent bg,
orthographic, flat shading near the target palette); Pixy conforms it:

    python scripts/analyze_sample.py one_render.png --colors 15 --canvas 64x64 \
        --background transparent --hue-shift --out hero.spec.json
    python scripts/frames_to_pixel.py raw/ --spec hero.spec.json --out-dir out/ \
        --directions s,se,e,ne,n,nw,w,sw --frames 6 \
        --denoise med --outline spec --outline-mode selout \
        --per-direction-gifs --export aseprite --strict

This conforms every frame into ONE spec, assembles a directions x frames
sheet (+ JSON), per-direction GIFs, and an engine export, and gates set
uniformity + per-frame craft. `--directions s` alone = a plain motion cycle.
The Blender headless render recipe and "when NOT to use this" are in
`references/three-d-to-pixel.md`.

## Project consistency (sets that stay sets)

One spec per project — never change it mid-project. `style_lock` stamps
assets and `--check` flags drift; `verify --glob "**/*.pix" --strict
--min-craft 75 --min-uniformity 70` is the one-command project gate;
`consistency_report` ranks outliers; `variants`/`transform_pix` make
recolors without redrawing. Three locks do the rest: legend (palette),
canvas, `transparent_char` → alpha 0 (누끼) — the renderer refuses
violations, byte-identical output for identical input.

## Tool index (one line each; `--help` for details)

| Tool | Job |
|---|---|
| `pixyfly` | image → spec → conform → render → gate verdict → fx GIF, one command |
| `frames_to_pixel` | a rendered 3D frame sequence → conform all → directions×frames sheet + per-direction GIFs + engine export + gates |
| `charset` | sets: `--poses` (character) / `--subjects --template` (style); conform+gates; `--animate --export` |
| `generate_pixel` | spec-tuned prompt → provider (prompt-only/hf/openai/command/file) → conform |
| `analyze_sample` | reference → character-true spec (palette, ramps, `--hue-shift`, `--include`, `--canvas`) |
| `init_spec` | preset specs (generic, engines, consoles: gameboy/nes/gba-battle/gba-overworld/pico8) |
| `imageify` | conform raster → `.pix`: denoise/guard, feature re-injection, dither modes, sel-out outline, `--tileable` |
| `craft_score` | retro-craft 0-100 + fix commands + `--brief` regeneration brief |
| `lint_pix` | orphans, holes, outline gaps, jaggies, banding, wrong-side light |
| `autofix` | orphans/holes, `--smooth` jaggies, `--outline` |
| `check_sprite` / `render_sprite` | hard validity gate / deterministic PNG |
| `animate` / `animate_fx` / `anim_score` | assemble GIF/APNG/sheet / fx cycles / smoothness+seam gate |
| `detail_score` / `consistency_report` / `verify` / `style_lock` | finish signals / set uniformity / project gate / drift |
| `draw_pix` / `shade_form` / `proportions` / `frame_guide` | block shapes / light-model shading / frame fit / overlay |
| `transform_pix` / `variants` / `palette_tool` | flip/rotate/recolor / material reskins / ramps & palette import |
| `tilemap` / `autotile` / `compose_scene` / `nine_slice` / `text_pix` | maps, terrain, screens, UI frames, pixel text |
| `export_engine` / `batch` / `gallery` / `regen_prompt` / `ref_similarity` / `trace_image` / `detail_calibrator` | sheet exports / glob ops / review page / regen steps / reference match / import art / calibrator |

## References (read when the pipeline touches the topic)

- `references/image-generation.md` — image-first details: providers,
  denoise/dither/feature-preservation, style sets, headless self-QA.
- `references/vision-qa.md` — the seeing judge's checklist (use in the Loop).
- `references/animation.md` — frame sources, fx table, frames/fps recipes.
- `references/three-d-to-pixel.md` — model in 3D, ship in 2D: the bridge, the Blender headless render recipe, when to use it.
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
