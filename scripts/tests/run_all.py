#!/usr/bin/env python3
"""Integration tests for every Pixy script.

Run: python scripts/tests/run_all.py

Exercises init_spec, check_sprite, render_sprite, draw_pix, transform_pix,
lint_pix, trace_image, palette_tool, animate, and export_engine end to end in
a temp directory, plus a determinism proof (the same grid + spec renders to
byte-identical PNGs). Pure stdlib + Pillow. Exit 0 iff all checks pass.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

# Golden render of a fixed 4x4 spec+grid at scale 2, hashed over raw RGBA
# pixels (encoder-independent). This is the fidelity invariant: if it ever
# changes, the renderer stopped producing identical output for identical
# input - the core cross-model guarantee would be broken.
GOLDEN_SPEC = {"canvas": {"width": 4, "height": 4}, "scale": 2,
               "background": "transparent", "transparent_char": ".",
               "legend": {"K": "#000000", "W": "#ffffff"}}
GOLDEN_ROWS = [".KK.", "KWWK", "KWWK", ".KK."]
GOLDEN_SHA256 = "7699c3424d5d2b5da43b2cff4f8b6507ae47ea9f270eca396f732089190ff48e"

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import init_spec, check_sprite, render_sprite, draw_pix  # noqa: E402
import transform_pix, lint_pix, trace_image, palette_tool  # noqa: E402
import animate, export_engine, batch, shade_form, detail_score, gallery  # noqa: E402
import detail_calibrator  # noqa: E402
import consistency_report, regen_prompt, ref_similarity  # noqa: E402
import autofix, variants, anim_score, proportions, frame_guide  # noqa: E402
import style_lock, verify, autotile  # noqa: E402
import text_pix, nine_slice, tilemap, compose_scene  # noqa: E402
import imageify, generate_pixel  # noqa: E402
from PIL import Image  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def run(mainfn, args):
    """Call a script main(argv) with output suppressed; return exit code."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            return mainfn(args)
        except SystemExit as e:  # scripts that sys.exit on missing Pillow
            return int(e.code or 0)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="pixy_test_"))
    spec = tmp / "pixy.spec.json"
    gb = tmp / "gb.spec.json"

    # init_spec
    check("init_spec game-character",
          run(init_spec.main, ["--out", str(spec), "--preset",
                               "game-character", "--force"]) == 0)
    data = json.loads(spec.read_text())
    check("spec canvas 32x32", data["canvas"] == {"width": 32, "height": 32})
    check("init_spec gameboy 4-color",
          run(init_spec.main, ["--out", str(gb), "--preset", "gameboy",
                               "--force"]) == 0
          and len(json.loads(gb.read_text())["legend"]) == 4)

    # draw_pix -> a valid sprite (filled circle + outline)
    sprite = tmp / "s.pix"
    check("draw_pix circle+outline",
          run(draw_pix.main, ["--spec", str(spec), "--out", str(sprite),
                              "--circle", "16,16,10,g,fill", "--outline", "K",
                              "--force"]) == 0)
    check("check_sprite OK on drawn",
          run(check_sprite.main, [str(sprite), "--spec", str(spec)]) == 0)

    # check_sprite rejects a bad grid
    bad = tmp / "bad.pix"
    bad.write_text("ZZZ\nZZZ\n", encoding="utf-8")
    check("check_sprite rejects bad",
          run(check_sprite.main, [str(bad), "--spec", str(spec)]) == 1)

    # render + determinism
    png1, png2 = tmp / "a.png", tmp / "b.png"
    r1 = run(render_sprite.main, [str(sprite), "--spec", str(spec),
                                  "--out", str(png1)])
    r2 = run(render_sprite.main, [str(sprite), "--spec", str(spec),
                                  "--out", str(png2)])
    check("render exits 0", r1 == 0 and r2 == 0)
    check("render deterministic (byte-identical)",
          png1.read_bytes() == png2.read_bytes())

    # transform: flip + recolor
    flipped = tmp / "flip.pix"
    check("transform flip h",
          run(transform_pix.main, [str(sprite), "--flip", "h",
                                   "--out", str(flipped), "--force"]) == 0)
    recolored = tmp / "blue.pix"
    check("transform recolor stays in-palette",
          run(transform_pix.main, [str(sprite), "--recolor", "g:b,G:c",
                                   "--out", str(recolored), "--spec", str(spec),
                                   "--force"]) == 0)

    # lint: clean drawn sprite, then an orphan
    check("lint clean sprite", run(lint_pix.main,
          [str(sprite), "--spec", str(spec)]) == 0)
    orphan = tmp / "orphan.pix"
    rows = check_sprite.parse_pix(sprite)
    grid = [list(r) for r in rows]
    grid[0][0] = "W"  # isolated pixel in the corner
    check_sprite.write_pix(["".join(r) for r in grid], orphan)
    check("lint --strict flags orphan",
          run(lint_pix.main, [str(orphan), "--spec", str(spec),
                              "--strict"]) == 1)

    # trace: render then trace back to a valid grid
    traced = tmp / "traced.pix"
    check("trace_image from rendered png",
          run(trace_image.main, [str(png1), "--spec", str(spec),
                                 "--out", str(traced), "--force"]) == 0
          and run(check_sprite.main, [str(traced), "--spec", str(spec)]) == 0)

    # palette_tool: ramp, import .hex, apply
    check("palette ramp", run(palette_tool.main,
          ["--ramp", "3b5dc9", "--steps", "5"]) == 0)
    hexpal = tmp / "p.hex"
    hexpal.write_text("000000\nff0000\n00ff00\n0000ff\nffffff\n",
                      encoding="utf-8")
    applied = tmp / "applied.spec.json"
    run(init_spec.main, ["--out", str(applied), "--preset", "ui-icon",
                         "--force"])
    check("palette import+apply",
          run(palette_tool.main, ["--import", str(hexpal), "--apply",
                                  str(applied), "--force"]) == 0
          and len(json.loads(applied.read_text())["legend"]) == 5)

    # animate: 3 frames -> all formats + onion + pingpong
    f0, f1, f2 = tmp / "f0.pix", tmp / "f1.pix", tmp / "f2.pix"
    for f, r in ((f0, 8), (f1, 10), (f2, 12)):
        run(draw_pix.main, ["--spec", str(spec), "--out", str(f),
                            "--circle", f"16,16,{r//2},g,fill",
                            "--outline", "K", "--force"])
    anim_out = tmp / "anim"
    check("animate all+onion+pingpong",
          run(animate.main, ["--spec", str(spec), "--frames", str(f0),
                             str(f1), str(f2), "--out", str(anim_out),
                             "--format", "all", "--fps", "8", "--pingpong",
                             "--onion"]) == 0)
    sheet_json = tmp / "anim_sheet.json"
    check("sheet json + gif + onion exist",
          sheet_json.exists() and (tmp / "anim.gif").exists()
          and (tmp / "anim_onion.png").exists())
    check("sheet count == 4 (3 frames + pingpong bounce)",
          json.loads(sheet_json.read_text())["count"] == 4)

    # export_engine: aseprite + css
    ase = tmp / "anim.ase.json"
    css = tmp / "anim.html"
    check("export aseprite",
          run(export_engine.main, [str(sheet_json), "--engine", "aseprite",
                                   "--out", str(ase), "--force"]) == 0
          and "frames" in json.loads(ase.read_text()))
    check("export css",
          run(export_engine.main, [str(sheet_json), "--engine", "css",
                                   "--out", str(css), "--force"]) == 0
          and "@keyframes" in css.read_text())

    # golden fidelity: fixed input must render to the recorded pixel hash
    gimg = render_sprite.render(GOLDEN_ROWS, GOLDEN_SPEC, GOLDEN_SPEC["scale"])
    check("golden render matches recorded hash (fidelity invariant)",
          hashlib.sha256(gimg.tobytes()).hexdigest() == GOLDEN_SHA256)

    # draw_pix flood-fill
    fillp = tmp / "fill.pix"
    check("draw_pix flood-fill",
          run(draw_pix.main, ["--spec", str(spec), "--out", str(fillp),
                              "--rect", "4,4,24,24,K", "--fill-area", "16,16,g",
                              "--force"]) == 0
          and run(check_sprite.main, [str(fillp), "--spec", str(spec)]) == 0)

    # lint --max-colors
    check("lint --max-colors flags overflow",
          run(lint_pix.main, [str(sprite), "--spec", str(spec),
                              "--max-colors", "1", "--strict"]) == 1)

    # lint --tileable on a seamless full-fill tile (no seam holes/orphans)
    tile = tmp / "tile.pix"
    run(draw_pix.main, ["--spec", str(gb), "--out", str(tile),
                        "--rect", "0,0,16,16,K", "--fill-area", "0,0,L",
                        "--force"])
    check("lint --tileable clean on full tile",
          run(lint_pix.main, [str(tile), "--spec", str(gb), "--tileable"]) == 0)

    # batch: check + render over a glob in a subdir
    bdir = tmp / "batchset"
    bdir.mkdir()
    for i in range(3):
        run(draw_pix.main, ["--spec", str(spec), "--out", str(bdir / f"s{i}.pix"),
                            "--circle", f"16,16,{4+i},g,fill", "--force"])
    check("batch check over glob",
          run(batch.main, ["check", "--spec", str(spec),
                           "--glob", f"{bdir.as_posix()}/*.pix"]) == 0)
    check("batch render over glob",
          run(batch.main, ["render", "--spec", str(spec),
                           "--glob", f"{bdir.as_posix()}/*.pix",
                           "--out-dir", str(tmp / "bpng"), "--force"]) == 0
          and len(list((tmp / "bpng").glob("*.png"))) == 3)

    # text_pix: .pix grid (5 rows) and a colored PNG
    txt = tmp / "score.pix"
    check("text_pix .pix grid",
          run(text_pix.main, ["--text", "SCORE 1", "--char", "K",
                              "--out", str(txt), "--force"]) == 0
          and len(check_sprite.parse_pix(txt)) == 5)
    txtpng = tmp / "score.png"
    check("text_pix png",
          run(text_pix.main, ["--text", "HI", "--png", "--color", "#ffffff",
                              "--scale", "3", "--out", str(txtpng),
                              "--force"]) == 0 and txtpng.exists())

    # two solid 16x16 tiles on the gameboy spec, then a tilemap
    t1, t2 = tmp / "t1.pix", tmp / "t2.pix"
    run(draw_pix.main, ["--spec", str(gb), "--out", str(t1),
                        "--rect", "0,0,16,16,L", "--fill-area", "0,0,L",
                        "--force"])
    run(draw_pix.main, ["--spec", str(gb), "--out", str(t2),
                        "--rect", "0,0,16,16,D", "--fill-area", "0,0,D",
                        "--force"])
    tmap = tmp / "m.tmap.json"
    tmap.write_text(json.dumps({"tiles": {"a": "t1.pix", "b": "t2.pix",
                                          ".": None},
                                "map": ["aba", "bab"]}), encoding="utf-8")
    mapout = tmp / "map.png"
    check("tilemap assemble 3x2 tiles",
          run(tilemap.main, [str(tmap), "--spec", str(gb), "--out",
                             str(mapout), "--force"]) == 0
          and Image.open(mapout).size == (3 * 16 * 8, 2 * 16 * 8))

    # nine-slice a 16x16 frame up to 48x32
    frame = tmp / "frame.png"
    check("nine_slice scales frame",
          run(nine_slice.main, [str(t1), "--spec", str(gb), "--insets",
                                "2,2,2,2", "--size", "48x32", "--out",
                                str(frame), "--force"]) == 0
          and Image.open(frame).size == (48, 32))

    # compose a scene: map background + pixel text overlay
    scene = tmp / "scene.json"
    scene.write_text(json.dumps({
        "canvas": [200, 120], "background": "#1a1c2c",
        "layers": [{"image": "map.png", "at": [0, 0]},
                   {"text": "HP 100", "at": [4, 4], "scale": 2,
                    "color": "#ffffff"}]}), encoding="utf-8")
    sout = tmp / "scene.png"
    check("compose_scene layers to finished screen",
          run(compose_scene.main, [str(scene), "--out", str(sout),
                                   "--force"]) == 0
          and Image.open(sout).size == (200, 120))

    # shade_form: flat region -> shaded form, in-palette, multi-tone, stable
    shball = tmp / "shball.pix"
    run(draw_pix.main, ["--spec", str(spec), "--out", str(shball),
                        "--circle", "16,16,12,b,fill", "--force"])
    shout = tmp / "shaded.pix"
    shargs = [str(shball), "--spec", str(spec), "--region", "b", "--ramp",
              "D,b,c,W", "--form", "sphere", "--light", "tl", "--rim", "--ao",
              "--out", str(shout), "--force"]
    check("shade_form sphere in-palette",
          run(shade_form.main, shargs) == 0
          and run(check_sprite.main, [str(shout), "--spec", str(spec)]) == 0)
    shrows = check_sprite.parse_pix(shout)
    tones = {c for row in shrows for c in row if c in set("DbcW")}
    check("shade_form produced >=3 tones (not flat)", len(tones) >= 3)
    shout2 = tmp / "shaded2.pix"
    run(shade_form.main, shargs[:-3] + ["--out", str(shout2), "--force"])
    check("shade_form deterministic",
          shout.read_text() == shout2.read_text())

    # spec-locked shading: --material only (light/outline come from the spec)
    sdata = json.loads(spec.read_text())
    check("spec has a locked shading block",
          "shading" in sdata and "materials" in sdata["shading"]
          and sdata["shading"].get("outline"))
    matout = tmp / "mat.pix"
    check("shade_form --material (spec-locked style)",
          run(shade_form.main, [str(shball), "--spec", str(spec), "--region",
                                "b", "--material", "blue", "--form", "sphere",
                                "--rim", "--ao", "--out", str(matout),
                                "--force"]) == 0
          and run(check_sprite.main, [str(matout), "--spec", str(spec)]) == 0)

    # detail_score: a shaded form must outscore a flat blob, with suggestions
    flatp = tmp / "flatp.pix"
    run(draw_pix.main, ["--spec", str(spec), "--out", str(flatp),
                        "--circle", "16,16,13,b,fill", "--force"])
    specd = json.loads(spec.read_text())
    flat_r = detail_score.score(check_sprite.parse_pix(flatp), specd)
    shaded_r = detail_score.score(check_sprite.parse_pix(matout), specd)
    check("detail_score: shaded scores higher than flat",
          shaded_r["overall"] > flat_r["overall"])
    check("detail_score: flat flagged low with fix suggestions",
          flat_r["grade"] in ("flat/blocky", "basic")
          and len(flat_r["suggestions"]) >= 1)
    check("detail_score main runs",
          run(detail_score.main, [str(matout), "--spec", str(spec)]) == 0)

    # gallery: HTML review page with one card per asset
    gal = tmp / "gallery.html"
    check("gallery builds HTML with a card per asset",
          run(gallery.main, [str(shout), str(matout), "--spec", str(spec),
                             "--out", str(gal), "--force"]) == 0
          and gal.exists()
          and gal.read_text(encoding="utf-8").count('class="card"') == 2)

    # detail_calibrator: builds the interactive HTML with sliders + prompt JS
    cal = tmp / "cal.html"
    check("detail_calibrator builds interactive HTML",
          run(detail_calibrator.main, ["--out", str(cal), "--force"]) == 0
          and cal.exists()
          and 'id="r_detail"' in cal.read_text(encoding="utf-8")
          and "function compose" in cal.read_text(encoding="utf-8"))
    check("detail_calibrator is a live canvas (not baked images)",
          'id="cv"' in cal.read_text(encoding="utf-8")
          and "function renderEarth" in cal.read_text(encoding="utf-8")
          and len(cal.read_bytes()) < 200 * 1024)
    check("detail_calibrator has the cleanup/denoise axis",
          'id="r_cleanup"' in cal.read_text(encoding="utf-8")
          and "denoise-area" in cal.read_text(encoding="utf-8"))

    # trace --derive: reproduce a render with an auto-matched palette + spec
    derived, dspec = tmp / "derived.pix", tmp / "derived.spec.json"
    check("trace --derive builds spec + faithful pix",
          run(trace_image.main, [str(png1), "--derive", "6", "--out-spec",
                                 str(dspec), "--out", str(derived),
                                 "--force"]) == 0
          and dspec.exists()
          and run(check_sprite.main, [str(derived), "--spec",
                                      str(dspec)]) == 0)

    # imageify: conform a non-pixel-perfect raster (soft gradient blob on a
    # solid bg) into a clean in-spec .pix - bg keyed out, dithered, multi-tone
    import math as _math
    gen = tmp / "gen.png"
    gimg2 = Image.new("RGB", (160, 160), (8, 10, 18))
    gpx = gimg2.load()
    for yy in range(160):
        for xx in range(160):
            dd = _math.hypot(xx - 80, yy - 80)
            if dd < 64:
                # full dark->light grayscale ramp so the gradient crosses
                # several palette luminance bands (K/D/B/L/W)
                lv = max(0.0, min(1.0, 0.5 + 0.5 * ((80 - xx) + (80 - yy)) / 90))
                v = int(20 + 220 * lv)
                gpx[xx, yy] = (v, v, v)
    gimg2.save(gen)
    imgpix = tmp / "img.pix"
    check("imageify conforms a raster to a valid in-spec grid",
          run(imageify.main, [str(gen), "--spec", str(spec), "--out",
                              str(imgpix), "--dither", "--force"]) == 0
          and run(check_sprite.main, [str(imgpix), "--spec", str(spec)]) == 0)
    irows = check_sprite.parse_pix(imgpix)
    itones = {c for row in irows for c in row if c != "."}
    check("imageify dithering yields a shaded multi-tone result (>=3 tones)",
          len(itones) >= 3)
    check("imageify keys out the solid background (not fully opaque)",
          any("." in row for row in irows))
    # --simplify trades detail for a cleaner/cuter read: fewer colors as the
    # level rises, and still a valid in-spec grid
    simp_counts = {}
    for lvl in ("none", "high"):
        sp_pix = tmp / f"simp_{lvl}.pix"
        run(imageify.main, [str(gen), "--spec", str(spec), "--out", str(sp_pix),
                            "--dither", "--simplify", lvl, "--force"])
        rws = check_sprite.parse_pix(sp_pix)
        simp_counts[lvl] = len({c for row in rws for c in row if c != "."})
        check(f"imageify --simplify {lvl} stays valid in-spec",
              run(check_sprite.main, [str(sp_pix), "--spec", str(spec)]) == 0)
    check("imageify --simplify high uses no more colors than none (flatter)",
          simp_counts["high"] <= simp_counts["none"])

    # denoise: a stray "impurity" pixel on a flat field is cleaned, but a 1px
    # line survives (line-preserving majority filter)
    field = [["g"] * 9 for _ in range(9)]
    for ci in range(9):
        field[2][ci] = "K"          # a horizontal 1px line
    field[5][4] = "W"               # a stray impurity on the flat field
    imageify.denoise_regions(field, ".", "med")
    check("denoise removes a stray pixel on a flat field", field[5][4] == "g")
    check("denoise preserves a 1px line",
          all(field[2][ci] == "K" for ci in range(9)))
    # stronger cluster cleanup: a 2x2 noise blob is absorbed, a line survives
    field2 = [["g"] * 12 for _ in range(12)]
    for ci in range(12):
        field2[2][ci] = "K"
    for yy in (6, 7):
        for xx in (6, 7):
            field2[yy][xx] = "W"
    imageify.denoise_regions(field2, ".", "none", area=5)
    check("denoise --area absorbs a small color blob",
          field2[6][6] == "g" and field2[7][7] == "g")
    check("denoise --area keeps a long line (blob > area)",
          all(field2[2][ci] == "K" for ci in range(12)))
    # default conform leaves flat regions clean (no dither) and stays valid
    defpix = tmp / "default.pix"
    check("imageify default (no dither) conforms a valid clean grid",
          run(imageify.main, [str(gen), "--spec", str(spec), "--out",
                              str(defpix), "--force"]) == 0
          and run(check_sprite.main, [str(defpix), "--spec", str(spec)]) == 0)

    # upscale stays crisp: a tiny 2-color source conformed into a much larger
    # canvas must use NEAREST (no blended in-between tones from a BOX upscale)
    tiny = tmp / "tiny.png"
    timg = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for yy in range(1, 7):
        for xx in range(1, 7):
            timg.putpixel((xx, yy), (244, 244, 244, 255) if xx < 4
                          else (26, 28, 44, 255))
    timg.save(tiny)
    up_pix = tmp / "up.pix"
    run(imageify.main, [str(tiny), "--spec", str(spec), "--out", str(up_pix),
                        "--no-crop", "--denoise", "none", "--force"])
    up_rows = check_sprite.parse_pix(up_pix)
    up_used = {c for row in up_rows for c in row if c != "."}
    check("imageify upscale is crisp (2-color source -> 2 colors, no blends)",
          len(up_used) <= 2)

    # high-resolution presets exist for the image-first path (more detail)
    for hp, dim in (("hero", 128), ("keyart", 192), ("scene", 256),
                    ("poster", 512), ("mural", 1024)):
        hspec = tmp / f"{hp}.spec.json"
        check(f"init_spec preset {hp} is {dim}x{dim}",
              run(init_spec.main, ["--out", str(hspec), "--preset", hp,
                                   "--force"]) == 0
              and json.loads(hspec.read_text())["canvas"]
              == {"width": dim, "height": dim})
    # imageify conforms a raster into a 128px hero spec (high-res path)
    herospec = tmp / "hero.spec.json"
    heropix = tmp / "hero.pix"
    check("imageify conforms into a 128px hero spec",
          run(imageify.main, [str(gen), "--spec", str(herospec), "--out",
                              str(heropix), "--dither", "--contain",
                              "--force"]) == 0
          and run(check_sprite.main, [str(heropix), "--spec",
                                      str(herospec)]) == 0
          and len(check_sprite.parse_pix(heropix)) == 128)

    imgpix2 = tmp / "img2.pix"
    run(imageify.main, [str(gen), "--spec", str(spec), "--out", str(imgpix2),
                        "--dither", "--force"])
    check("imageify deterministic (same raster+spec -> same .pix)",
          imgpix.read_text() == imgpix2.read_text())

    # generate_pixel: prompt-only prints a spec-tuned prompt (no network); the
    # file provider conforms an existing raster through the shared pipeline
    check("generate_pixel --prompt-only emits a spec-derived prompt",
          run(generate_pixel.main, ["a wizard frog", "--spec", str(spec),
                                    "--out", str(tmp / "x.pix"),
                                    "--provider", "prompt-only"]) == 0)
    genpix = tmp / "gen.pix"
    check("generate_pixel file provider -> valid in-spec .pix",
          run(generate_pixel.main, ["a blob", "--spec", str(spec), "--out",
                                    str(genpix), "--provider", "file",
                                    "--image", str(gen), "--dither",
                                    "--force"]) == 0
          and run(check_sprite.main, [str(genpix), "--spec", str(spec)]) == 0)

    # character preservation: the guard absorbs only LOW-contrast speckle.
    # On a green field (g #38b764): a stray adjacent-tone G (#a7f070, close)
    # is cleaned, but a 2x2 near-black K "eye" (high contrast) survives the
    # same denoise that previously ate it.
    lr = {c: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
          for c, h in json.loads(spec.read_text())["legend"].items()}
    face = [["g"] * 10 for _ in range(10)]
    face[2][2] = "G"                                    # ramp speckle
    for yy in (6, 7):
        for xx in (6, 7):
            face[yy][xx] = "K"                          # the eye
    imageify.denoise_regions(face, ".", "max", legend_rgb=lr, guard=150)
    check("guarded denoise cleans adjacent-tone speckle", face[2][2] == "g")
    check("guarded denoise keeps a high-contrast eye blob",
          all(face[yy][xx] == "K" for yy in (6, 7) for xx in (6, 7)))
    # simplify color cap: a rare but high-contrast color (catch-light) is kept
    cap = [["b"] * 8 for _ in range(8)]
    cap[3][3] = "W"                                     # rare catch-light
    cap[4][4] = "c"                                     # rare adjacent tone
    imageify.cap_colors(cap, ".", lr, 1, guard=150)
    check("guarded color cap keeps the rare catch-light, merges near tone",
          cap[3][3] == "W" and cap[4][4] == "b")
    # feature re-injection: a small dark pupil on a bright face survives the
    # downscale instead of averaging away into a pale blur
    fimg = Image.new("RGBA", (80, 80), (244, 244, 244, 255))
    for yy in range(40, 46):
        for xx in range(40, 46):
            fimg.putpixel((xx, yy), (26, 28, 44, 255))  # 6px pupil
    bigbase = fimg.resize((8, 8), imageify.BOX)
    kept = imageify._reinject_features(fimg, fimg.resize((8, 8), imageify.BOX))
    def darkest(im):
        return min(sum(im.getpixel((x, y))[:3]) for y in range(8)
                   for x in range(8))
    check("feature re-injection keeps the pupil dark (vs washed-out BOX)",
          darkest(kept) < darkest(bigbase) - 100)

    # analyze_sample --canvas/--background: one-command character-true spec
    dspec2 = tmp / "derived64.spec.json"
    import analyze_sample
    check("analyze_sample --canvas/--background overrides",
          run(analyze_sample.main, [str(gen), "--out", str(dspec2),
                                    "--colors", "15", "--canvas", "64x64",
                                    "--background", "transparent",
                                    "--force"]) == 0
          and json.loads(dspec2.read_text())["canvas"]
          == {"width": 64, "height": 64}
          and json.loads(dspec2.read_text())["background"] == "transparent")
    # --include forces signature colors into the legend within the budget
    dspec3 = tmp / "derived_inc.spec.json"
    check("analyze_sample --include forces a signature color",
          run(analyze_sample.main, [str(gen), "--out", str(dspec3),
                                    "--colors", "12", "--include",
                                    "#ff77a8,#b13e53", "--force"]) == 0
          and "#ff77a8" in json.loads(dspec3.read_text())["legend"].values()
          and "#b13e53" in json.loads(dspec3.read_text())["legend"].values()
          and len(json.loads(dspec3.read_text())["legend"]) <= 12)

    # GBA / FireRed-grade presets: hardware 4bpp = 15 visible colors
    gba = tmp / "gba.spec.json"
    check("gba-battle preset: 64x64, 15-color legend (4bpp)",
          run(init_spec.main, ["--out", str(gba), "--preset", "gba-battle",
                               "--force"]) == 0
          and json.loads(gba.read_text())["canvas"] == {"width": 64, "height": 64}
          and len(json.loads(gba.read_text())["legend"]) == 15)
    gbao = tmp / "gbao.spec.json"
    check("gba-overworld preset: 16x32 (FireRed hero)",
          run(init_spec.main, ["--out", str(gbao), "--preset", "gba-overworld",
                               "--force"]) == 0
          and json.loads(gbao.read_text())["canvas"]
          == {"width": 16, "height": 32})

    # imageify --outline spec: conform finishes with a clean 1px outline
    olpix = tmp / "ol_conform.pix"
    run(imageify.main, [str(gen), "--spec", str(spec), "--out", str(olpix),
                        "--outline", "spec", "--force"])
    olrows = check_sprite.parse_pix(olpix)
    oledge = []
    for yy, row in enumerate(olrows):
        for xx, ch in enumerate(row):
            if ch == ".":
                continue
            if xx == 0 or yy == 0 or xx == len(row) - 1 \
                    or yy == len(olrows) - 1 \
                    or olrows[yy][xx - 1] == "." or olrows[yy][xx + 1] == "." \
                    or olrows[yy - 1][xx] == "." or olrows[yy + 1][xx] == ".":
                oledge.append(ch)
    check("imageify --outline spec closes the silhouette in the outline char",
          oledge and all(c == "K" for c in oledge))

    # generate_pixel prompt carries the spec's style contract (conventions)
    gba_spec = json.loads(gba.read_text())
    gprompt = generate_pixel.build_prompt("a fire lizard", gba_spec)
    check("build_prompt embeds the spec conventions (style contract)",
          "Style contract:" in gprompt and "FireRed" in gprompt)

    # B: consistency report over a set + regen-prompt helper
    check("consistency_report over a set",
          run(consistency_report.main, [str(matout), str(shout), str(flatp),
                                        "--spec", str(spec)]) == 0)
    check("regen_prompt prints steps for a target",
          run(regen_prompt.main, [str(flatp), "--spec", str(spec),
                                  "--target", "80"]) == 0)

    # C: reference similarity (self ~ high), autofix, variants
    selfpng = tmp / "self.png"
    run(render_sprite.main, [str(matout), "--spec", str(spec), "--out",
                             str(selfpng)])
    check("ref_similarity runs (pix vs png)",
          run(ref_similarity.main, [str(matout), str(selfpng), "--spec",
                                    str(spec)]) == 0)
    orphanp = tmp / "orph.pix"
    g = [list(r) for r in check_sprite.parse_pix(shball)]
    g[0][0] = "b"                                   # plant an orphan
    check_sprite.write_pix(["".join(r) for r in g], orphanp)
    fixedp = tmp / "fixed.pix"
    check("autofix removes orphan + re-scores",
          run(autofix.main, [str(orphanp), "--spec", str(spec), "--out",
                             str(fixedp), "--force"]) == 0
          and check_sprite.parse_pix(fixedp)[0][0] == ".")
    vdir = tmp / "variants"
    check("variants reskins into materials",
          run(variants.main, [str(matout), "--spec", str(spec), "--materials",
                              "green,red", "--out-dir", str(vdir),
                              "--force"]) == 0
          and (vdir / (matout.stem + "_green.pix")).exists()
          and run(check_sprite.main, [str(vdir / (matout.stem + "_red.pix")),
                                      "--spec", str(spec)]) == 0)

    # D: bevel/cone shading forms + hue-shift ramp + animation score
    bev = tmp / "bevel.pix"
    check("shade_form bevel form",
          run(shade_form.main, [str(shball), "--spec", str(spec), "--region",
                               "b", "--material", "blue", "--form", "bevel",
                               "--out", str(bev), "--force"]) == 0
          and run(check_sprite.main, [str(bev), "--spec", str(spec)]) == 0)
    check("palette_tool --hue-shift ramp",
          run(palette_tool.main, ["--ramp", "3b5dc9", "--steps", "5",
                                  "--hue-shift"]) == 0)
    check("anim_score over frames",
          run(anim_score.main, [str(f0), str(f1), str(f2), "--spec",
                                str(spec)]) == 0)

    # Frame/proportions: off-center asset flags, --fit recenters + baselines
    check("spec has a frame block",
          "frame" in specd and "baseline" in specd["frame"])
    off = tmp / "off.pix"
    run(draw_pix.main, ["--spec", str(spec), "--out", str(off),
                        "--circle", "8,8,5,b,fill", "--force"])
    check("proportions flags off-center (strict)",
          run(proportions.main, [str(off), "--spec", str(spec),
                                 "--strict"]) == 1)
    fitp = tmp / "fit.pix"
    run(proportions.main, [str(off), "--spec", str(spec), "--fit", "--out",
                           str(fitp), "--force"])
    fr = specd["frame"]
    m0 = proportions.measure(check_sprite.parse_pix(off), specd)
    m1 = proportions.measure(check_sprite.parse_pix(fitp), specd)
    check("--fit moves content toward the center axis",
          abs(m1["center_x"] - fr["center_axis"])
          <= abs(m0["center_x"] - fr["center_axis"]))
    check("--fit drops content onto the baseline",
          abs(m1["bottom"] - fr["baseline"])
          <= abs(m0["bottom"] - fr["baseline"]) + 0.01)
    gpng = tmp / "guide.png"
    check("frame_guide renders an overlay",
          run(frame_guide.main, ["--spec", str(spec), "--on", str(fitp),
                                 "--out", str(gpng), "--force"]) == 0
          and gpng.exists())

    # fine-tune: pivot anchoring, frame registration, gate, outline auto-add
    check("autofix --outline adds an edge",
          run(autofix.main, [str(shball), "--spec", str(spec), "--out",
                             str(tmp / "ol.pix"), "--outline", "K",
                             "--force"]) == 0
          and any("K" in r for r in check_sprite.parse_pix(tmp / "ol.pix")))
    check("animate --register stays grounded",
          run(animate.main, ["--spec", str(spec), "--frames", str(f0), str(f1),
                             str(f2), "--out", str(tmp / "reg"), "--format",
                             "sheet", "--register"]) == 0)
    check("consistency_report --strict gate (min 0 passes)",
          run(consistency_report.main, [str(matout), str(shout), "--spec",
                                        str(spec), "--strict", "--min",
                                        "0"]) == 0)
    pivot_scene = tmp / "pv.json"
    pivot_scene.write_text(json.dumps({
        "canvas": [200, 200], "background": "transparent",
        "layers": [{"pix": str(matout).replace("\\", "/"),
                    "spec": str(spec).replace("\\", "/"),
                    "at": [100, 180], "anchor": "pivot"}]}), encoding="utf-8")
    check("compose_scene pivot anchoring",
          run(compose_scene.main, [str(pivot_scene), "--out",
                                   str(tmp / "pv.png"), "--force"]) == 0
          and Image.open(tmp / "pv.png").size == (200, 200))

    # spec fingerprint + drift detection + full-project verify gate
    check("spec carries a spec_id fingerprint",
          "spec_id" in specd and len(specd["spec_id"]) >= 6)
    check("style_lock stamps then --check matches",
          run(style_lock.main, [str(matout), str(shout), "--spec",
                                str(spec)]) == 0
          and run(style_lock.main, [str(matout), str(shout), "--spec",
                                    str(spec), "--check"]) == 0)
    spec2 = tmp / "spec2.json"
    d2 = json.loads(spec.read_text())
    d2["scale"] = d2["scale"] + 1
    d2["spec_id"] = check_sprite.spec_id(d2)
    spec2.write_text(json.dumps(d2), encoding="utf-8")
    check("style_lock --check detects drift after spec change",
          run(style_lock.main, [str(matout), "--spec", str(spec2),
                                "--check"]) == 1)
    check("verify runs the full battery over a set",
          run(verify.main, [str(matout), str(shout), "--spec", str(spec)]) == 0)
    check("verify --strict gates on detail threshold",
          run(verify.main, [str(flatp), "--spec", str(spec), "--strict",
                            "--min-detail", "90"]) == 1)

    # autotile: a fill mask -> seamless terrain with uniform auto-borders
    mask = tmp / "mask.txt"
    mask.write_text("##\n###\n.##\n", encoding="utf-8")
    terr = tmp / "terrain.png"
    check("autotile renders a terrain map from a mask",
          run(autotile.main, [str(mask), "--spec", str(spec), "--material",
                              "green", "--out", str(terr), "--force"]) == 0
          and terr.exists())

    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
