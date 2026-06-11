# Track 2: Blender via MCP (the agent drives Blender, not the user)

Track 1 (pure LLM + image model) needs zero tools but its angles are only as
consistent as the image model. Track 2 gets **true geometric consistency** -
every direction and motion frame rendered from one 3D scene - and, when a
**Blender MCP server** is connected, it needs **zero user skills**: the AGENT
operates Blender. The user never opens it.

## When to use which track

| | Track 1 (pure LLM) | Track 2 (Blender MCP) |
|---|---|---|
| needs | an image model | Blender + a blender-mcp server connected |
| user skills | none | none (the agent drives) |
| angle/frame consistency | good, model-dependent (gates catch drift) | exact (same scene, rotated camera) |
| visual richness | high (image model paints) | blockout-simple unless a real model exists |
| best for | hero art, icons, style sets | 4/8-way movement sets, many motion frames |

Detection: if the session's tools include a Blender MCP (commonly
`execute_blender_code`, `get_scene_info`, screenshot/viewport tools), Track 2
is available. No MCP but the user has Blender? Same scripts run via
copy-paste into Blender's Scripting tab or `blender f.blend --background
--python script.py` - still no 3D skills, just paste.

## The agent procedure (end to end)

1. **Lock the spec first**, as always (`init_spec` preset or `analyze_sample`
   from a reference). The palette drives the blockout colors.
2. **Emit the Blender script** with `blender_snippet.py`:
   - User has no model -> `--mode blockout` BUILDS a primitive character from
     words: `--parts "sphere,body,0 0 0.55,0.55,#2b52c0;sphere,head,0 0
     1.25,0.38,#6ae2f5;sphere,eyeL,-0.14 -0.3 1.3,0.07,#12143b;..."`.
     Translate the user's character description into 3-8 primitives
     (sphere/cube/cylinder/cone), positions in meters, and FLAT colors taken
     from the spec legend. Crude is fine - at 64px a blockout reads great.
   - A model already exists in the scene -> `--mode render` (just the
     camera/light rig + the render loop).
   - Both modes set up everything conform needs: orthographic camera,
     transparent film, key light matching the spec's top-left light,
     `--res` an integer multiple of the canvas (256 for 64px).
3. **Execute through MCP**: send the emitted script to
   `execute_blender_code`. It is idempotent (safe to re-run) and ends by
   printing `PIXY_RENDER_DONE <dir> ...`. If the MCP variant has a
   viewport/screenshot tool, peek once before rendering to sanity-check the
   blockout silhouette.
4. **Find the PNGs**: Blender writes `<out_dir>/<direction>_<frame>.png` on
   the machine where Blender runs (`//pixy_raw` = beside the .blend; ask the
   MCP for `bpy.path.abspath` if unsure - the script prints the absolute
   path).
5. **Back into the normal factory**:

       python scripts/frames_to_pixel.py pixy_raw/ --spec hero.spec.json \
           --out-dir out/ --directions s,se,e,ne,n,nw,w,sw --frames 1 \
           --denoise med --outline spec --outline-mode selout \
           --per-direction-gifs --export aseprite --strict

   Conform, directional sheet, GIFs, engine export, uniformity + craft gates -
   identical to any other raster source. Run the Loop to SHIP.

## Motion frames via MCP

For walk/idle cycles the blockout needs keyframes. Keep it primitive-simple:
bob the body Z or rotate limbs a few degrees over the timeline with
`execute_blender_code` (e.g. keyframe `Pixy_body.location.z` at frames 1/11/21),
then emit `--mode render --frames 4 --anim-start 1 --anim-step 5`. The
sampling loop does the rest. For anything beyond bob/sway, prefer Track 1
walk prompts or a user-supplied rigged model.

## Honest limits

- A blockout is chunky by design: silhouettes and palette are exact, faces
  are simple. For a charming face at 64px, composite Track 1 art for the
  front pose and Track 2 for the other 7 directions, or hand-touch the
  `.pix` (it stays editable).
- MCP variants differ; `execute_blender_code` is the lowest common
  denominator this track relies on. Without any MCP and without Blender
  installed, Track 2 is unavailable - use Track 1.
