# Composing Parts into Finished Screens

Pixy's first job is **parts** (sprites, tiles, icons). This layer is the
**assembly**: turning those parts into a finished map, HUD, menu, or title
screen. Every step is deterministic, so the assembled result is identical for
any agent.

## Contents

- [The pipeline](#the-pipeline)
- [Tilemaps: tilemap.py](#tilemaps-tilemappy)
- [Scenes: compose_scene.py](#scenes-compose_scenepy)
- [Scalable UI frames: nine_slice.py](#scalable-ui-frames-nine_slicepy)
- [Pixel text: text_pix.py](#pixel-text-text_pixpy)
- [A worked example](#a-worked-example)

## The pipeline

1. **Parts** — author/validate/render sprites and tiles (the rest of Pixy).
2. **Maps** — lay tiles out with `tilemap.py`.
3. **UI pieces** — scale frames with `nine_slice.py`, render labels with
   `text_pix.py`.
4. **Finished screen** — place everything with `compose_scene.py`.

The manifests (`.tmap.json`, `scene.json`) are the **assembly instructions**;
the rendered PNG is the **finished result**. Keeping instructions as data
makes a screen reproducible and editable.

## Tilemaps: tilemap.py

Map single characters to tile `.pix` files and lay them in a grid:

    python scripts/tilemap.py level1.tmap.json --spec tiles.spec.json --out level1.png

```json
{
  "tiles": { "g": "grass.pix", "w": "water.pix", ".": null },
  "map": [ "ggggg", "gwwwg", "ggggg" ]
}
```

Every tile renders through the same spec, so they share size and palette and
the grid lines up. A `null`/unmapped char leaves a transparent gap. Output is
one PNG of `cols*tileW x rows*tileH`. Template: `templates/tilemap.json.tmpl`.

## Scenes: compose_scene.py

Place parts at pixel coordinates, layered back to front:

    python scripts/compose_scene.py scene.json --out screen.png

```json
{
  "canvas": [320, 180],
  "background": "transparent",
  "layers": [
    { "image": "level1.png", "at": [0, 0] },
    { "pix": "hero.pix", "spec": "tiles.spec.json", "scale": 8, "at": [40, 96] },
    { "image": "hud_panel.png", "at": [4, 4] },
    { "text": "SCORE 100", "at": [12, 8], "scale": 2, "color": "#ffffff" }
  ]
}
```

Layer types: `image` (a PNG), `pix` (a sprite, needs `spec`), `text` (pixel
text). The first layer is the bottom. Template: `templates/scene.json.tmpl`.

## Scalable UI frames: nine_slice.py

Resize a small frame to any size while keeping its corners intact - for
panels, buttons, dialogs, bars:

    python scripts/nine_slice.py panel.png --insets 4,4,4,4 --size 200x120 --out big.png

`--insets L,T,R,B` are the fixed border widths. Edges and center repeat
(`--mode tile`, the pixel-crisp default) or scale (`--mode stretch`). A `.pix`
frame works too with `--spec`.

## Pixel text: text_pix.py

Render UI text with the built-in 3x5 font (uppercase, digits, punctuation):

    python scripts/text_pix.py --text "GAME OVER" --png --color "#ffffff" --scale 6 --out go.png
    python scripts/text_pix.py --text "HP" --char K --out hp.pix

`--png` makes a colored image; the default makes a `.pix` grid (the `--char`
is the "on" color) that flows through the rest of the pipeline. The font is
embedded and deterministic, so labels look identical everywhere.

## A worked example

```bash
# tiles -> map
python scripts/tilemap.py level.tmap.json --spec tiles.spec.json --out level.png
# UI frame + label
python scripts/nine_slice.py panel.pix --spec ui.spec.json --insets 3,3,3,3 \
    --size 160x40 --out hud.png
# assemble the screen (map + character + HUD + score)
python scripts/compose_scene.py title.json --out title.png
```

`title.json` layers `level.png`, the hero sprite, `hud.png`, and a
`text` score into one finished screen.
