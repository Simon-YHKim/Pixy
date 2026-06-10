#!/usr/bin/env python3
"""Build the interactive detail calibrator HTML (self-contained, zero-token).

Usage:
    detail_calibrator.py --out calibrator.html

Generates a standalone HTML page that lets a user *dial in the detail they
want before generating*. It pre-renders two subjects (Earth, Human) along five
independent 0-100 sliders (10 steps each):

    resolution  - native pixel grid (16 -> 128)
    colors      - palette size / bit depth (2 -> 64)
    detail      - shading sophistication (flat -> shaded -> dither -> AA)
    frames      - animation smoothness (1 still -> 24 frames)
    cleanup     - imageify --denoise strength: how aggressively stray pixels
                  and small blobs are absorbed off flat areas (0 -> area 24)

Each slider step is a real pre-rendered example (base64-embedded), so it costs
no tokens at use time. Moving a slider shows that axis; the four chosen numbers
plus the user's own request are assembled into a copy-paste prompt for the LLM.
0 = early-DOS look, 100 = modern high-res pixel art.

Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import base64
import io
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from PIL import Image
except ImportError:
    print("error: Pillow is required. Install: python -m pip install Pillow",
          file=sys.stderr)
    sys.exit(3)

import imageify  # noqa: E402  (reuse the real denoise so the demo is faithful)

NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")
DISPLAY = 320  # px shown in the HTML (nearest-upscaled)

# 11 stops per axis -> score 0,10,...,100 (+10 each). Index = score // 10.
RES_STEPS = [16, 20, 24, 32, 40, 48, 56, 64, 80, 96, 128]
COLOR_STEPS = [2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96]
FRAME_STEPS = [1, 2, 3, 4, 5, 6, 8, 12, 16, 20, 24]
# Cleanup = how aggressively imageify --denoise absorbs stray pixels/blobs off
# flat areas. Values are the cluster-size threshold (--denoise-area N); 0 = off.
CLEANUP_STEPS = [0, 1, 2, 3, 4, 6, 8, 10, 14, 18, 24]
BITS = {2: "1-bit", 4: "2-bit", 6: "~2.5-bit", 8: "3-bit", 12: "~3.5-bit",
        16: "4-bit", 24: "~4.5-bit", 32: "5-bit", 48: "~5.5-bit", 64: "6-bit",
        96: "~6.5-bit"}
NSTEPS = 11


def hx(c):
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


# Cohesive ramps (dark -> light) for the procedural subjects.
OCEAN = [hx(c) for c in ("0b1b3a", "163e6e", "2f6fb0", "5aa9e6", "bfe3ff")]
LAND = [hx(c) for c in ("17361a", "276b2f", "4ea04a", "8fd06a", "d8f0a0")]
SKIN = [hx(c) for c in ("6a3b2a", "9c5a3c", "c98a5e", "e8b489", "f6d9b8")]
SHIRT = [hx(c) for c in ("3a2150", "5d2f7e", "8a4fb0", "b97fd6", "e0c0f0")]
HAIR = [hx(c) for c in ("1a1320", "39243f", "5d3f63", "8a6f90", "b9a0bd")]
CLOUD = (245, 248, 255, 235)
OUTLINE = (16, 14, 26)
LIGHT = (-0.62, -0.62, 0.49)  # top-left


def lambert(nx, ny):
    r2 = nx * nx + ny * ny
    if r2 > 1:
        return None
    nz = math.sqrt(1 - r2)
    v = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]
    return max(0.0, min(1.0, 0.5 + 0.5 * v))


def ramp_color(ramp, v, tones, dither, x, y):
    f = (v ** 1.5) * (tones - 1)
    i = int(round(f))
    i = max(0, min(tones - 1, i))
    if dither and 0 < i < tones - 1 and abs(f - i) > 0.25 and (x + y) % 2 == 0:
        i = min(tones - 1, i + (1 if f - i > 0 else -1))
    # ramp may be longer than `tones`; sample across it
    idx = round(i / max(1, tones - 1) * (len(ramp) - 1))
    return ramp[idx] + (255,)


ICE = (224, 238, 250, 255)
ATMO = (150, 200, 245)
CITY = (255, 211, 120, 255)


def _blend(col, other, t):
    return tuple(int(col[i] * (1 - t) + other[i] * t) for i in range(3)) + (255,)


def _hash(a, b):
    """Deterministic 0..1 value used for clustered terrain (no randomness)."""
    h = (int(a) * 73856093) ^ (int(b) * 19349663)
    return ((h & 0x7fffffff) % 1000) / 1000.0


def render_earth(native, detail, rot=0.0):
    """Detail adds CONTENT, not just tones: continents -> ice -> rivers ->
    forests -> night city-lights -> atmosphere. Features live in globe space
    (lon/lat) so they spin coherently with rot."""
    img = Image.new("RGBA", (native, native), (0, 0, 0, 0))
    px = img.load()
    cx = cy = (native - 1) / 2
    r = native * 0.46
    tones = max(2, min(5, 2 + detail // 2))
    dither = detail >= 8
    atmo = detail >= 3
    ice = detail >= 6
    clouds = detail >= 7
    rivers = detail >= 7
    forest = detail >= 8
    specular = detail >= 8
    lights = detail >= 9
    blobs = [(0.15, -0.1, 0.5, 0.45), (-0.45, 0.25, 0.42, 0.5),
             (0.55, 0.35, 0.3, 0.3), (-0.05, -0.5, 0.3, 0.22)]
    use = blobs[:1] if detail == 4 else (blobs if detail >= 5 else [])
    land = set()
    for y in range(native):
        for x in range(native):
            nx = (x - cx) / r
            ny = (y - cy) / r
            r2 = nx * nx + ny * ny
            if r2 > 1:
                continue
            nz = math.sqrt(max(0.0, 1 - r2))
            v = max(0.0, min(1.0, 0.5 + 0.5 * (nx * LIGHT[0] + ny * LIGHT[1]
                                               + nz * LIGHT[2])))
            lat = ny
            lon = math.atan2(nx, max(1e-3, nz)) / 1.6 + rot
            on_land = False
            for (bl, bt, bw, bh) in use:
                if ((((lon - bl + 1) % 2 - 1) / bw) ** 2
                        + ((lat - bt) / bh) ** 2) <= 1:
                    on_land = True
                    break
            ramp, vv = OCEAN, v
            if on_land:
                ramp = LAND
                if forest:                                # clustered terrain
                    hh = _hash(int((lon + 4) * 7), int((lat + 2) * 7))
                    vv = v * 0.6 if hh < 0.3 else (v * 0.82 if hh < 0.52 else v)
            col = ramp_color(ramp, vv, tones, dither, x, y)
            if on_land and rivers and abs(lat - 0.3 * math.sin(lon * 2.3 + 0.5)) < 0.045:
                col = _blend(ramp_color(OCEAN, v, tones, dither, x, y), (40, 90, 150), 0.4)
            if ice and abs(lat) > 0.66:
                col = _blend(col, ICE, 0.6)
            if clouds:
                cl = 0.5 * math.sin(lon * 2.0 + 1.7) + 0.5 * math.sin(lat * 4 - 0.6)
                if cl > 0.7 and v > 0.32:
                    col = CLOUD
            if on_land and lights and v < 0.46 \
                    and _hash(int((lon + 4) * 9), int((lat + 2) * 9)) < 0.12:
                col = CITY
            if atmo and not on_land and r2 > 0.9:
                col = _blend(col, ATMO, 0.5)
            px[x, y] = col
            if on_land:
                land.add((x, y))
    if use:                                               # 1px darker coastline
        coast = ramp_color(LAND, 0.26, tones, False, 0, 0)
        for (x, y) in list(land):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) not in land:
                    bx, by = (x + dx - cx) / r, (y + dy - cy) / r
                    if bx * bx + by * by <= 1:
                        px[x, y] = coast
                        break
    if specular:
        sx, sy = int(cx - r * 0.42), int(cy - r * 0.42)
        rr = max(2, native // 16)
        for dx in range(-rr, rr):
            for dy in range(-rr, rr):
                if 0 <= sx + dx < native and 0 <= sy + dy < native \
                        and px[sx + dx, sy + dy][3] \
                        and dx * dx + dy * dy <= (native // 20) ** 2:
                    px[sx + dx, sy + dy] = (245, 250, 255, 255)
    _outline_circle(px, native, cx, cy, r)
    return img


def _seg(px, native, x0, y0, x1, y1, half, color):
    """Fill a capsule (thick line) - used for swinging arms and legs."""
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    ir = int(half) + 1
    for s in range(steps + 1):
        t = s / steps if steps else 0.0
        ax, ay = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        for dy in range(-ir, ir + 1):
            for dx in range(-ir, ir + 1):
                if dx * dx + dy * dy <= half * half:
                    x, y = int(round(ax)) + dx, int(round(ay)) + dy
                    if 0 <= x < native and 0 <= y < native:
                        px[x, y] = color


def render_human(native, detail, phase=0.0):
    """phase 0..1 drives a walk cycle: arms/legs swing, head bobs, a blink and
    a mouth move so motion (not just up/down) reads even at low frame counts."""
    img = Image.new("RGBA", (native, native), (0, 0, 0, 0))
    px = img.load()
    tones = max(2, min(5, 2 + detail // 2))
    dither = detail >= 8
    hair = detail >= 4
    shade = detail >= 2
    u = native / 16.0
    cx = 8 * u
    swing = math.sin(phase * 2 * math.pi)            # legs/arms
    bob = -abs(math.sin(phase * 2 * math.pi)) * 0.6 * u

    def disk(dcx, dcy, rx, ry, ramp):
        for y in range(native):
            for x in range(native):
                nx = (x - dcx) / rx
                ny = (y - dcy) / ry
                if nx * nx + ny * ny <= 1:
                    v = (lambert(nx, ny) or 0.5) if shade else 0.7
                    px[x, y] = ramp_color(ramp, v, tones, dither, x, y)

    shoulder_y = 7.6 * u + bob
    hip_y = 10.6 * u + bob
    leg = (ramp_color(SHIRT, 0.32, tones, dither, 0, 0))   # dark "pants"
    arm = (ramp_color(SHIRT, 0.6, tones, dither, 1, 0))
    hand = SKIN[3] + (255,)
    # legs (feet swing opposite each other)
    _seg(px, native, cx - 0.9 * u, hip_y, cx - 0.9 * u + swing * 1.7 * u,
         15.3 * u + bob, 0.85 * u, leg)
    _seg(px, native, cx + 0.9 * u, hip_y, cx + 0.9 * u - swing * 1.7 * u,
         15.3 * u + bob, 0.85 * u, leg)
    # arms (swing opposite to the legs); hand = skin at the end
    for sgn, sw in ((-1, -swing), (1, swing)):
        hx = cx + sgn * 2.0 * u + sw * 1.5 * u
        hy = 11.4 * u + bob
        _seg(px, native, cx + sgn * 1.9 * u, shoulder_y, hx, hy, 0.7 * u, arm)
        _seg(px, native, hx, hy, hx, hy, 0.7 * u, hand)
    # torso over the arm/leg roots
    disk(cx, 9.2 * u + bob, 2.3 * u, 3.0 * u, SHIRT)
    # head
    head_cy = 5.1 * u + bob
    disk(cx, head_cy, 2.5 * u, 2.7 * u, SKIN)
    if detail >= 3:                                   # hair
        for y in range(native):
            for x in range(native):
                nx = (x - cx) / (2.7 * u)
                ny = (y - head_cy) / (2.9 * u)
                if nx * nx + ny * ny <= 1 and ny < -0.12:
                    v = lambert(nx, ny) or 0.5
                    px[x, y] = ramp_color(HAIR, v, tones, dither, x, y)
    # face features grow with detail: eyes -> mouth -> nose -> brow
    eye_y = int(round(head_cy - 0.2 * u))
    if detail >= 4:                                   # eyes (blink in anim)
        blink = 0.44 < (phase % 1.0) < 0.52
        for ex in (cx - 1.0 * u, cx + 1.0 * u):
            exi = int(round(ex))
            if blink:
                for dx in (-1, 0, 1):
                    if 0 <= exi + dx < native:
                        px[exi + dx, eye_y] = OUTLINE + (255,)
            else:
                for dy in (0, 1):
                    if 0 <= eye_y + dy < native:
                        px[exi, eye_y + dy] = OUTLINE + (255,)
        if detail >= 9:                               # brow
            for ex in (cx - 1.1 * u, cx + 1.1 * u):
                exi, yy = int(round(ex)), eye_y - 2
                if 0 <= exi < native and 0 <= yy < native and px[exi, yy][3]:
                    px[exi, yy] = _blend(px[exi, yy], (70, 45, 40), 0.6)
    if detail >= 6:                                   # nose
        nxp, nyp = int(round(cx)), int(round(head_cy + 0.5 * u))
        if 0 <= nxp < native and 0 <= nyp < native and px[nxp, nyp][3]:
            px[nxp, nyp] = _blend(px[nxp, nyp], (120, 80, 60), 0.5)
    if detail >= 5:                                   # mouth (opens off-beat)
        mouth_open = math.sin(phase * 4 * math.pi) > 0.3
        my = int(round(head_cy + 1.2 * u))
        for dx in range(-int(0.6 * u), int(0.6 * u) + 1):
            for dy in range(0, 2 if mouth_open else 1):
                x, y = int(round(cx)) + dx, my + dy
                if 0 <= x < native and 0 <= y < native and px[x, y][3]:
                    px[x, y] = OUTLINE + (255,)
    # clothing details grow with detail: collar -> belt -> folds -> scarf
    if detail >= 6:
        tcx, tcy, trx, tryy = cx, 9.2 * u + bob, 2.3 * u, 3.0 * u
        dark = ramp_color(SHIRT, 0.3, tones, dither, 0, 0)
        for y in range(int(tcy - tryy), int(tcy + tryy) + 1):
            for x in range(int(tcx - trx), int(tcx + trx) + 1):
                if not (0 <= x < native and 0 <= y < native and px[x, y][3]):
                    continue
                nxx, nyy = (x - tcx) / trx, (y - tcy) / tryy
                if nxx * nxx + nyy * nyy > 1:
                    continue
                if -0.62 < nyy < -0.5:                       # collar
                    px[x, y] = dark
                elif detail >= 9 and -0.82 < nyy <= -0.62:   # scarf accent
                    px[x, y] = (239, 125, 87, 255)
                elif detail >= 7 and 0.46 < nyy < 0.6:       # belt
                    px[x, y] = dark
                elif detail >= 8 and 0.05 < nyy < 0.5 \
                        and abs(abs(nxx) - 0.42) < 0.07:     # two cloth folds
                    px[x, y] = dark
    _outline_alpha(px, native)
    return img


def _outline_circle(px, native, cx, cy, r):
    for y in range(native):
        for x in range(native):
            if px[x, y][3]:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nxp, nyp = x + dx, y + dy
                    if not (0 <= nxp < native and 0 <= nyp < native) \
                            or px[nxp, nyp][3] == 0:
                        px[x, y] = OUTLINE + (255,)
                        break


def _outline_alpha(px, native):
    solid = {(x, y) for y in range(native) for x in range(native)
             if px[x, y][3]}
    for (x, y) in solid:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in solid:
                px[x, y] = OUTLINE + (255,)
                break


def quantize(img, n):
    rgb = img.convert("RGBA")
    alpha = rgb.getchannel("A")
    q = rgb.convert("RGB").quantize(colors=max(2, n), method=Image.Quantize.MEDIANCUT)
    out = q.convert("RGBA")
    out.putalpha(alpha)
    return out


# --- Cleanup (denoise) demo: quantize to a small palette, inject deterministic
# speckle so a flat area looks noisy, then run the real imageify.denoise_regions
# at each strength so the slider shows exactly what --denoise does. ---
GRID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghij"


def _img_to_grid(img, ncolors=14):
    """Quantize to <=ncolors and return (grid of legend chars, char->rgb)."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    q = rgba.convert("RGB").quantize(colors=ncolors, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    qpx = q.load()
    grid, cmap = [], {}
    for y in range(h):
        row = []
        for x in range(w):
            if px[x, y][3] < 128:
                row.append(".")
                continue
            i = qpx[x, y]
            ch = GRID_CHARS[i % len(GRID_CHARS)]
            cmap[ch] = (pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2])
            row.append(ch)
        grid.append(row)
    return grid, cmap


