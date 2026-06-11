# Changelog

## 0.32.1 - 2026-06-11

- **Iteration 3 of the persona usability program** - two pipelines no persona had walked yet were replayed end to end and PASSED with zero new HIGH frictions: P3 style sets (`charset --subjects` -> conform `--images-dir --strict` -> 100% palette overlap, uniformity 100/100) and P6 maps/screens (`--tileable` conform -> `lint_pix --tileable` clean -> autotile -> text_pix -> compose_scene). A fresh Blender blockout was re-emitted and line-reviewed: all six v0.32 bpy fixes verified present in the emitted code (PNG-before-RGBA, EEVEE try/except, sun parented to pivot, BSDF lookup by type, hide_render on non-Pixy objects, tempfile fallback) plus re-run color update and the PIXY_RENDER_DONE marker.
- **craft <-> lint banding agreement (last open MED)**: craft_score no longer suggests a double-outline repair for 1-2 doubled px that `lint_pix` (which reports at >= 3) would never flag - the two gates now share one bar, so The Loop can't be sent chasing a finding that doesn't exist.
- **blender_snippet `--parts` scale errors are recoverable**: passing `1 1 1` for scale now explains scale is ONE uniform number and shows a working example, instead of a bare `could not convert string to float`.
- **plugin.json version can't drift anymore**: it lagged a release behind SKILL.md (plugin managers key updates off it) - synced and now guarded by a test.
- 41 scripts, 160 tests.

## 0.32.0 - 2026-06-11

- **Six-persona parallel usability program** (complete beginner, pixel designer, indie Godot dev, no-vision CLI power user, Blender expert, blender-mcp user): three agents ran every journey against the real repo and filed 42 frictions; every HIGH and most MED items fixed and replay-verified:
  - **The Loop no longer dead-ends**: pixyfly auto-repairs mechanical lint (jaggies, isolated outline px) before the verdict and prints top lint categories - the flame test case went REVIEW-forever -> 6 auto-fixes -> 0 lint -> SHIP.
  - **P5 finally passes its own gates**: `autofix --selout` (hand-path selective outline) + isolated-outline repair under `--smooth`; the gold-coin case went 20 findings -> 0, craft 80 -> 97. `autofix --outline` now dilates OUTWARD instead of eating shaded edge pixels.
  - **The all-black-sword incident**: shade_form warns when the outline consumes >50% of a region (and documents `--outline ''`); craft_score caps a consumed-outline sprite at 55 with the real cause, instead of scoring a black blob 85.
  - **Suggestions are now path-aware and non-contradictory**: no dither accusation without an actual weave; band/edge fixes name both `autofix --selout` (.pix) and the imageify re-conform.
  - **P1 default conform now derives the palette from the generated raster** (a "purple cat" no longer turns blue-grey inside a preset legend).
  - **animate_fx `--fx spin`** (coins/gems: horizontal squash + mirrored back half) and per-frame walk stride phrasing (contact LEFT / passing / contact RIGHT...) so image models can actually alternate legs.
  - **frames_to_pixel**: `--name`, `--register` passthrough (kills silhouette wobble), directions recorded in the sheet json; **export_engine gains a Godot SpriteFrames `.tres` target** (one animation per direction).
  - **Blender code is now version/locale-proof**: PNG before RGBA (FFmpeg-configured .blends), EEVEE-NEXT try/except (4.2+), Principled lookup by TYPE (translated UIs), sun parented to the pivot (light stays top-left in every view), blockout hides pre-existing meshes/lights (default-cube engulfing), absolute temp out-dir for unsaved .blends; the broken hand-written recipe in three-d-to-pixel.md was replaced by blender_snippet as the single source of truth.
  - Docs: canonical one-pass directional path, `--scale 1` for editor imports, anim_score expectations per motion type, dark-subject-on-black warning, MCP chunking/remote-file guidance, min-uniformity scope note.
- 41 scripts, 157 tests.

## 0.31.0 - 2026-06-11

