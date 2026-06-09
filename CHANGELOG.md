# Changelog

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

