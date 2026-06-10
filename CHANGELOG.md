# Changelog

## 0.24.1 - 2026-06-10

- Post-merge factory dogfood on main (spec -> conform -> craft self-QA -> 4bpp gate -> animate_fx -> render, all green) surfaced one robustness nit, now fixed: `analyze_sample` used the deprecated `Image.getdata()` (removed in Pillow 14); switched to `'P'`-mode `tobytes()`. Verified clean under `-W error::DeprecationWarning`, and the craft_score self-correction loop closes (its `--denoise` advice raises the score). 36 scripts, 125 tests.

## 0.24.0 - 2026-06-10

- Close ALL remaining factory gaps + animation deep-dive:
  - **Gap 1, set/pose consistency — `charset.py`**: consistent character sets (poses / animation frames). One locked spec + one character block per prompt (with pose phrases and frame numbering), identity chaining (first pose's raw image = `{ref_png}` img2img reference for the rest), conform per pose, then gates: palette overlap/uniformity + per-pose craft, `--strict` fails loudly. Works prompt-only, from `--images-dir`, or fully automatic via providers.
  - **Gap 2, real generation — `--provider hf`** (HF serverless Inference API, `HF_TOKEN`, `PIXY_HF_MODEL` default FLUX.1-schnell) and `--ref`/`{ref_png}` img2img substitution in the command provider; graceful errors without keys.
  - **Gap 3, headless self-QA — `craft_score.py`**: retro-craft discipline 0-100 (jaggies, banding, flat purity, edge definition incl. sel-out, light agreement, dither regularity, on-ramp colors), each failure paired with its exact fix command; `--brief` emits a regeneration brief; `verify --min-craft` gates it in CI. Discriminates: clean conform 87, ordered-dither 84, FS-noise 69.
  - **Gap 4, light lint**: `lint_pix` flags an asset whose highlights sit opposite the spec's light direction (bright-vs-dark centroid test; flat assets skipped). shade_form tl-lit scores +1.0, br-lit -1.0 and flags.
  - **Animation — `animate_fx.py`**: classic motion cycles from ONE base sprite (bob, hover, breathe, sway w/ pinned feet, shake, blink via `--eye-char`, damage flash), all frames validated in-spec, `--gif` assembles directly; `anim_score --loop` now flags a popping loop seam; `references/animation.md` gains the three frame-sources, an fx table, and frame-count/fps recipes per motion type.
- 36 scripts, 125 tests.

## 0.23.1 - 2026-06-10

- Audit pass (dogfood the skill's own gates on its own output + edge cases); three correctness fixes:
  - **Background-keying data loss**: a solid / edge-to-edge opaque image was flood-keyed to *nothing* (0% coverage). The key now self-guards - if the flood would erase >=99.5% of the canvas there is no real background, so it keys nothing. Tuned so a small subject in a large margin is still cut out correctly.
  - **Lint false-positive on sel-out outlines** (a regression from the sel-out feature): the "broken outline" check now only fires when the asset uses a mostly-continuous hard outline (edge-outline fraction >=0.6); a selective/sel-out outline is intentionally discontinuous. A genuine stray interior outline dot is still flagged.
  - **Empty/low-coverage conform** now warns (with an actionable `--contain` / solid-background hint) instead of silently writing a blank or near-blank grid.
- 33 scripts, 112 tests.

## 0.23.0 - 2026-06-10

- Close the remaining retro-craft gaps from the authenticity audit:
  - **Jaggies lint + autofix**: `lint_pix` flags 1px contour wobbles (the pixel-perfect-curve rule; flatness required two steps out, so organic spiky edges do not false-positive - verified 0 noise on the flame reference) and `autofix --smooth` repairs them (shave bumps, fill dents, re-clean exposed orphans).
  - **Outline banding lint**: double-thick outline runs along straight silhouette edges are flagged when the spec asks `selective-1px` (corners exempt).
  - **Hue-shift + ramps for derived specs**: `analyze_sample` now groups the derived palette into hue-family ramps and writes a `shading` block (so `shade_form --material` works on derived specs), and `--hue-shift` bends each colorful ramp's shadow end toward cool / highlight end toward warm - the period color discipline.
- 33 scripts, 109 tests.

## 0.22.0 - 2026-06-10

- Retro-authenticity audit ("would a period pixel-art designer recognize this?") and fixes:
  - **Ordered (Bayer 4x4) dithering** is now the default `--dither` pattern in imageify/generate_pixel - the regular checker weave hand-pixelled era art actually used. Floyd-Steinberg remains as `--dither-mode fs` (smoother but irregular/modern). This also aligns the conform path with shade_form's checkerboard.
  - **Sel-out outlines** (`--outline-mode selout`): lit edges keep a darker shade of their own color, only shadow edges take the hard outline char - the retro-designer move the GBA conventions promised but no tool delivered (fixes the uniform "sticker ring" look).
  - **`nes` preset**: curated 28-color NES 2C02 gamut, 16x16, with the hardware rule (3 colors + transparency per sprite, gate via `lint_pix --max-colors 3`).
- 33 scripts, 102 tests.

## 0.21.0 - 2026-06-10

- Round eyes: feature re-injection's minority-bias (snap a cell at >=18% coverage) was correct for thin lines but made BLOB boundaries lumpy - an eye's edge cell flipped whole depending on grid phase ("squashed eyes"). Cells now take their **dominant** side (>=50%), keeping round contours round, and snap to the minority only for a true thin feature (one that dominates no neighbouring cell - a catch-light or 1px wireframe). Verified: round sparkly eyes at 64/96, cube wireframe unbroken.
- `analyze_sample --include "#hex,..."`: force signature colors into the legend within the `--colors` budget (accents too small for the quantizer to allocate). 33 scripts, 98 tests.

## 0.20.0 - 2026-06-10

- Character preservation: simplification was eating the marks that carry a character (sparkly eyes, catch-lights, hearts) - small, rare, high-contrast, exactly what naive cleanup removes first. Fixed with three safeguards, all default-on:
  - **Contrast guard** (`--denoise-guard`, default 150): denoise and the simplify color cap absorb only low-contrast ramp speckle; high-contrast small features survive any denoise level. (Quantization speckle is adjacent-tone; an eye on a face is not.)
  - **Feature re-injection** (`--no-keep-features` to disable): after the BOX downscale, a cell containing a coherent high-contrast minority (>=18% coverage, contrast >=110) snaps to that minority instead of the washed-out mean - pupils stay dark, thin outlines keep weight.
  - **Character-true palette in one command**: `analyze_sample --canvas WxH --scale N --background ...` overrides, so a reference-derived palette + target canvas spec needs no manual JSON editing (generic preset palettes were the #1 "soulless output" cause).
  - Calibrator preview updated to match: guarded denoise + adjacent-tone speckle. Verified on the reference: eyes/heart/smile preserved at 64x64/15col (4bpp gate) and 96x96. 33 scripts, 97 tests.

## 0.19.0 - 2026-06-10

- FireRed-grade factory targets: the goal is a pipeline that mass-produces GBA-Pokemon-level (and beyond) pixel art with the LLM steering intent.
  - `gba-battle` (64×64) and `gba-overworld` (16×32) presets with the hardware 4bpp cap (15 colors + transparency) and FireRed craft conventions (selective outline + sel-out, 2-3 tone ramps, flat planes, NO dithering) written into the spec.
  - `generate_pixel.build_prompt` now embeds the spec's `conventions` as a "Style contract" so the image model is steered to the project's look, not a generic one.
  - `imageify --outline CHAR|spec` finishing pass: conformed assets get the same clean 1px outline rule as hand-authored ones.
  - `--prompt-only` flag added as documented shorthand for `--provider prompt-only` (docs said it; CLI now accepts it). 33 scripts, 92 tests.

## 0.18.7 - 2026-06-10

- Full audit pass; two defects fixed:
  - imageify upscaling was blurry: conforming a source *smaller* than the canvas (e.g. into `poster`/`mural`) used the BOX filter, blending pixel edges before quantization. Resizes now use NEAREST when scaling up (crisp pixels) and the chosen area filter only when scaling down; regression-tested (2-color source -> exactly 2 colors).
  - generate_pixel leaked an empty temp PNG on every `--provider file` run; the temp file is now only created for providers that actually generate (openai/command).
- README quickstart preset list updated to include the icon-hd..mural tiers. 33 scripts, 88 tests.

## 0.18.6 - 2026-06-10

- Calibrator rewritten to render **live on an HTML5 canvas** instead of pre-baking every slider step as an embedded image. The file drops from ~1.9 MB to ~18 KB, all five axes now **combine in one live preview** (you see resolution x colors x detail x cleanup together, plus real animation), and the page is stdlib-only to generate.
  - The render, median-cut quantize, speckle, and denoise (majority + cluster) are ported to JS so the preview mirrors imageify; verified headless under Node.
  - `assets/calibrator.html` regenerated (18 KB). 33 scripts, 87 tests.

## 0.18.5 - 2026-06-10

- Calibrator gains a 5th axis, **Cleanup (denoise)**: a noisy subject is cleaned at each slider step using the real `imageify.denoise_regions`, so you can see exactly how much stray-pixel/blob removal each strength does (and where thin lines start to erode). The chosen value is emitted as the matching `imageify --denoise-area N` command alongside the prompt.
- `assets/calibrator.html` regenerated. 33 scripts, 86 tests.

## 0.18.4 - 2026-06-10

- Stronger denoise: the per-pixel majority filter only removed lone 1px specks, so 2-4px noise clumps survived. Added a per-blob **cluster cleanup** that absorbs a whole connected same-color blob smaller than N px into its surround (line-preserving: a line is a long blob).
  - New `max` level (blob threshold 8) and a `--denoise-area N` override on `imageify.py`/`generate_pixel.py` to push cleanup as far as wanted (try 6-16), documented with the line-erosion tradeoff at high N.
  - Levels now map to blob thresholds: low/med/high/max = 0/2/4/8. 33 scripts, 85 tests.

## 0.18.3 - 2026-06-10

- Clean flat surfaces: the real cause of "not simple / impurities on a flat area" was dithering scatter + quantization speckle, not tone count.
  - `--denoise none|low|med|high` (default `low`) on `imageify.py`/`generate_pixel.py`: a line-preserving 8-neighbour majority filter that snaps stray pixels to the surrounding flat color while keeping 1px lines (cube wireframes, outlines) intact. So a shaded form reads as clean bands, not scattered dots.
  - `--dither` is now clearly off-by-default and documented as scatter for smooth gradients only — never for clean/cute/cel art (it was the main source of the busy look).
  - Docs across SKILL.md / `references/image-generation.md`: clean/cute → no dither + `--denoise`; rich/painterly → `--dither`. 33 scripts, 83 tests.

## 0.18.2 - 2026-06-10

- `--simplify` detail/cuteness dial on `imageify.py` and `generate_pixel.py` (none/low/med/high): image models over-add fine detail that makes cute subjects look fussy, so this chunks the grid (shrink-then-snap), keeps only the N most-used flat colors, drops dither, and median-filters the source. `high` = poster-flat kawaii; `none` = max fidelity.
- Larger canvas options: `poster` (512×512) and `mural` (1024×1024) presets, completing the 256/512/1024 ladder for the image-first path.
- Docs across SKILL.md / `references/image-generation.md` / `shading.md` / `spec-schema.md`: detail is a dial, not a maximum — small canvas or `--simplify` for cute/clean, large canvas + `--dither` for rich. 33 scripts, 80 tests.

## 0.18.1 - 2026-06-10

- More resolution variations for the image-first path, so reference-level detail is reachable instead of being squeezed into too small a canvas (the top cause of "lower quality than my reference"):
  - New high-res presets: `hero` (128×128), `keyart` (192×192), `scene` (256×256) — too dense to hand-author, meant for `generate_pixel.py` → `imageify.py`.
  - Guidance in `references/shading.md` / `spec-schema.md` / SKILL.md to match the canvas to the reference's real native size (~96–128px for fine-featured art) and to conform at 64/96/128 and keep the smallest that holds the detail. 33 scripts, 75 tests.

## 0.18.0 - 2026-06-10

- Image-first generation path for reference-level quality, since an LLM hand-authoring an ASCII grid tops out at flat, simple sprites:
  - `imageify.py`: conform any raster (generated art, photo) into a clean in-spec `.pix` — area-average downscale (gradients survive), **Floyd–Steinberg dithering to the locked palette** (smooth shading with only spec colors), solid-background flood-fill cut-out, orphan cleanup. Deterministic and validated against the spec.
  - `generate_pixel.py`: build a spec-tuned prompt and call an image model (host tool via `--prompt-only`, OpenAI, or any local model via `--provider command`), then conform — the model supplies the picture, the spec still supplies palette/canvas/cut-out.
  - `references/image-generation.md`; SKILL.md "Generate (image-first)" route; `detail_score.py` now states it measures finish *signals*, not artistry. 33 scripts, 71 tests.

## 0.17.2 - 2026-06-10

- Calibrator must be surfaced when a concept lacks a detail/resolution target: checkpoint points to the calibrator instead of silently assuming and starting

## 0.17.1 - 2026-06-10

- Make the intent step robust across agents: ALWAYS print a brief+assumptions block before generating (even autonomous/Codex runs), ask only when the host allows; never generate without surfacing intent

## 0.17.0 - 2026-06-10

- autotile.py: seamless terrain from a fill mask with uniform auto-borders (tilemap edge consistency). 31 scripts, 65 tests.

## 0.16.0 - 2026-06-10

- Style-lock consistency: spec_id fingerprint; style_lock.py (stamp + drift detection); verify.py (one-command full-battery project gate). 30 scripts, 64 tests.

## 0.15.0 - 2026-06-10

- Uniformity at use-time + gates: compose_scene pivot anchoring, animate --register (grounded frames), consistency_report --strict/--min gate, autofix --outline auto-add

## 0.14.0 - 2026-06-10

- Proportion/frame consistency: spec 'frame' block (margin/baseline/center-axis/content-height/pivot/symmetry); proportions.py (measure/check/--fit recenter+baseline); frame_guide.py (guide overlay); consistency_report now scores proportion uniformity. 28 scripts, 55 tests.

## 0.13.0 - 2026-06-10

- B/C/D: consistency_report + regen_prompt (B); ref_similarity + autofix + variants (C); shade_form bevel/cone forms, palette_tool --hue-shift, anim_score (D). 26 scripts, 50 tests.

## 0.12.2 - 2026-06-10

- Fix: calibrator Copy-prompt button (copyOut was undefined); add file://-safe copy via execCommand with clipboard API fallback

## 0.12.1 - 2026-06-10

- Fine-tune calibrator subjects to a finished look: coastlines, clustered forests, single meandering river, globe-space features (coherent spin); slimmer human torso, soft drape folds instead of rake streaks

## 0.12.0 - 2026-06-10

- Calibrator detail axis now adds visible content as it climbs (Earth: continents/ice/rivers/forests/city-lights/atmosphere; Human: hair/eyes/mouth/nose/collar/belt/folds/scarf/brow); max anchored to Sanabi-level

## 0.11.1 - 2026-06-10

- Calibrator human now animates a walk cycle (swinging arms/legs, head bob, blink, mouth) instead of just bobbing, so frame-count differences read as real motion

## 0.11.0 - 2026-06-10

- Add detail_calibrator.py + pre-built assets/calibrator.html: interactive pre-generation detail picker (resolution/colors/detail/frames sliders, live Earth/Human examples, prompt composer)

## 0.10.0 - 2026-06-10

- Add gallery.py: HTML review gallery of an asset set with detail scores and a consistency summary

## 0.9.0 - 2026-06-10

- Add detail_score.py: 0-100 detail/finish scorecard with sub-metrics, fix suggestions, and set-consistency summary; reported in the Create-asset workflow

## 0.8.0 - 2026-06-10

- Add intent/direction understanding step before generation (interactive clarify or stated assumptions; show-and-iterate feedback loop)

## 0.7.0 - 2026-06-10

- Shading polish (tight specular, solid outline) + locked shading style (spec shading block + shade_form --material) for uniform output

## 0.6.0 - 2026-06-10

- Quality engine: shade_form.py turns flat silhouettes into shaded 3D forms (sphere/cylinder/bevel + directional light, rim, AO, dither); trace_image --derive reproduces a detailed/HD reference in one command (image-matched palette + spec); hi-res presets (icon-hd/portrait/emblem); shading reference; block-then-shade workflow. 35 tests.

## 0.5.0 - 2026-06-09

- Add composition layer: tilemap.py (tiles->map), compose_scene.py (layered finished screens), nine_slice.py (scalable UI frames), text_pix.py (built-in 3x5 pixel font). Templates (tilemap/scene), composition reference, +5 integration checks (now 31). Pixy now covers parts -> assembly -> finished screen -> UI/UX.

## 0.4.0 - 2026-06-09

- Add tileset seamless lint (--tileable) and per-sprite color cap (--max-colors), flood-fill in draw_pix, native-size detection in trace_image, batch.py (check/lint/render/recolor over a glob), golden-fidelity render regression test, README, and CI workflow

## 0.3.0 - 2026-06-09

- Add editing/import tools (trace_image, draw_pix, transform_pix), quality lint (lint_pix), palette tooling (palette_tool: ramps + .hex/.gpl import), engine export (export_engine: aseprite/css), animation depth (pingpong, per-frame timing, onion-skin), and a 20-check integration test suite incl. render determinism proof

## 0.2.0 - 2026-06-09

- Add animation (animate.py: GIF/APNG/sprite-sheet from .pix frames + .anim.json manifest) and universal engine coverage (unity/godot/rpgmaker/gameboy/pico8 presets, per-preset locked palettes, engine-targets + animation references)

## 0.1.1 - 2026-06-09

- Fix: ASCII-only script help/docstrings so --help works on non-UTF-8 consoles (Windows cp949)

## 0.1.0 - 2026-06-09

- Initial release: deterministic spec+renderer pixel-art skill (init_spec/check_sprite/render_sprite/analyze_sample)

