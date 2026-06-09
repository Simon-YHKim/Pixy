# How Pixy Keeps Every Agent Consistent

Different models draw differently. A diffusion model is non-deterministic;
even one model varies run to run. Pixy does not fight this by asking for
"better" drawing — it removes the variables that cause drift, so the only
thing left to the model is the shape.

## The three locks

1. **Palette lock.** The `legend` (char → hex) lives in the spec, shared
   by every `.pix` and every agent. The renderer maps characters to colors
   from this one table and refuses any character not in it. No agent can
   introduce an off-palette shade, so color stays identical across assets.

2. **Canvas lock.** The renderer reads `canvas.width`/`height` from the
   spec and refuses a grid of any other size. Every asset therefore
   exports at the same native dimensions and the same `scale`.

3. **Cut-out (nukki) lock.** `transparent_char` always renders to alpha 0
   when the background is transparent. Backgrounds are reliably removed
   without per-image masking, so no asset ships with a stray fill.

Because rendering is a pure function of (grid, spec), the **same grid
yields a byte-identical PNG** on any machine, for any agent. Consistency
is a property of the pipeline, not of the model.

## Two execution paths

- **Code-only agents** (or any agent without vision): author the grid,
  run `check_sprite.py` (the gate), then `render_sprite.py`. The locks
  guarantee spec-conformant output even though the agent never sees the
  result.

- **Vision-capable agents**: do the same, then open the rendered PNG and
  run the vision-QA loop — compare against `conventions`, edit the grid,
  re-render. The locks still bound them; vision only improves the art
  inside those bounds.

## The vision-QA loop

    1. Render the .pix to PNG.
    2. Open the PNG (and, if helpful, an upscaled preview).
    3. Check: silhouette readable? light source per conventions? only
       legend ramps used? background fully cut out?
    4. If anything is off, edit the .pix rows.
    5. check_sprite.py, then re-render. Repeat until it matches the spec.

## Proving determinism (and cross-model consistency)

The claim "any agent produces the same output" reduces to a testable fact:
rendering is a pure function of (grid, spec). `scripts/tests/run_all.py`
asserts it directly — it renders the same `.pix` twice and checks the PNGs
are byte-identical. Because of that, two different models (Claude, Codex,
GPT, Gemini) that author the *same* grid get the *same* PNG; the only
remaining variable is the grid they draw, and the palette/canvas locks plus
`check_sprite.py` bound that too. To compare models for real, have each draw
the same prompt against one shared spec and diff the rendered PNGs — any
difference is purely in the authored shapes, never in size, color, or
background.

## Why this beats prompt-only consistency

Prompting a model with "use this style every time" drifts: wording is
fuzzy, the model forgets, and raster output is never identical. A locked
spec plus a deterministic renderer turns "style" into data the pipeline
enforces, so a new teammate — human or AI — produces matching assets on
day one by reading one JSON file.
