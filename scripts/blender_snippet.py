#!/usr/bin/env python3
"""Emit ready-to-run Blender Python for the Blender-MCP track (Track 2).

Usage:
    # full no-skills path: BUILD a blockout character from primitives, set up
    # an ortho pixel-art camera/light, render directions x frames:
    blender_snippet.py --mode blockout --out-dir //pixy_raw \
        --parts "sphere,body,0 0 0.55,0.55,#2b52c0;sphere,head,0 0 1.25,0.38,#6ae2f5;
                 sphere,eyeL,-0.14 -0.3 1.3,0.07,#12143b;sphere,eyeR,0.14 -0.3 1.3,0.07,#12143b" \
        --directions s,se,e,ne,n,nw,w,sw --frames 1 --res 256

    # scene already exists (user's model or MCP-built): just the render loop
    blender_snippet.py --mode render --out-dir //pixy_raw \
        --directions s,e,n,w --frames 6 --anim-start 1 --anim-step 5

The printed script is what an AGENT executes through the blender-mcp server's
`execute_blender_code` tool (or the user pastes into Blender's Scripting tab -
copy-paste, no 3D skills). It writes `<out>/<direction>_<frame>.png` with a
transparent background, orthographic camera, and a fixed key light matching
the spec's top-left light - exactly what `frames_to_pixel.py` ingests next.

Why emit code instead of calling Blender: Pixy stays a 3D-free skill; the 3D
work happens wherever Blender lives (the user's machine via MCP), and this
generator guarantees the render settings that make conform clean.

Exit codes: 0 = printed/written, 2 = usage error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

VALID_PRIMS = ("sphere", "cube", "cylinder", "cone")

HEADER = '''import bpy, math, os, tempfile

# --- Pixy pixel-art render rig (generated; safe to re-run) ---
scene = bpy.context.scene
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'   # Blender 4.2+
except TypeError:
    scene.render.engine = 'BLENDER_EEVEE'        # Blender 3.x - 4.1
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'  # before color_mode: RGBA is
scene.render.image_settings.color_mode = 'RGBA'  # invalid under e.g. FFMPEG
scene.render.resolution_x = scene.render.resolution_y = {res}
scene.render.resolution_percentage = 100
out_dir = bpy.path.abspath("{out_dir}")
if "{out_dir}".startswith('//') and not bpy.data.filepath:
    # unsaved .blend: '//' has no anchor - use a real absolute temp dir
    out_dir = os.path.join(tempfile.gettempdir(), 'pixy_raw')
os.makedirs(out_dir, exist_ok=True)

def _ensure(name, maker):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = maker()
        ob.name = name
    return ob

# pivot the camera orbits around
pivot = _ensure('PixyPivot', lambda: bpy.data.objects.new('PixyPivot', None))
if pivot.name not in {{o.name for o in scene.collection.objects}}:
    scene.collection.objects.link(pivot)

def _mk_cam():
    cam_data = bpy.data.cameras.new('PixyCam')
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = {ortho}
    ob = bpy.data.objects.new('PixyCam', cam_data)
    scene.collection.objects.link(ob)
    return ob
cam = _ensure('PixyCam', _mk_cam)
cam.parent = pivot
cam.location = (0.0, -{dist}, {height})
cam.rotation_euler = (math.radians({tilt}), 0.0, 0.0)
scene.camera = cam

def _mk_sun():
    sd = bpy.data.lights.new('PixySun', type='SUN')
    sd.energy = 3.0
    ob = bpy.data.objects.new('PixySun', sd)
    scene.collection.objects.link(ob)
    return ob
sun = _ensure('PixySun', _mk_sun)
# key light from top-left; PARENTED to the pivot so the light direction stays
# top-left in screen space for every facing direction (lint's light check)
sun.parent = pivot
sun.rotation_euler = (math.radians(50), 0.0, math.radians(-35))
'''

BLOCKOUT = '''
# --- blockout: a primitive character built from words (no modeling skills) ---
def _flat_mat(name, hexv):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    # find Principled by TYPE (the UI name is locale-translated)
    bsdf = next((n for n in m.node_tree.nodes
                 if n.type == 'BSDF_PRINCIPLED'), None)
    r = int(hexv[1:3], 16) / 255.0
    g = int(hexv[3:5], 16) / 255.0
    b = int(hexv[5:7], 16) / 255.0
    if bsdf:  # update even on re-run, so changed part colors take effect
        bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)
        bsdf.inputs['Roughness'].default_value = 1.0
    return m

_PRIM_OPS = {{
    'sphere': lambda: bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8),
    'cube': lambda: bpy.ops.mesh.primitive_cube_add(),
    'cylinder': lambda: bpy.ops.mesh.primitive_cylinder_add(vertices=12),
    'cone': lambda: bpy.ops.mesh.primitive_cone_add(vertices=12),
}}
PARTS = {parts!r}
for prim, name, loc, scl, hexv in PARTS:
    if bpy.data.objects.get('Pixy_' + name) is None:
        _PRIM_OPS[prim]()
        ob = bpy.context.active_object
        ob.name = 'Pixy_' + name
        ob.location = loc
        ob.scale = (scl, scl, scl)
        ob.data.materials.append(_flat_mat('PixyM_' + name, hexv))
        bpy.ops.object.shade_smooth()
    else:
        _flat_mat('PixyM_' + name, hexv)   # refresh color on re-run

# only the blockout renders: hide pre-existing meshes/lights (the default
# scene's 2m Cube would otherwise engulf the character)
for ob in scene.objects:
    if ob.type == 'MESH' and not ob.name.startswith('Pixy_'):
        ob.hide_render = True
    if ob.type == 'LIGHT' and ob.name != 'PixySun':
        ob.hide_render = True
'''

RENDER_LOOP = '''
# --- render directions x frames -> <out>/<dir>_<frame>.png ---
DIRS = {dirs!r}
FRAMES = {frames}
ANIM_START = {anim_start}
ANIM_STEP = {anim_step}
for fi in range(FRAMES):
    if FRAMES > 1:
        scene.frame_set(ANIM_START + fi * ANIM_STEP)
    for di, d in enumerate(DIRS):
        pivot.rotation_euler = (0.0, 0.0, math.radians(di * 360.0 / max(1, len(DIRS))))
        scene.render.filepath = os.path.join(out_dir, f"{{d}}_{{fi}}.png")
        bpy.ops.render.render(write_still=True)
print("PIXY_RENDER_DONE", out_dir, len(DIRS), "dirs x", FRAMES, "frames")
'''


def parse_parts(raw: str):
    parts = []
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        bits = [b.strip() for b in item.split(",")]
        if len(bits) not in (4, 5):
            raise ValueError(f"part needs prim,name,'x y z',scale[,#hex]: {item!r}")
        prim, name, loc_s, scl_s = bits[0], bits[1], bits[2], bits[3]
        hexv = bits[4] if len(bits) == 5 else "#8888aa"
        if prim not in VALID_PRIMS:
            raise ValueError(f"prim must be one of {VALID_PRIMS}: {prim!r}")
        try:
            loc = tuple(float(v) for v in loc_s.split())
        except ValueError:
            raise ValueError(f"location must be three numbers 'x y z': {loc_s!r}")
        if len(loc) != 3:
            raise ValueError(f"location must be 'x y z': {loc_s!r}")
        if not (hexv.startswith("#") and len(hexv) == 7):
            raise ValueError(f"color must be #RRGGBB: {hexv!r}")
        try:
            scale = float(scl_s)
        except ValueError:
            raise ValueError(
                f"scale must be ONE number (uniform size in meters), got "
                f"{scl_s!r} - e.g. 'sphere,body,0 0 0.5,0.55,#2b52c0'")
        parts.append((prim, name, loc, scale, hexv))
    if not parts:
        raise ValueError("no parts parsed")
    return parts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=("render", "blockout"), required=True)
    p.add_argument("--out-dir", default="//pixy_raw",
                   help="Blender path for the PNGs (// = beside the .blend)")
    p.add_argument("--directions", default="s,se,e,ne,n,nw,w,sw")
    p.add_argument("--frames", type=int, default=1)
    p.add_argument("--anim-start", type=int, default=1,
                   help="first timeline frame to sample (render mode)")
    p.add_argument("--anim-step", type=int, default=5,
                   help="timeline frames between samples")
    p.add_argument("--res", type=int, default=256,
                   help="render resolution (integer multiple of the canvas)")
    p.add_argument("--ortho-scale", type=float, default=3.0)
    p.add_argument("--cam-dist", type=float, default=8.0)
    p.add_argument("--cam-height", type=float, default=5.5)
    p.add_argument("--cam-tilt", type=float, default=60.0,
                   help="camera X tilt in degrees (60 = high 3/4 top-down)")
    p.add_argument("--parts",
                   help="blockout parts: 'prim,name,x y z,scale[,#hex];...' "
                        "(prims: sphere/cube/cylinder/cone). Place small "
                        "details (eyes) proud of the parent surface by "
                        "0.05-0.1m or they vanish at sprite scale.")
    p.add_argument("--out", type=Path, help="write the script here instead "
                                            "of stdout")
    args = p.parse_args(argv)

    dirs = [d.strip() for d in args.directions.split(",") if d.strip()]
    if not dirs:
        print("error: --directions is empty", file=sys.stderr)
        return 2
    code = HEADER.format(res=args.res, out_dir=args.out_dir,
                         ortho=args.ortho_scale, dist=args.cam_dist,
                         height=args.cam_height, tilt=args.cam_tilt)
    if args.mode == "blockout":
        if not args.parts:
            print("error: --mode blockout requires --parts", file=sys.stderr)
            return 2
        try:
            parts = parse_parts(args.parts)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        code += BLOCKOUT.format(parts=parts)
    code += RENDER_LOOP.format(dirs=dirs, frames=args.frames,
                               anim_start=args.anim_start,
                               anim_step=args.anim_step)
    try:
        compile(code, "<blender-snippet>", "exec")     # syntax self-check
    except SyntaxError as e:
        print(f"internal error: emitted code does not parse: {e}",
              file=sys.stderr)
        return 2
    if args.out:
        args.out.write_text(code, encoding="utf-8")
        print(f"wrote {args.out} ({len(code)} bytes). Run it via the "
              f"blender-mcp execute_blender_code tool, Blender's Scripting "
              f"tab, or: blender file.blend --background --python {args.out}")
    else:
        print(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
