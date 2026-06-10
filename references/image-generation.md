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
- **`--dither`** — Floyd–Steinberg error diffusion to the locked palette.
- **`--bg-tolerance N`** — how aggressively the solid background is keyed out.
- Orphan/hole cleanup runs by default (`--no-clean` to skip).

Output is validated against the spec, so a bad conform fails loud just like a
hand-authored grid.

## Dithering to the locked palette

This is the single biggest quality lever. A 16-color palette cannot represent a
smooth shaded gradient with solid fills — you get visible banding. Floyd–
Steinberg dithering diffuses the quantization error to neighboring pixels, so a
gradient reads as a smooth blend *using only the spec's colors*. The result
looks shaded and three-dimensional while never leaving the palette lock. Always
pass `--dither` for shaded/organic subjects; drop it for flat, hard-cel art.

If a gradient dithers into an off-hue color (e.g. greens picking up browns), the
palette simply lacks mid-tones for that hue — use a spec whose palette has a
ramp for that material (see `references/palette-design.md`), or shade a flat
base with `shade_form.py` instead.

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