- Packaged as a **Claude Code plugin** (the skill outgrew "just a skill"): `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (the repo is both the marketplace and the plugin) + slash commands `/pixy-new`, `/pixy-index`, `/pixy-doctor`. Install: `/plugin marketplace add Simon-YHKim/Pixy` then `/plugin install pixy-the-pixel-art@pixy`. (Track 1 needs no MCP; the optional blender-mcp is documented, not hard-bundled, so installs never break.)
- **Environment doctor** (`pixy_doctor.py`): reports which track is ready (Track 1 conform/render + image source; Track 2 = Blender) and prints the exact platform install command for what's missing (brew/apt/snap/flatpak/winget). Track 2 runs Blender HEADLESS - no MCP, no GUI, no 3D skills; blender-mcp is an optional alternative. Wired into the intake so the agent picks a track by interview, not mid-pipeline failure.
- **Asset library / indexing** (`pixy_index.py`): scans a project for every `.pix`, resolves each spec, and builds a searchable HTML library + JSON catalog - thumbnail, set, canvas, colors, craft score, and a spec-`drift` badge per asset, filterable by name / set / min craft. The answer to "too many assets to keep track of".
- 41 scripts, 148 tests.

## 0.30.0 - 2026-06-11

- **Two-track architecture** (user-directed): Track 1 = pure LLM + image model (grid-locked generation, words-based 8-way directions/walks); Track 2 = **Blender driven BY THE AGENT through a blender-mcp server** - the user never opens Blender, gaining exact geometric consistency across angles/frames.
  - `blender_snippet.py`: emits ready-to-run, self-checking Blender Python for the MCP's `execute_blender_code` (or Scripting-tab paste / headless): idempotent pixel-art rig (orthographic cam, transparent film, top-left key light matching the spec), `--mode blockout` builds a primitive character from words (parts list with flat spec-palette colors), `--mode render` for existing scenes, directions x frames sampling loop ending in a `PIXY_RENDER_DONE` marker; output feeds `frames_to_pixel` unchanged.
  - `references/blender-mcp-track.md`: the agent procedure end to end, track comparison table, motion-keyframe recipe, honest limits (blockouts are chunky; composite Track 1 for the face). SKILL.md gains the Two-tracks section, P7 split (7a MCP agent-driven / 7b user renders), dispatch + tool index.
  - Track-1 preflight hardening for the home test: direction x motion combo poses (`s_0` = facing south + walk frame 1 of N) now keep BOTH semantics in the prompt (was losing the facing); frame-total edge guard. Full home workflow (prompts -> images -> charset gates -> frames_to_pixel sheet) simulated end to end: PASS.
- 39 scripts, 145 tests.

## 0.29.1 - 2026-06-10

- Accessibility correction: the v0.29 3D-to-pixel path implicitly told a "can't use Blender" user to go use Blender - betraying the skill's premise (no coding/design/tools required). Fixed without removing the expert lane:
  - **8-way directional sets with NO 3D tools**: `charset --poses s,se,e,ne,n,nw,w,sw` now turns each compass direction into a top-down facing-direction prompt; the image model draws the angles, identity stays locked, Pixy conforms. The benefit people want from 3D (many directions/frames of one character) is now reachable by description alone.
  - Repositioned everywhere: P7 is an OPTIONAL expert lane "only if the user already has a 3D asset", dispatch routes non-3D users to P2, and `references/three-d-to-pixel.md` leads with the no-tools path and an explicit "never tell a non-3D user to just use Blender".
- 38 scripts, 142 tests.

## 0.29.0 - 2026-06-10

- 3D-to-pixel bridge (the "model in 3D, ship in 2D" workflow - Dead Cells-style): `frames_to_pixel.py` ingests a rendered frame sequence (`raw/<direction>_<frame>.png`) from any 3D tool, conforms every frame into ONE locked spec, and assembles the canonical game output - a directions x frames sprite sheet (+ JSON), per-direction GIFs, and an engine export - then gates set uniformity + per-frame craft.
  - Deliberately NOT a 3D engine: the model/rig/motion/render stay in Blender/Godot/Maya (a rendered frame is just another raster source, and 3D renders conform cleaner than generated art - identical palette/scale/alignment frame-to-frame).
  - `references/three-d-to-pixel.md`: the bridge, a copy-paste Blender headless turntable render recipe, conform-friendly render tips (orthographic, flat shading, transparent bg, light matching the spec), and when NOT to use it. SKILL.md P7 pipeline + dispatch row.
- 38 scripts, 141 tests.

## 0.28.1 - 2026-06-10

- README brought fully current with v0.28: the stale pre-image-first "workflow" section replaced with the six enforced pipelines + the Loop/SHIP verdict; Quickstart leads with the pixyfly image-first express lane; repo-layout annotations updated (operating procedure, 13 references, golden corpus). Counts were already current; the narrative was not.

## 0.28.0 - 2026-06-10

- **SKILL.md rewritten from tool catalog to MANDATORY operating procedure** - the root cause of every field failure was an agent improvising around the machinery, because nothing forced the pipeline. The skill's runtime is the agent reading SKILL.md; performance comes from what it enforces, not what it offers.
  - **Iron rules** (each one a documented field failure): never deliver a raw model image; never generate a set as one grid; never hand-write image prompts; never start without a locked spec; always gate then self-correct to SHIP before presenting; sets stay identity-locked; look-to-flags mapping fixed.
  - **The Loop** as a first-class algorithm: conform -> craft_score + lint + vision-QA -> apply the first suggested fix or regenerate with `craft_score --brief` -> max 2 retries -> deliver only with the evidence line.
  - Six explicit pipelines (single asset / character set / style set / animation / hand-authored / maps & screens), each as a numbered checklist ending in the Loop; dispatch table from request phrasing.
  - 455 -> 226 lines: tool encyclopedia compressed to a one-line index; details stay in references/ (progressive disclosure). All tool/reference links validated by test sweep.

## 0.27.0 - 2026-06-10

- Style sets (field-failure driven): a real 6-icon set generated from "reference + prompt" drifted exactly as predicted - the model borrowed the vibe but reinvented the shared cube per cell, flattened the shading, hallucinated a hanging wire through every subject, and the single grid image defeated per-asset conform/gates.
  - `charset --subjects "a;b;c" --template "..."`: style-set mode - DIFFERENT subjects, ONE locked template injected verbatim into every prompt as identical-by-contract, with guardrails (exactly ONE subject per image, not a grid, nothing dangling, match the reference's shading depth). ';' separator for comma-bearing descriptions.
  - Derived specs now carry REAL conventions ("light top-left, hard pixels, derived ramps...") instead of a DRAFT disclaimer that leaked straight into generation prompts; the warning moved to `review_note`.
- 37 scripts, 138 tests.

## 0.26.0 - 2026-06-10

- Everything-else round (all remaining backlog items in one pass):
  - **Walk-cycle finish line**: `charset --animate PREFIX [--fps N] [--export aseprite|css]` - after conforming the poses, assembles PREFIX_0.. into GIF + sprite sheet + engine export in the same call. A pose list now goes raw images -> gated set -> engine-ready cycle in one command.
  - **Seamless tiles**: `imageify --tileable` pulls opposite edges into agreement (guard-aware, so intentional high-contrast edge marks survive); verify with `lint_pix --tileable`.
  - **Quality golden corpus** (`scripts/tests/golden/`): a deterministic shaded-blob conform must match the committed `.pix` exactly - catches silent quality regressions in BOX/feature-reinjection/denoise/quantize tuning, complementing the renderer's byte-determinism golden.
  - **Fuzz/property tests**: seeded random images x specs - conform must always produce a valid grid or a clean error, and the result must render.
  - **Perf**: memoized nearest-color in the ordered-dither path (O(npix x palette) -> ~O(distinct)); 512px conform ~1.2s, guarded by a perf test.
  - **Calibrator -> spec wiring**: the dialed sliders now emit the exact `init_spec --canvas RxR --scale N` command alongside the prompt and the imageify command.
  - **Vision QA rubric** (`references/vision-qa.md`): the seeing judge - a numbered checklist (silhouette -> identity -> ... -> cut-out, plus animation/set checks) that ends in a PASS/FAIL report with the one next command.
- 37 scripts, 135 tests.

## 0.25.0 - 2026-06-10

- `pixyfly.py` - one-command factory assembly line: a generated/reference image -> derive a character-true spec (or `--spec` to reuse) -> conform -> render -> craft+lint gate with a release **verdict** (SHIP / REVIEW+next-action / FAIL on `--strict --min-craft`) -> optional `animate_fx` cycle + GIF. Turns the 4-5 manual steps into one call; verified end to end on the reference (craft 84, 0 lint, SHIP). 37 scripts, 129 tests.

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

