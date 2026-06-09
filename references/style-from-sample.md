# Deriving a Spec from a Reference Image

When the user gives a sample image and says "match this style", split the
work: code extracts the **measurable** facts, and a vision-capable agent
refines the **judgment** parts.

## Step 1 — Extract hard data (code)

    python scripts/analyze_sample.py reference.png --out pixy.spec.json --colors 16

This writes a **draft** spec containing:

- **palette** — dominant colors quantized to `--colors` (default 16),
  assigned legend characters and sorted by luminance.
- **transparency** — whether the image has an alpha channel; sets
  `background` to `transparent` or to the dominant color.
- **native size** — estimated from the greatest-common-divisor of color
  run lengths, then divided into the source dimensions to get the grid.

The draft includes an `_analysis` block recording the source size,
estimated scale, alpha flag, and palette count.

## Step 2 — Review the estimates (do not blindly trust)

Pixel-size estimation is a heuristic. It works well on clean, integer-
upscaled pixel art and poorly on photos, anti-aliased, or JPEG-compressed
images. Check:

- **Native size sane?** If `analyze_sample` reports an odd grid (e.g.
  37×41), the source probably is not clean pixel art at an integer scale —
  ask the user for the intended grid, or set `--canvas` manually.
- **Palette not over-merged?** Quantization can collapse close shades.
  Bump `--colors` or relabel into clean ramps (see `palette-design.md`).

## Step 3 — Refine conventions (vision)

A vision-capable agent opens `reference.png` and fills in what code
cannot measure, writing it into the spec `conventions`:

- **Outline:** present? color? full or selective? width?
- **Light source:** which direction are highlights on?
- **Shading:** flat, ramped, or dithered? how many shades per material?
- **Edges:** hard pixels only, or hand-placed anti-aliasing?

## Step 4 — Lock and draw

Once the user confirms the native size, palette, and conventions, the
draft becomes the project spec. New sprites authored against it
(`authoring-format.md`) will match the reference's regularity — same
grid, same palette, same cut-out — because the locks now enforce it.

## Limitation

`analyze_sample.py` recovers the spec, not the artwork. It does not trace
the reference into a `.pix`; it captures the *style rules* so new assets
share them. To reproduce the reference image itself, author its grid by
hand against the derived spec.
