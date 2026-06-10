# Image-First Generation (high-quality assets)

## Contents

- [Why image-first](#why-image-first)
- [The two halves](#the-two-halves)
- [generate_pixel.py](#generate_pixelpy)
- [Providers](#providers)
- [imageify.py — the conform step](#imageifypy--the-conform-step)
- [Dithering to the locked palette](#dithering-to-the-locked-palette)
- [Background cut-out](#background-cut-out)
- [It still obeys the consistency contract](#it-still-obeys-the-consistency-contract)
- [Prompt design](#prompt-design)
- [When to use which path](#when-to-use-which-path)

## Why image-first

An LLM hand-authoring an ASCII grid is reliable, deterministic, and offline,
but its quality ceiling is a simple, stylized sprite. Painterly shading,
gradients, intricate silhouettes, and "looks like a finished game asset"
detail are very hard to type one character at a time — the output collapses
into a flat blob. That is not a tuning problem; it is the wrong tool for the
last mile of quality.

The image-first path uses an image model for the part it is good at (drawing a
rich picture) and uses Pixy for the part *it* is good at (forcing that picture
onto one locked palette, canvas size, and cut-out). Quality goes up; the
cross-asset, cross-agent consistency does not go down.

## The two halves

1. **Generate** a raster image from a text prompt (`generate_pixel.py`).
2. **Conform** that raster into the spec, deterministically (`imageify.py`).

The conform step is the durable, testable core. The generate step is
pluggable — it can be the host agent's own image tool, a hosted API, or a
local model — because once you have a PNG, conform is identical.

## generate_pixel.py

    python scripts/generate_pixel.py "a wizard frog with a staff" \
        --spec pixy.spec.json --out frog.pix --dither

It builds a prompt **from the spec** (native size, the exact palette hexes,
light direction, transparent/solid background), generates a raster via the
chosen `--provider`, and runs the conform step. Pass-through flags `--dither`,
`--contain`, and `--bg-tolerance` go to the conform step.

`--prompt-only` (the default when no key/command is configured) just prints the
tuned prompt and the exact `imageify` command to run next — this is the path
for an agent that has its own image generation: generate from the prompt, save
the PNG, conform it.

## Providers

| `--provider` | What it does | Needs |
|--------------|--------------|-------|
| `prompt-only` | Print the spec-tuned prompt + the conform command, stop. | nothing |
| `openai` | Call the OpenAI Images API and conform the result. | `OPENAI_API_KEY` (optional `PIXY_OPENAI_MODEL`) |
| `command` | Run any shell command; `{prompt}`/`{out_png}` are substituted. Use for local SD/ComfyUI/Flux. | a local generator |
| `file` | Conform an already-generated raster (`--image`). | a PNG |

`--keep-png PATH` saves the raw generated image alongside the `.pix` so you can
re-conform with different settings without regenerating.

## imageify.py — the conform step

`imageify` is built for **non-pixel-perfect** sources (AI art, photos,
gradients), which is exactly what an image model returns:

    python scripts/imageify.py frog.png --spec pixy.spec.json \
        --out frog.pix --dither --contain

- **Area-average downscale** (`BOX`) — averages source pixels into each native
  cell, so gradients and anti-aliased edges survive instead of aliasing into
  speckle. (Contrast `trace_image.py`, which point-samples — right for a clean
  integer-upscaled sprite, wrong for generated art.)
- **`--contain`** — aspect-preserving fit into the canvas with the spec frame
  margin, so a non-square subject is centered, not stretched.
- **`--dither`** — dither gradients into the locked palette (`--dither-mode
  ordered` = retro Bayer weave, default; `fs` = error diffusion).
- **`--bg-tolerance N`** — how aggressively the solid background is keyed out.
- Orphan/hole cleanup runs by default (`--no-clean` to skip).

Output is validated against the spec, so a bad conform fails loud just like a
hand-authored grid.

## Clean flat surfaces vs dithering

The most common "this doesn't look like clean pixel art" complaint is **stray
pixels scattered across an area that should be one flat color** — impurities on
a surface, shading that breaks into speckle instead of clean bands. Two settings
control this, and the defaults are tuned for the clean look:

- **`--denoise` (default `low`)** — line-preserving cleanup of "impurity" pixels
  off flat areas, in two stages: a per-pixel **majority filter** (snaps a stray
  speck to its surround) and a per-blob **cluster cleanup** (absorbs a whole
  connected same-color blob smaller than N pixels into the surrounding color).
  Levels raise both — `none` → `low` → `med` → `high` → `max` (blob threshold
  0/0/2/4/8). A 1px line is a *long* blob, so it survives. This is what makes a
  shaded pillar read as clean bands instead of scattered dots.
  - The per-pixel filter alone only kills lone 1px specks; 2-4px clumps need the
    cluster stage, which is why `med`+ are much stronger than `low`.
  - To push past `max`, set **`--denoise-area N`** directly (try 6-16). Higher N
    flattens more, but once N exceeds your *thin features'* blob size it starts
    eating short line segments and small highlights — back off if outlines or
    wireframes break up. `max` (8) is the safe strong ceiling.
- **`--dither` (off by default)** — dithering trades clean flats for gradient
  smoothness. Use it ONLY for genuinely smooth gradients where banding would
  otherwise show — never for cute/cel/flat art. Two patterns
  (`--dither-mode`): **`ordered`** (default) is the Bayer 4×4 checker weave
  hand-pixelled retro art actually used — regular, period-correct; `fs`
  (Floyd–Steinberg) is smoother but irregular — a modern image-processing
  look. If output looks busy or noisy, drop `--dither` first.

Rule of thumb: **clean / cute / cel** → no dither, `--denoise low|med` (and maybe
`--simplify`). **Rich / painterly / large** → `--dither`, `--denoise none`.

## Character preservation (simplify WITHOUT losing the soul)

Simplification must not eat the marks that carry the character - the sparkly
eyes, catch-lights, a heart, a smile. Those are *small* and *rare*, exactly
what naive cleanup removes first. Three safeguards (all on by default):

- **Contrast guard (`--denoise-guard`, default 150)** - quantization speckle
  sits between ADJACENT ramp tones (small color distance), while an eye or a
  catch-light is HIGH-contrast against its surround. Denoise and the simplify
  color cap only absorb strays within the guard distance, so ramp speckle is
  cleaned but features survive any `--denoise` level. Raise toward 442 only if
  you truly want featureless flat fills.
- **Feature re-injection (on; `--no-keep-features` to disable)** - plain
  area-average downscaling washes a dark pupil on a bright face into a pale
  blur (the mean). After the BOX pass each contrasty cell is split into its two
  color sides: the cell takes the **dominant** side (>=50%), so a round blob's
  boundary stays smooth and round - never lumpy - and snaps to the **minority**
  side only for a true thin feature (a catch-light, a 1px wireframe), detected
  as a minority that dominates no neighbouring cell. Eyes stay round AND
  sparkly; thin lines keep their weight.
- **Character-true palette** - a generic preset palette deadens a specific
  character (the #1 cause of "soulless" output). Derive the palette from the
  reference in one command, keeping your target canvas:

      python scripts/analyze_sample.py ref.png --colors 15 \
          --canvas 64x64 --background transparent --out char.spec.json
      python scripts/imageify.py ref.png --spec char.spec.json \
          --out char.pix --denoise med

  If a signature color is too small for the quantizer to allocate (an accent,
  a brand color), force it: `--include "#ff77a8,#b13e53"` keeps those in the
  legend within the `--colors` budget.

If a conform still loses a feature, lower `--denoise` first, then check the
palette actually contains the feature's colors (catch-light white, pupil dark)
before touching the guard.

If colors still look wrong (e.g. greens picking up browns), the palette lacks
mid-tones for that hue — use a spec whose palette has a ramp for that material
(see `references/palette-design.md`).

## Simplicity / cuteness control

More fidelity is not always better. Image models love to add fine detail
(stray highlights, busy texture, noisy edges) that makes a *cute* subject look
fussy — the charm of kawaii pixel art is a small effective grid, a few flat
colors, and clean shapes, not maximum detail. `--simplify` dials this in,
on both `imageify.py` and `generate_pixel.py`:

| `--simplify` | grid | colors | dither | use |
|--------------|------|--------|--------|-----|
| `none` | full | all | as set | faithful, maximal detail |
| `low` | full | ≤12 | on | lightly cleaned |
| `med` | /2 coarser | ≤8 | off (flat) | clean, designed look |
| `high` | /3 coarser | ≤6 | off (flat) | chunky, cute, poster-flat |

It works by shrinking the native grid then snapping it back (chunkier shapes),
keeping only the N most-used palette colors (remapping the rest to the nearest
kept one), forcing flat fills instead of dither, and median-filtering the
source first. If the output looks noisy or "tries too hard," raise the level.

Independently, **a small native canvas is itself a simplicity lever** — a cute
sprite is often better at 48-64px upscaled large (small grid, big `scale`) than
at 128px. Combine: a small canvas *or* `--simplify` for cute/clean, a large
canvas with `--dither` for rich/detailed.

## Background cut-out

For a transparent-background spec, imageify produces the cut-out (누끼) two ways:

- If the source already has alpha, that alpha is used.
- If the source is opaque (most image models return an opaque PNG even when
  asked for transparency), imageify detects the background color from the four
  corners and **flood-fills from the borders**, keying out only the
  background region connected to the edge — a subject that happens to share the
  background color is not punched full of holes. Prompt for a *flat solid*
  background (the composed prompt already does) to make this clean.

## It still obeys the consistency contract

Nothing about image-first relaxes the three locks:

- **Palette lock** — the conform step quantizes to the spec legend; no color
  outside it can appear (the renderer would reject it anyway).
- **Canvas lock** — the raster is downscaled to the exact spec canvas.
- **Cut-out lock** — background becomes the `transparent_char`.

So a conformed asset animates, recolors, composes, and passes `verify.py`
exactly like any hand-authored one, and two agents conforming the same raster
get the same `.pix`. The model's freedom is bounded to the picture; the
technical fidelity is still enforced by code.

## Prompt design

`build_prompt` already encodes the essentials; when writing your own prompt for
a host image tool, keep these:

- **State native resolution** ("about 32x32 native pixel resolution") and ask
  for **crisp hard-edged pixels** — discourages a smooth illustration that
  downscales poorly.
- **List the palette hexes** so the model stays near the locked colors (less
  error for the quantizer to diffuse).
- **One centered subject, even margins, flat solid background, no text / UI /
  watermark / ground shadow / frame.** These wreck the cut-out and the
  silhouette otherwise.
- Name the **light direction** from the spec so shading matches the rest of the
  project.

## When to use which path

- **Hand-authoring** (`draw_pix` + `shade_form`): small icons/tiles, flat or
  simple-shaded sprites, anything that must be produced fully offline and
  deterministically without an image model.
- **Image-first** (`generate_pixel` + `imageify`): hero characters, detailed
  emblems/portraits, richly shaded or organic subjects, or any time
  hand-authored output looks flat and the user wants higher fidelity. Make the
  hero asset image-first, then derive recolors, variants, and animation frames
  from its `.pix` so the whole set stays coherent.
- **Derive-trace** (`trace_image --derive`): when a *specific existing
  reference* defines the bar and you want a faithful, editable reproduction.
