# Changelog

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

