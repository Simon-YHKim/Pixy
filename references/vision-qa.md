# Vision QA Rubric (for agents that can SEE the render)

`craft_score.py` is the headless judge; this rubric is the seeing judge.
After `render_sprite.py`, open the PNG and walk this checklist top to bottom.
Each item names the failure, the question to ask of the image, and the exact
fix - so the QA pass ends in commands, not adjectives.

## How to run the pass

1. Render at export scale AND look at a 1x mental squint - pixel art must
   read at game size, not only zoomed.
2. Walk the checklist. Stop at the FIRST failing item; fix; re-render;
   restart the checklist (early items mask later ones).
3. Two clean passes in a row = ship. Note the craft_score alongside - if the
   eye says fine but craft < 70, trust the eye and say so in the report.

## The checklist

| # | Check | Ask the image | Fix |
|---|-------|---------------|-----|
| 1 | Silhouette | Cover the interior (squint): is the subject identifiable from the outline alone? | reshape in the `.pix`; this is unfixable by filters |
| 2 | Identity | Does it still look like THE character (eyes/marks/colors), not a generic one? | re-conform with reference palette (`analyze_sample --include`), lower `--denoise` |
| 3 | Readability | At 1x, do face/key features read without zooming? | bigger canvas, or simplify detail (`--simplify`) |
| 4 | Flat purity | Are areas that should be one color actually one color (no speckle)? | `--denoise med..max`, `autofix` |
| 5 | Contours | Do curves step cleanly (no 1px wobbles, no jaggies)? | `autofix --smooth` |
| 6 | Outline | Is the edge defined - 1px, consistent mode (hard or sel-out), no double bands? | `--outline spec [--outline-mode selout]` |
| 7 | Light | Do highlights sit toward the spec light, shadows opposite? | reshade `shade_form --light`, or flip |
| 8 | Dither | If dithered: a regular checker weave, never random noise? | `--dither-mode ordered`, or drop `--dither` |
| 9 | Palette | Ramps in use, no near-duplicate colors, shadows lean cool / lights warm? | `--hue-shift` derive, `transform_pix --recolor` |
| 10 | Cut-out | Background fully transparent, no halo/fringe pixels? | `--bg-tolerance`, `autofix` |
| 11 | Frame | Centered, sane margins, feet on the baseline? | `proportions --fit` |

## For animation (after `animate.py` / `animate_fx.py`)

| # | Check | Fix |
|---|-------|-----|
| A1 | Loop seam: does the last->first transition pop? | settle frame, `--pingpong`; confirm with `anim_score --loop` |
| A2 | Volume: does the sprite's mass stay constant across frames? | redraw the offending frame |
| A3 | Ground contact: do the feet stay planted (unless airborne)? | `animate --register`, pivot anchor |
| A4 | Timing: do key poses hold longer than in-betweens? | per-frame `ms` in the manifest |

## For sets (after `charset.py` / `consistency_report.py`)

- Line the renders up side by side: same character? same light? same outline
  mode? same scale of detail? Any odd-one-out goes back through the loop with
  the first pose's image as `--ref`.

## Report format

End the QA pass with exactly this block so the result is actionable:

    VISION-QA: PASS | FAIL @ item N
    craft_score: NN/100
    fix: <the one command or .pix edit to do next, or "none">
