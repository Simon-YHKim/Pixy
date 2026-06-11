# 3D-to-pixel (OPTIONAL expert lane)

> **You do NOT need 3D tools to make directional or animated pixel art.**
> If the user cannot use Blender/Godot, this whole page is irrelevant — send
> them to the no-tools path instead (below). This page is only for users who
> *already* have a 3D model and the skills to render it.

## No 3D tools? Use words, not Blender

The point of this skill is that someone who can't model, rig, or animate can
still make game art. The benefit people want from 3D — many directions and
motion frames of one character, made once — is available with **zero tools**
via the image-first path (`charset`, pipeline P2):

    # 8-way directional set, no 3D, no drawing - just describe:
    python scripts/charset.py --spec hero.spec.json \
        --character "a small green slime with a happy face" \
        --poses s,se,e,ne,n,nw,w,sw --out-dir set/
    # generate one image per printed prompt (reuse the first as --ref so the
    # character stays identical), save as s.png .., then:
    python scripts/charset.py ... --images-dir raw/ --strict

    # a walk cycle the same way:
    --poses walk_0,walk_1,walk_2,walk_3   (... --animate walk --export aseprite)

charset writes a top-down facing prompt for each compass direction and a
"frame N of M, mid-stride" prompt for each walk frame, keeps identity locked,
conforms every frame to one spec, and gates consistency. Less geometrically
perfect than a real rig (back/3-4 angles can drift — fix an outlier by
regenerating it with the first pose as `--ref`), but it needs nothing but a
description.

---

The rest of this page is the **expert lane** for users who already have a 3D
asset.

## Pixy is NOT a 3D engine (by design)

The model, rig, motion, lighting, and render belong in a real 3D tool
(Blender, Godot, Maya, Unity). Reimplementing any of that inside a
stdlib+Pillow skill would be wrong and impossible to do well. **A rendered
frame is just another raster source** - exactly like an image model's output.
Pixy's job is the deterministic 2D back half it is already good at:

    3D tool: model -> rig -> motion -> render a frame sequence (PNGs)
    Pixy:    conform each frame -> ONE locked spec -> gate -> directional
             sprite sheet + per-direction GIFs + engine export

3D renders are even *better* input than generated art: palette, scale, and
alignment are identical frame-to-frame, so conform and the consistency gate
pass cleanly.

## The bridge: frames_to_pixel.py

Render your motion to `raw/<direction>_<frame>.png` (e.g. `s_0.png` ..
`s_5.png`, `se_0.png` ..), then:

    python scripts/frames_to_pixel.py raw/ --spec hero.spec.json --out-dir out/ \
        --directions s,se,e,ne,n,nw,w,sw --frames 6 \
        --denoise med --outline spec --outline-mode selout \
        --per-direction-gifs --export aseprite --strict --min-uniformity 70

It conforms every frame into the spec, lays them out as a
**directions x frames** sheet (`out/sheet_sheet.png` + `sheet_sheet.json`),
optionally writes one GIF per direction and an engine export, and gates set
uniformity + per-frame craft. One direction (`--directions s`) = a plain
motion cycle.

Get the spec first the usual way - derive it from a reference render so the
palette is the game's: `analyze_sample one_render.png --colors 15
--canvas 64x64 --background transparent --hue-shift --out hero.spec.json`.

## Blender headless render recipe

Render a turntable (8 directions) of frame F to transparent PNGs. Save as
`render_dirs.py` and run `blender model.blend --background --python
render_dirs.py`:

    import bpy, math, os
    scene = bpy.context.scene
    scene.render.film_transparent = True            # alpha background (nukki)
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.resolution_x = scene.render.resolution_y = 256
    cam = bpy.data.objects['Camera']
    pivot = bpy.data.objects['Pivot']               # camera parented to this
    out = os.path.abspath('raw'); os.makedirs(out, exist_ok=True)
    DIRS = ['s','se','e','ne','n','nw','w','sw']     # 8-way, matches the tool
    FRAMES = list(range(0, 60, 10))                  # motion keyframes to sample
    for fi, frame in enumerate(FRAMES):
        scene.frame_set(frame)
        for di, d in enumerate(DIRS):
            pivot.rotation_euler[2] = math.radians(di * 360.0 / len(DIRS))
            scene.render.filepath = os.path.join(out, f'{d}_{fi}.png')
            bpy.ops.render.render(write_still=True)

Tips that make conform clean: **orthographic camera** (no perspective skew
across directions), **flat/cell shading** with few materials (closer to the
target palette = less for the quantizer to do), render at a small integer
multiple of your native canvas (e.g. 256 for a 64px sprite, `--contain` off),
and a **fixed key light** matching the spec's light direction so
`lint_pix`'s light check passes.

Any 3D tool works as long as it writes `<direction>_<frame>.png` with a
transparent background. Godot: an orthographic `SubViewport` + a rotating
pivot, save each frame; same naming.

## When NOT to use this

For a single hero portrait or an icon, image-first (P1) is faster. 3D-to-pixel
pays off when you need **many directions x many motion frames** of the same
rig - top-down/isometric characters, vehicles, anything with 4/8-way movement.
The cost is authoring the 3D asset; the payoff is the whole sheet from one rig.