def _add_noise(grid, cmap, frac=0.12):
    """Flip ~frac of opaque pixels to another palette color (deterministic)."""
    chars = list(cmap)
    if not chars:
        return [row[:] for row in grid]
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for y in range(h):
        for x in range(w):
            if grid[y][x] == "." or _hash(x * 3 + 1, y * 7 + 2) >= frac:
                continue
            nc = chars[int(_hash(x * 5 + 2, y * 11 + 3) * len(chars)) % len(chars)]
            if nc != grid[y][x]:
                out[y][x] = nc
    return out


def _grid_to_img(grid, cmap):
    h, w = len(grid), len(grid[0])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c != ".":
                px[x, y] = cmap[c] + (255,)
    return img


def build_cleanup_ladder(render, native_base=64, detail_base=8):
    base = render(native_base, detail_base)
    grid, cmap = _img_to_grid(base)
    noisy = _add_noise(grid, cmap)
    out = []
    for area in CLEANUP_STEPS:
        g = [row[:] for row in noisy]
        if area > 0:
            imageify.denoise_regions(g, ".", "med", area=area)
        out.append(b64png(_grid_to_img(g, cmap)))
    return out


def up(img):
    s = max(1, DISPLAY // img.width)
    return img.resize((img.width * s, img.height * s), NEAREST)


def b64png(img):
    b = io.BytesIO()
    up(img).save(b, "PNG")
    return base64.b64encode(b.getvalue()).decode()


def b64gif(frames, fps):
    ups = [up(f).convert("RGBA") for f in frames]
    pal = [u.convert("P", palette=Image.Palette.ADAPTIVE) for u in ups]
    b = io.BytesIO()
    pal[0].save(b, "GIF", save_all=True, append_images=pal[1:],
                duration=max(40, round(1000 / fps)), loop=0, disposal=2)
    return base64.b64encode(b.getvalue()).decode()


def build_ladders(render, native_base=64, detail_base=8, color_base=64):
    res = [b64png(render(p, detail_base)) for p in RES_STEPS]
    colors = [b64png(quantize(render(native_base, detail_base), n))
              for n in COLOR_STEPS]
    detail = [b64png(render(96, d)) for d in range(NSTEPS)]  # room for features
    frames = []
    for fc in FRAME_STEPS:
        if fc == 1:
            frames.append(("png", b64png(render(native_base, detail_base))))
        else:
            # phase 0..1 = one full cycle (Earth spin / human walk)
            fr = [render(native_base, detail_base, i / fc) for i in range(fc)]
            frames.append(("gif", b64gif(fr, min(12, fc))))
    cleanup = build_cleanup_ladder(render)
    return {"resolution": res, "colors": colors, "detail": detail,
            "frames": frames, "cleanup": cleanup}


AXES = [
    ("resolution", "Resolution", RES_STEPS, "px"),
    ("colors", "Colors", COLOR_STEPS, "colors"),
    ("detail", "Detail", list(range(NSTEPS)), "shading"),
    ("frames", "Frames", FRAME_STEPS, "frames"),
    ("cleanup", "Cleanup (denoise)", CLEANUP_STEPS, "area"),
]
DETAIL_TABLE = [
    (0, "Flat fill, 1-2 tones - early-DOS look"),
    (20, "Solid + outline; basic shape, no features"),
    (40, "Shading + main features (continents / hair + eyes)"),
    (60, "+ secondary content (ice caps, mouth, collar) + outline"),
    (80, "+ texture & extras (rivers, forests, belt, cloth folds) + dither"),
    (100, "Max content + night lights, scarf, brow, specular, atmosphere - "
          "aiming at Sanabi-level hi-res (85+ usually needs hand-pixeling or "
          "reference-trace)"),
]


def build_html(subjects, title):
    import json
    data = {name: build_ladders(fn) for name, fn in subjects}
    rows = "".join(f"<tr><td>{s}</td><td>{d}</td></tr>" for s, d in DETAIL_TABLE)
    axis_html = ""
    for key, label, steps, unit in AXES:
        marks = " ".join(str(v) for v in steps)
        axis_html += f"""
      <div class="axis" data-axis="{key}">
        <label>{label} <span class="val" id="v_{key}">60</span>/100
          <span class="setting" id="s_{key}"></span></label>
        <input type="range" min="0" max="100" step="10" value="60"
               oninput="upd('{key}')" id="r_{key}">
        <div class="marks">{marks}</div>
      </div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><style>
 body{{background:#15161f;color:#e8e8ee;font:14px system-ui,sans-serif;margin:0;padding:24px;max-width:980px}}
 h1{{font-size:20px;margin:0 0 2px}} .sub{{color:#8b95b2;margin-bottom:18px}}
 .wrap{{display:flex;gap:24px;flex-wrap:wrap}}
 .stage{{flex:0 0 340px}}
 .preview{{width:340px;height:340px;background:#0e0f17 url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="10" height="10" fill="%231b1d2b"/><rect x="10" y="10" width="10" height="10" fill="%231b1d2b"/></svg>') repeat;border-radius:8px;display:flex;align-items:center;justify-content:center}}
 .preview img{{image-rendering:pixelated;max-width:100%;max-height:100%}}
 .tabs{{margin:10px 0}} .tabs button{{background:#252840;color:#cfd6ea;border:0;padding:6px 14px;border-radius:6px;cursor:pointer;margin-right:6px}}
 .tabs button.on{{background:#41a6f6;color:#0e0f17;font-weight:700}}
 .ctrl{{flex:1;min-width:320px}}
 .axis{{margin-bottom:14px}} .axis label{{display:block;margin-bottom:4px;font-weight:600}}
 .val{{color:#a7f070}} .setting{{color:#8b95b2;font-weight:400;font-size:12px}}
 input[type=range]{{width:100%}} .marks{{display:flex;justify-content:space-between;color:#56607e;font-size:9px;margin-top:2px}}
 table{{border-collapse:collapse;margin-top:16px;font-size:12px;width:100%}}
 td{{border-top:1px solid #2a2d44;padding:4px 8px;vertical-align:top}} td:first-child{{color:#ffcd75;width:42px;text-align:right;font-weight:700}}
 .prompt{{margin-top:18px}} textarea{{width:100%;height:90px;background:#0e0f17;color:#cfe;border:1px solid #2a2d44;border-radius:6px;padding:8px;font:13px monospace}}
 .row{{display:flex;gap:8px;align-items:center;margin:8px 0}}
 button.act{{background:#38b764;color:#08120a;border:0;padding:8px 16px;border-radius:6px;font-weight:700;cursor:pointer}}
 #req{{flex:1;background:#0e0f17;color:#cfe;border:1px solid #2a2d44;border-radius:6px;padding:8px}}
 label.ck{{color:#cfd6ea}}
</style></head><body>
<h1>Pixy Detail Calibrator</h1>
<div class="sub">Dial in the look you want, then copy the prompt into your LLM. 0 = early-DOS, 100 = modern hi-res pixel art. Each step is a real pre-rendered example.</div>
<div class="wrap">
 <div class="stage">
   <div class="preview"><img id="pic" src=""></div>
   <div class="tabs"><button id="t_earth" class="on" onclick="setSub('earth')">Earth</button><button id="t_human" onclick="setSub('human')">Human</button></div>
   <div style="color:#8b95b2;font-size:12px">Showing axis: <b id="curaxis">detail</b> (move a slider to preview that axis)</div>
 </div>
 <div class="ctrl">
   {axis_html}
   <div class="row"><label class="ck"><input type="checkbox" id="anim" onchange="compose()"> Animate</label>
     <span style="color:#8b95b2;font-size:12px">(uses the Frames value)</span></div>
   <table><tr><th></th><th style="text-align:left;color:#8b95b2">Detail level means</th></tr>{rows}</table>
 </div>
</div>
<div class="prompt">
 <div style="font-weight:600;margin-bottom:6px">Your request (subject, mood, references):</div>
 <div class="row"><input id="req" oninput="compose()" placeholder="e.g. a glowing health potion, fantasy RPG, cute"></div>
 <textarea id="out" readonly></textarea>
 <div class="row"><button class="act" onclick="copyOut()">Copy prompt</button><span id="copied" style="color:#a7f070"></span></div>
</div>
<script>
const DATA={json.dumps(data)};
const STEPS={{resolution:{json.dumps(RES_STEPS)},colors:{json.dumps(COLOR_STEPS)},detail:{json.dumps(list(range(NSTEPS)))},frames:{json.dumps(FRAME_STEPS)},cleanup:{json.dumps(CLEANUP_STEPS)}}};
const BITS={json.dumps(BITS)};
let sub='earth', axis='detail';
function idx(k){{return Math.round(+document.getElementById('r_'+k).value/10);}}
function setImg(k){{axis=k;document.getElementById('curaxis').textContent=k;
  const e=DATA[sub][k][idx(k)];
  let src; if(Array.isArray(e)){{src='data:image/'+(e[0]=='gif'?'gif':'png')+';base64,'+e[1];}}else{{src='data:image/png;base64,'+e;}}
  document.getElementById('pic').src=src;}}
function setting(k){{const v=STEPS[k][idx(k)];
  if(k=='resolution')return v+'px'; if(k=='colors')return v+' ('+BITS[v]+')';
  if(k=='frames')return v+(v==1?' (still)':' frames');
  if(k=='cleanup')return v==0?'none (raw)':'absorb <'+v+'px blobs'; return 'level '+v;}}
function upd(k){{document.getElementById('v_'+k).textContent=document.getElementById('r_'+k).value;
  document.getElementById('s_'+k).textContent=' -> '+setting(k); setImg(k); compose();}}
function setSub(s){{sub=s;document.getElementById('t_earth').className=s=='earth'?'on':'';
  document.getElementById('t_human').className=s=='human'?'on':''; setImg(axis);}}
function compose(){{
  const r=+document.getElementById('r_resolution').value, c=+document.getElementById('r_colors').value,
        d=+document.getElementById('r_detail').value, f=+document.getElementById('r_frames').value;
  const anim=document.getElementById('anim').checked;
  const req=document.getElementById('req').value.trim()||'<describe the subject>';
  let p='Create pixel art: '+req+'. Target detail (Pixy 0-100): resolution '+r+' ('+setting('resolution')+'), colors '+c+' ('+setting('colors')+'), detail '+d+'/100 shading';
  p+=anim?(', animated '+setting('frames')+'.'):' , single frame.';
  p+=' Keep one light direction and a locked palette so the set stays uniform.';
  if(d>=80)p+=' (High detail: use a 64px+ canvas, 5-tone ramps + dither; 85+ may need hand-pixeling or reference-trace.)';
  // Image-first conform step: the cleanup slider maps straight to imageify flags.
  const clArea=STEPS.cleanup[idx('cleanup')];
  let conform='python scripts/imageify.py GENERATED.png --spec pixy.spec.json --out asset.pix';
  if(clArea>0)conform+=' --denoise-area '+clArea; else conform+=' --denoise none';
  if(d>=80)conform+=' --dither';   // only smooth/painterly art wants dither
  conform+=' --force';
  p+='\\n\\n# If you generate a raster (image-first), conform it into the spec:\\n'+conform;
  if(clArea>0)p+='\\n# (cleanup absorbs <'+clArea+'px stray blobs off flat areas; thin lines survive. Lower it if outlines break up.)';
  document.getElementById('out').value=p;
}}
function copyOut(){{
  const t=document.getElementById('out'); t.focus(); t.select();
  try{{ t.setSelectionRange(0, t.value.length); }}catch(e){{}}
  let ok=false; try{{ ok=document.execCommand('copy'); }}catch(e){{}}
  if(!ok && navigator.clipboard){{ navigator.clipboard.writeText(t.value).catch(()=>{{}}); ok=true; }}
  const c=document.getElementById('copied');
  c.textContent = ok ? 'Copied!' : 'Press Ctrl+C to copy';
  setTimeout(()=>{{c.textContent='';}}, 1600);
}}
['resolution','colors','detail','frames','cleanup'].forEach(k=>{{document.getElementById('s_'+k).textContent=' -> '+setting(k);}});
setImg('detail');compose();
</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, required=True, help="output .html")
    p.add_argument("--title", default="Pixy Detail Calibrator")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)
    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    doc = build_html([("earth", render_earth), ("human", render_human)],
                     args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(doc, encoding="utf-8")
    print(f"wrote {args.out}  ({len(doc)//1024} KB, 2 subjects x 5 axes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

