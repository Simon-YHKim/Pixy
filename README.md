# Pixy The Pixel Art

A Claude Code **Skill** that makes *any* LLM produce pixel-art assets with the
**same fidelity** every time — identical canvas size, identical palette,
identical transparent background — whether the artist is Claude, Codex, GPT,
or Gemini.

> Same grid + same spec → byte-identical pixels. Guaranteed, and tested.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [How it works](#how-it-works)
- [Install](#install)
- [Quickstart](#quickstart)
- [The workflow](#the-workflow)
- [The `.pix` format](#the-pix-format)
- [The spec (`pixy.spec.json`)](#the-spec-pixyspecjson)
- [Script reference](#script-reference)
- [Presets](#presets)
- [The fidelity guarantee](#the-fidelity-guarantee)
- [Testing & CI](#testing--ci)
- [Repository layout](#repository-layout)
- [License](#license)

---

## Why this exists

Ask any model to "draw a 32×32 slime sprite with a transparent background" ten
times and you get ten different sizes, palettes, and backgrounds. Ask two
different models and it is worse. Pixel art for a game or app needs the
opposite: every asset must share one exact size, one palette, one cut-out
rule.

Pixy fixes this by refusing to leave consistency to the model. It splits the
job in two:

- **The non-artistic parts** (size, scale, palette, transparency, file
  format) are *locked in a spec and enforced by code*. No model can deviate.
- **The artistic part** (the actual shapes) is the only thing the model
  decides — and even that is bounded by a hard validation gate and assisted by
  drawing/tracing tools so weaker models still produce in-spec art.

The result: the technical fidelity of the output is **identical across every
model**. The only thing that varies is how good the shapes look, which is the
one thing no tool can fully equalize — and Pixy is honest about that.

For higher quality than an LLM can type by hand, Pixy adds an **image-first
path**: an image model draws the picture and Pixy *conforms* it into the locked
spec (`generate_pixel.py` → `imageify.py`) — quantizing to the exact palette,
keying out the background, and cleaning stray pixels off flat areas
(line-preserving `--denoise`) so surfaces read clean, with optional `--dither`
for smooth gradients and `--simplify` for a chunkier/cuter look. The model
supplies the art; the spec still supplies the palette, canvas, and cut-out —
quality up, consistency intact. And since v0.28 the skill is not a toolbox
but an **operating procedure**: SKILL.md drives the agent through mandatory
pipelines with hard gates and a self-correction loop — nothing reaches the
user before a **SHIP** verdict (craft score + lint + vision QA). See
`references/image-generation.md`.

## How it works

Three locks, one deterministic renderer:

1. **Palette lock** — the legend (`char → #RRGGBB`) lives in the spec and is
   shared by every sprite and every agent. The renderer refuses any character
   that is not in the legend, so color can never drift.
2. **Canvas lock** — the renderer refuses a grid whose dimensions differ from
   the spec, so every asset exports at the same size.
3. **Cut-out (누끼) lock** — the `transparent_char` always renders to alpha 0,
   so backgrounds are removed reliably without manual masking.

The agent authors a plain-text **character grid** (`.pix`). The renderer maps
each character to its locked color and scales the grid up with
nearest-neighbor (no blur). Rendering is a pure function of `(grid, spec)`, so
the same inputs always produce the same pixels — proven by a golden-hash
regression test.

## Install

Clone the repo straight into your Claude Code skills directory:

```bash
git clone https://github.com/Simon-YHKim/Pixy.git ~/.claude/skills/pixy-the-pixel-art
```

Requirements:

- **Python ≥ 3.9**
- **Pillow** (`python -m pip install Pillow`) — only for the rendering,
  animation, and image-tracing scripts. Everything else (spec, validation,
  drawing, transform, lint, palette, batch, export) is pure standard library,
  so it runs anywhere.

Run scripts from inside the skill directory: `python scripts/<name>.py ...`.

**Or install as a Claude Code plugin** (bundles the skill + slash commands
`/pixy-new`, `/pixy-index`, `/pixy-doctor`):

```
/plugin marketplace add Simon-YHKim/Pixy
/plugin install pixy-the-pixel-art@pixy
```

## Quickstart

```bash
# 0. IMAGE-FIRST EXPRESS (the quality path): a generated/reference image ->
#    character-true spec -> conform -> gates -> animated asset, one command
python scripts/pixyfly.py art.png --name hero --out-dir out/ \
    --colors 15 --canvas 64x64 --hue-shift \
    --denoise med --outline spec --outline-mode selout --fx hover --gif
#    (sets: scripts/charset.py --poses ... | --subjects ... --template ...)

# 1. Lock a project style (presets: game-character, tileset, ui-icon,
#    web-avatar, emoji, marquee, icon-hd, portrait, emblem, hero, keyart,
#    scene, poster, mural, unity, godot, rpgmaker, gameboy, nes,
#    gba-battle, gba-overworld, pico8)
python scripts/init_spec.py --out pixy.spec.json --preset game-character

# 2. Block in a sprite with shapes (or hand-author the grid), then validate
python scripts/draw_pix.py --spec pixy.spec.json --out slime.pix \
    --circle 16,19,11,g,fill --circle 16,15,9,G,fill \
    --dot 12,16,K --dot 20,16,K --line 14,20,18,20,K --outline K
python scripts/check_sprite.py slime.pix --spec pixy.spec.json

# 3. Render an exact-size, transparent PNG
python scripts/render_sprite.py slime.pix --spec pixy.spec.json --out slime.png

# 4. Animate frames into a GIF + APNG + sprite sheet
python scripts/animate.py --spec pixy.spec.json \
    --frames walk_0.pix walk_1.pix walk_2.pix walk_3.pix \
    --out walk --format all --fps 8

# 5. Assemble parts into a finished screen
python scripts/tilemap.py level.tmap.json --spec tiles.spec.json --out level.png
python scripts/compose_scene.py scene.json --out screen.png   # map + hero + HUD text
```

Pixy is not just an asset maker — it is a game-art **implementation** aid:
the parts (sprites, tiles, icons), how they assemble (tilemaps, scenes), the
finished result (composed screens), and the UI/UX that packages it (9-slice
frames, pixel text). See `references/composition.md`.

### Quality: shading and reference fidelity

Flat output looks like a doodle because volume (highlights, shadows, rim
light) is what makes pixel art read as finished. Don't hand-place shades —
block a flat silhouette, then shade it:

```bash
python scripts/draw_pix.py --spec emblem.spec.json --out gem.pix --circle 24,24,18,b,fill
python scripts/shade_form.py gem.pix --spec emblem.spec.json --region b \
    --ramp "D,b,c,L,W" --form sphere --light tl --rim --ao --out gem.pix
```

To hit a specific detailed/HD reference, reproduce it in one command:

```bash
python scripts/trace_image.py reference.png --derive 32 \
    --out-spec ref.spec.json --out ref.pix
```

Use 48px+ canvases (`icon-hd`, `portrait`, `emblem`) for detail, and the
high-res `hero` (128) / `keyart` (192) / `scene` (256) presets — paired with the
image-first path — for reference-level fidelity. See
`references/shading.md`.

**Pick a target before you generate:** open `assets/calibrator.html` — slide
resolution / colors / detail / frames / cleanup against live Earth & Human
examples (0 = early-DOS, 100 = modern hi-res) and copy a target-detail prompt
plus the matching `imageify --denoise` command. After generating,
`detail_score.py` rates the result so you can direct regeneration.

## The workflow (v0.28: enforced pipelines)

SKILL.md is an operating procedure, not a menu. The agent dispatches the
request to one of six pipelines and must run it to a SHIP verdict:

| Pipeline | For | Backbone |
|---|---|---|
| **P1 single asset** | one sprite/icon, "high quality", a reference | `analyze_sample` → generate → **`pixyfly`** (conform→render→gate→fx GIF, one command) |
| **P2 character set** | poses/walk frames of ONE character | `charset --poses` (identity chaining) → `--animate walk --export aseprite` |
| **P3 style set** | DIFFERENT subjects, one style (icon packs) | `charset --subjects --template` (the shared scene as an identical-by-contract block; never one grid image) |
| **P4 animation** | idle/hover/blink/hit, GIF/sheet | `animate_fx` cycles or P2 frames → `animate` → `anim_score --loop` seam gate |
| **P5 hand-authored** | offline / simple sprites & tiles | `draw_pix` → `shade_form` → `autofix --smooth` |
| **P6 maps & screens** | tilemaps, HUD, title screens | `--tileable` conform, `autotile`, `tilemap`, `compose_scene` |

Every pipeline ends in **the Loop**: `craft_score` (discipline 0-100 + fix
commands) + `lint_pix` + vision QA (`references/vision-qa.md`) → apply the
suggested fix or regenerate with `craft_score --brief` → max 2 retries →
deliver only with the evidence line. Iron rules forbid the failure modes we
hit in the field: raw model output as a deliverable, sets generated as one
grid image, hand-written image prompts, art before a locked spec.

## The `.pix` format

Plain text, diff-friendly, deterministic:

- Lines starting with `#` are comments/metadata (ignored).
- Blank lines are ignored.
- Every other line is one grid row of single characters.
- Each character maps to a color via the spec `legend`; the `transparent_char`
  (default `.`) is the background / cut-out.
- Row count must equal `canvas.height`; each row length must equal
  `canvas.width` (enforced by `check_sprite.py`).

Example (8×8):

```
# heart, 8x8
..RR.RR.
.RRRRRRR
.RRRRRRR
.RRRRRRR
..RRRRR.
...RRR..
....R...
........
```

## The spec (`pixy.spec.json`)

The single source of truth for a project's style:

| Field | Meaning |
|-------|---------|
| `canvas.width` / `canvas.height` | Native pixel grid. Every `.pix` must match exactly. |
| `scale` | Export upscale factor (nearest-neighbor). 32×32 @ 8 → 256×256 PNG. |
| `background` | `"transparent"` (cut-out) or `#RRGGBB` (solid fill). |
| `transparent_char` | Grid char that renders to alpha 0 (default `.`). |
| `legend` | The locked palette: `char → #RRGGBB`. The only colors any sprite may use. |
| `outline` | Which legend char is the outline, and its style. |
| `conventions` | Prose style notes (light source, shading) read by the agent. |
| `export` | Output format and filename pattern. |

## Script reference

| Script | What it does |
|--------|--------------|
| `init_spec.py` | Scaffold a spec from a use-case/engine/console preset and flags. |
| `generate_pixel.py` | **Image-first**: spec-tuned prompt → image model (host tool / OpenAI / local cmd) → conform into the spec. |
| `imageify.py` | Conform any raster into a clean in-spec `.pix`: area-average downscale, dither to the locked palette, background cut-out, cleanup. |
| `pixyfly.py` | One command: image -> spec -> conform -> render -> craft gate (verdict) -> animate GIF. |
| `frames_to_pixel.py` | 3D-to-pixel bridge: a rendered frame sequence -> conformed in-spec frames + directions x frames sheet + per-direction GIFs + export. |
| `blender_snippet.py` | Track 2: emit ready-to-run Blender Python (MCP execute_blender_code / paste / headless) - pixel camera+light rig, words->primitive blockout, render loop. |
| `pixy_doctor.py` | Environment check: which track is ready + exact platform install command for what's missing. |
| `pixy_index.py` | Scan a project -> searchable HTML asset library + JSON catalog (thumbnails, sets, craft, drift). |
| `charset.py` | Consistent character sets: identity-locked pose prompts, img2img chaining, conform + gates. |
| `craft_score.py` | Retro-craft discipline 0-100 + fix commands + regeneration brief (headless self-QA). |
| `animate_fx.py` | Motion cycles from one sprite: bob/hover/breathe/sway/shake/blink/flash -> frames + GIF. |
| `check_sprite.py` | **Hard gate**: validate a `.pix` against the spec (size, palette, transparency). |
| `render_sprite.py` | Render a `.pix` to an exact-size, transparent PNG (Pillow). |
| `draw_pix.py` | Block in a grid with shapes (`--rect/--circle/--line/--dot/--fill-area`), `--mirror`, `--outline`. |
| `shade_form.py` | Shade a flat region into a 3D form (sphere/cylinder/bevel) with light, rim, AO, dither. |
| `transform_pix.py` | `--flip`, `--rotate`, `--recolor` (palette variants, opposite facings). |
| `trace_image.py` | Import a reference image as an editable `.pix` (auto native-size detection). |
| `lint_pix.py` | Craft lint: orphan pixels, holes, broken outlines, `--tileable`, `--max-colors`. |
| `analyze_sample.py` | Derive a draft spec (palette/alpha/native size) from a reference image. |
| `animate.py` | Frames → GIF + APNG + sprite sheet + JSON; `--pingpong`, `--onion`, per-frame ms. |
| `palette_tool.py` | Generate HSL ramps or import `.hex`/`.gpl` (Lospec) palettes into a spec. |
| `export_engine.py` | Export a sheet to Aseprite JSON or a CSS `steps()` HTML page. |
| `batch.py` | Run check/lint/render/recolor across many `.pix` via a glob. |
| `detail_score.py` | Score an asset's detail/finish 0–100 with sub-metrics and fix suggestions. |
| `gallery.py` | HTML review gallery of a set: thumbnails + detail scores + consistency summary. |
| `detail_calibrator.py` | Build the interactive detail-calibrator HTML — live canvas, 5 axes (`assets/calibrator.html`). |
| `consistency_report.py` | Score a set's uniformity 0–100 and flag the odd ones out. |
| `regen_prompt.py` | Turn a detail score + target into next steps and an LLM brief. |
| `ref_similarity.py` | Score how close an asset is to a reference image. |
| `autofix.py` | Safely clean a `.pix` (orphans, holes) and re-score. |
| `variants.py` | Reskin one `.pix` into material/palette variants. |
| `anim_score.py` | Score animation smoothness and flag jumpy frames. |
| `proportions.py` | Measure/check/`--fit` an asset against the spec frame (size, centering, baseline). |
| `frame_guide.py` | Render the spec frame as a guide overlay to author against. |
| `style_lock.py` | Stamp assets with the spec fingerprint and flag style drift. |
| `verify.py` | One-command project gate (check/lint/proportions/detail/uniformity/drift). |
| `autotile.py` | Turn a fill mask into a seamless terrain map with uniform borders. |
| `tilemap.py` | Assemble tile `.pix` files into one map PNG from a `.tmap.json` grid. |
| `compose_scene.py` | Layer images/sprites/text at coordinates into a finished screen. |
| `nine_slice.py` | Scale a UI frame to any size with 9-slice (corners intact). |
| `text_pix.py` | Render UI text with a built-in 3x5 pixel font to a `.pix` or PNG. |

Every script supports `--help`. Deep docs live in `references/`.

## Presets

`python scripts/init_spec.py --list` prints the live table.

| Preset | Canvas | Scale | Palette | Notes |
|--------|--------|-------|---------|-------|
| `game-character` | 32×32 | 8 | default 16 | Character sprite |
| `tileset` | 16×16 | 8 | default 16 | Map tile |
| `ui-icon` | 24×24 | 10 | default 16 | Interface icon |
| `web-avatar` | 64×64 | 4 | default 16 | Profile art |
| `emoji` | 16×16 | 6 | default 16 | Small glyph |
| `marquee` | 128×64 | 3 | default 16 | Banner / title |
| `icon-hd` | 48×48 | 6 | default 16 | Detailed icon |
| `portrait` | 64×64 | 5 | default 16 | Character bust |
| `emblem` | 96×96 | 3 | default 16 | Detailed emblem/badge |
| `hero` | 128×128 | 4 | default 16 | Detailed hero/key sprite (image-first) |
| `keyart` | 192×192 | 2 | default 16 | Rich illustration / boxart (image-first) |
| `scene` | 256×256 | 2 | default 16 | Full scene / cover art (image-first) |
| `poster` | 512×512 | 1 | default 16 | Large illustration / wallpaper (image-first) |
| `mural` | 1024×1024 | 1 | default 16 | Max 1024px canvas (image-first) |
| `unity` | 32×32 | 8 | default 16 | Point filter, PPU = canvas |
| `godot` | 16×16 | 8 | default 16 | Nearest texture filter |
| `rpgmaker` | 48×48 | 6 | default 16 | 48×48 character cell |
| `gameboy` | 16×16 | 8 | **4-shade green (locked)** | DMG gamut |
| `nes` | 16×16 | 8 | **2C02 gamut (28)** | NES; 3 colors/sprite gate |
| `gba-battle` | 64×64 | 6 | **15 (4bpp cap)** | GBA / FireRed-grade battle sprite |
| `gba-overworld` | 16×32 | 8 | **15 (4bpp cap)** | GBA overworld character |
| `pico8` | 16×16 | 8 | **fixed 16 (locked)** | PICO-8 palette |

For any target without a preset, set canvas/background/palette directly — see
`references/engine-targets.md`.

## The fidelity guarantee

**What is guaranteed (mechanically, across every model):** identical canvas
size, identical palette, identical transparency, identical file format. The
renderer is a pure function, so the same `.pix` and spec render to
byte-identical pixels on any machine and for any agent. `scripts/tests/run_all.py`
proves it with a golden hash: a fixed spec+grid must render to a recorded
pixel digest, and CI fails if that ever changes.

**What is not guaranteed:** the artistic quality of the shapes the model draws.
No tool can make a weak model draw as well as a strong one. Pixy minimizes this
variable too — `draw_pix`, `trace_image`, and `transform_pix` let weaker models
compose in-spec art from primitives instead of placing 1024 pixels by hand, and
the `check_sprite` + `lint_pix` gates reject anything off-spec — but it is
honest that shape quality still depends on the model.

See `references/consistency-rules.md` for the full rationale and the
vision-QA loop.

## Testing & CI

```bash
python scripts/tests/run_all.py     # 162 integration checks across all scripts
```

The suite covers every script end to end, plus **render determinism**
(same input → byte-identical output) and the **golden-fidelity** regression.
GitHub Actions (`.github/workflows/ci.yml`) runs the suite and an ASCII-clean
check on every push.

## Repository layout

```
pixy-the-pixel-art/        (this repo == the skill)
├── SKILL.md               the operating procedure (iron rules, 6 pipelines, the Loop)
├── references/            13 deep docs (image-gen, vision-qa, animation, engines, ...)
├── scripts/               41 tools + tests/run_all.py + tests/golden/ quality corpus
├── assets/calibrator.html interactive detail calibrator (pre-built)
├── templates/             starter spec, sprite, and animation manifest
├── evals/cases.json       behavioral eval cases
├── CHANGELOG.md           version history
└── .github/workflows/     CI
```

## License

Personal project — no license set.
