# Runtime & control lessons (append-only, ship every entry)

Hard-won control- and runtime-level gotchas hit while *driving* Pixy — launch,
quoting, permissions, engine-API, GPU, headless, computer-use. These are NOT
art-craft notes (those go through the Loop / vision-qa). When you hit and fix a
new one, record it here and ship it with **`/pixy-learn`** so the skill never
repeats it. Format each entry: **Symptom -> Cause -> Fix** (one copy-pasteable
line where possible). Newest first inside each section.

---

## Blender Python API (5.x)

- **Engine enum changed.** 5.x exposes only `CYCLES`, `BLENDER_EEVEE`,
  `BLENDER_WORKBENCH`. The 4.2 name `BLENDER_EEVEE_NEXT` is gone (EEVEE-Next is
  now just `BLENDER_EEVEE`). Set the engine inside try/except and fall back.
- **`nodes.get("Principled BSDF")` returns None.** Under non-factory startup or
  a localized UI the node is not named in English (or the new material has no
  default tree). Find it by TYPE and create+link if missing:
  `b = next((n for n in nt.nodes if n.type=="BSDF_PRINCIPLED"), None)` then
  `nt.nodes.new("ShaderNodeBsdfPrincipled")` linked to a Material Output. Same
  pattern for the World `BACKGROUND` node. (`scripts/blender_snippet.py` already
  does this — copy it, never look up by display name.)
- **Emission input names.** 5.x Principled uses `Emission Color` +
  `Emission Strength` (not `Emission`). A part only glows if strength > 0.
- **`scene.node_tree` was REMOVED.** The compositor is now
  `scene.compositing_node_group` (a `CompositorNodeTree`). Inside that group the
  output is a `NodeGroupOutput` node fed via an OUTPUT `Image` socket on
  `nt.interface.new_socket(...)` — `CompositorNodeComposite` is *undefined*
  there and raises. Support both APIs (`hasattr(scene,"node_tree")`) and wrap
  the whole thing in try/except: compositor bloom is optional, never fatal.
- **Cycles renders on CPU unless you enable the GPU.** `compute_device_type`
  defaults to `NONE`. On an OptiX/CUDA box this is the difference between
  minutes and seconds (RTX renders 1600x1600 in ~6s). Enable it:

      prefs = bpy.context.preferences.addons["cycles"].preferences
      prefs.compute_device_type = "OPTIX"   # or "CUDA"
      prefs.refresh_devices()
      for d in prefs.devices: d.use = (d.type == "OPTIX")
      scene.cycles.device = "GPU"

  (EEVEE always uses the GPU, so the `blender_snippet` rig needs none of this —
  this is only for Cycles-quality stills.)
- **The BLOOM glare node blows out + smears glossy surfaces.** In 5.1 the
  compositor Glare `BLOOM` type over-blooms even at low mix and turns a glossy
  visor into a noisy cyan checkerboard. Keep bloom OFF or extremely subtle
  (high threshold, small size); let material emission + small point lights carry
  a restrained glow. "restrained glow" in a spec means: do not add heavy bloom.
- **`AgX` view transform desaturates neon.** Violet/cyan emission goes muddy
  under AgX. Use `Filmic` (tames clipping, keeps hue) or `Standard` for vivid
  palette art.
- `World.use_nodes` / `Material.use_nodes` / `Scene.use_nodes` print a
  "removed in 6.0" DeprecationWarning — harmless today, expect churn later.

## Process control & launching (Windows / PowerShell)

- **`Start-Process -ArgumentList` mangles paths with spaces.** Manual quotes get
  passed literally, the target isn't found, and the app silently opens its
  default doc (Blender showed "(Unsaved)" + the default cube). Use the call
  operator, which auto-quotes variable args: `& $exe "$pathWithSpaces"`. Or
  `Start-Process -WorkingDirectory <dir> -ArgumentList <bare-filename>` so the
  arg itself has no spaces.
- **Launching a GUI to let the user watch:** run it with the call operator under
  the tool's `run_in_background` — a foreground `& $gui` blocks until the window
  closes.

## Computer-use / GUI control

- **`open_application` on a launcher-backed app spawns a NEW default instance.**
  Blender's Start-menu entry is `blender-launcher.exe`, which starts a fresh
  `blender.exe` with the default scene every time — it does NOT focus the
  instance you already built into. Symptom: you keep seeing the default cube +
  splash. Focus the live window another way (taskbar click / it is already
  frontmost right after launch); don't re-`open_application` to refocus.
- **Grant the WORKER process, not just the launcher.** computer-use masks
  windows owned by ungranted processes as a solid gray rectangle. A launcher app
  needs the worker basename granted too (e.g. `blender.exe`), or the real window
  is invisible to screenshots even though the launcher name was approved.
- **RENDERED viewport stalls on first OptiX use.** The first rendered-shading
  frame compiles OptiX kernels — the viewport is blank/gray for ~10-30s. Wait,
  then nudge the mouse over the viewport to force a redraw before screenshotting.
- **Blender is rarely on PATH.** Use `blender_locate.find_blender()` (PATH +
  standard install dirs + `PIXY_BLENDER` override) instead of assuming `blender`
  resolves; `pixy_doctor` reports the resolved path.
