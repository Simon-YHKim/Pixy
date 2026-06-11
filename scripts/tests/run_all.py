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
import craft_score, charset, animate_fx  # noqa: E402
import pixyfly, frames_to_pixel  # noqa: E402
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

    # retro craft: ordered (Bayer) dither weaves a regular checker between
    # tones - assert an ABAB alternation appears in the transition zone
    gradpng = tmp / "grad.png"
    gimg3 = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    for yy in range(8, 120):
        for xx in range(8, 120):
            v = int(20 + 220 * (xx - 8) / 112)
            gimg3.putpixel((xx, yy), (v, v, v, 255))
    gimg3.save(gradpng)
    odpix = tmp / "od.pix"
    run(imageify.main, [str(gradpng), "--spec", str(spec), "--out", str(odpix),
                        "--dither", "--dither-mode", "ordered", "--contain",
                        "--denoise", "none", "--no-clean", "--force"])
    odrows = check_sprite.parse_pix(odpix)
    def has_weave(rows):
        for row in rows:
            for i in range(len(row) - 3):
                a, b = row[i], row[i + 1]
                if a != b and a != "." and b != "." \
                        and row[i + 2] == a and row[i + 3] == b:
                    return True
        return False
    check("ordered dither produces the retro checker weave", has_weave(odrows))

    # sel-out outline: lit (top-left) edges keep a darker self-color, only
    # shadow-side edges take the hard outline char
    discpng = tmp / "disc.png"
    dimg = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    for yy in range(96):
        for xx in range(96):
            if (xx - 48) ** 2 + (yy - 48) ** 2 <= 40 * 40:
                dimg.putpixel((xx, yy), (65, 166, 246, 255))   # 'c'
    dimg.save(discpng)
    selpix = tmp / "sel.pix"
    run(imageify.main, [str(discpng), "--spec", str(spec), "--out",
                        str(selpix), "--outline", "spec", "--outline-mode",
                        "selout", "--denoise", "none", "--force"])
    srows = check_sprite.parse_pix(selpix)
    sh2 = len(srows)
    def first_solid_in_col(xx):
        for yy in range(sh2):
            if srows[yy][xx] != ".":
                return srows[yy][xx]
    def last_solid_in_col(xx):
        for yy in range(sh2 - 1, -1, -1):
            if srows[yy][xx] != ".":
                return srows[yy][xx]
    mid = len(srows[0]) // 2
    check("sel-out: lit (top) edge is NOT the hard outline char",
          first_solid_in_col(mid) != "K")
    check("sel-out: shadow (bottom) edge IS the hard outline char",
          last_solid_in_col(mid) == "K")

    # jaggy lint: a 1px wobble on a flat edge is flagged; the clean edge and
    # a smooth staircase are not
    jag = [["."] * 12 for _ in range(12)]
    for yy in range(2, 10):
        for xx in range(4, 10):
            jag[yy][xx] = "g"
    jag[5][3] = "g"                                      # 1px bump on left
    jrows = ["".join(r) for r in jag]
    jfound = lint_pix.find_jaggies(jrows, ".")
    check("lint flags a 1px contour bump as a jaggy",
          any(n == "left" and k == "bump" for n, _i, k in jfound))
    clean_rows = ["".join(r) for r in
                  [["."] * 12 for _ in range(2)]
                  + [["." if xx < 4 or xx >= 10 else "g" for xx in range(12)]
                     for _ in range(8)]
                  + [["."] * 12 for _ in range(2)]]
    check("lint passes a clean flat edge (no jaggies)",
          not lint_pix.find_jaggies(clean_rows, "."))
    # autofix --smooth repairs the wobble (32x32 grid to match the spec)
    jag32 = [["."] * 32 for _ in range(32)]
    for yy in range(8, 24):
        for xx in range(10, 22):
            jag32[yy][xx] = "g"
    jag32[14][9] = "g"                                  # bump on the left
    jag32[18][10] = "."                                 # dent on the left
    jpix = tmp / "jag.pix"
    check_sprite.write_pix(["".join(r) for r in jag32], jpix)
    jfix = tmp / "jag_fixed.pix"
    check("autofix --smooth shaves the bump and fills the dent",
          run(autofix.main, [str(jpix), "--spec", str(spec), "--out",
                             str(jfix), "--smooth", "--force"]) == 0
          and not lint_pix.find_jaggies(check_sprite.parse_pix(jfix), "."))

    # outline banding: a double-thick outline wall is flagged; 1px is not
    band = [["."] * 12 for _ in range(12)]
    for yy in range(2, 10):
        band[yy][3] = "K"
        band[yy][4] = "K"                               # double-thick
        for xx in range(5, 9):
            band[yy][xx] = "g"
        band[yy][9] = "K"                               # 1px far side
    bhits = lint_pix.find_outline_banding(["".join(r) for r in band], ".", "K")
    check("lint flags double-thick outline banding", len(bhits) >= 3)
    thin = [["."] * 12 for _ in range(12)]
    for yy in range(2, 10):
        thin[yy][3] = "K"
        for xx in range(4, 9):
            thin[yy][xx] = "g"
        thin[yy][9] = "K"
    check("lint passes a selective 1px outline (no banding)",
          not lint_pix.find_outline_banding(["".join(r) for r in thin],
                                            ".", "K"))

    # derived specs get hue-family ramps + optional retro hue-shift
    rampsrc = tmp / "ramp.png"
    rimg = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    greens = [(20, 60, 25), (40, 110, 50), (90, 170, 95), (160, 220, 160)]
    for i, col in enumerate(greens):
        for yy in range(8, 56):
            for xx in range(8 + i * 12, 8 + (i + 1) * 12):
                rimg.putpixel((xx, yy), col + (255,))
    rimg.save(rampsrc)
    rspec1 = tmp / "ramp1.spec.json"
    run(analyze_sample.main, [str(rampsrc), "--out", str(rspec1), "--colors",
                              "4", "--force"])
    d1 = json.loads(rspec1.read_text())
    check("derived spec has shading.materials with a green ramp",
          "shading" in d1 and "green" in d1["shading"]["materials"]
          and len(d1["shading"]["materials"]["green"]) >= 3)
    rspec2 = tmp / "ramp2.spec.json"
    run(analyze_sample.main, [str(rampsrc), "--out", str(rspec2), "--colors",
                              "4", "--hue-shift", "--force"])
    d2 = json.loads(rspec2.read_text())
    import colorsys as _cs
    def hue_of(hexv):
        r, g, b = (int(hexv[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        return _cs.rgb_to_hsv(r, g, b)[0] * 360
    dark1 = d1["shading"]["materials"]["green"][0]
    dark2 = d2["shading"]["materials"]["green"][0]
    check("--hue-shift bends the shadow end toward cool (blue)",
          hue_of(d2["legend"][dark2]) > hue_of(d1["legend"][dark1]))

    # NES preset: curated 2C02 gamut, 16x16, 3-colors-per-sprite rule in note
    nes = tmp / "nes.spec.json"
    check("nes preset: 16x16, curated 2C02 gamut (28 colors)",
          run(init_spec.main, ["--out", str(nes), "--preset", "nes",
                               "--force"]) == 0
          and json.loads(nes.read_text())["canvas"]
          == {"width": 16, "height": 16}
          and len(json.loads(nes.read_text())["legend"]) == 28)

    # keying guard: a solid edge-to-edge opaque image must NOT be erased to
    # nothing (the flood-key reverts when it would eat >=92% of the canvas)
    solidpng = tmp / "solid.png"
    Image.new("RGB", (40, 40), (56, 183, 100)).save(solidpng)
    solidgrid = imageify.conform(
        Image.open(solidpng), json.loads(spec.read_text()),
        dither=False, bg_tol=42.0, resample="box", crop=True, contain=True,
        clean=True)
    check("keying guard: solid image survives (not erased to empty)",
          sum(1 for r in solidgrid for c in r if c != ".") > 0)

    # lint outline check is silenced for selective/sel-out outlines (sparse
    # outline) but still flags a stray interior outline dot on a hard outline
    selo = [["."] * 16 for _ in range(16)]
    for yy in range(3, 13):                              # a filled disc-ish
        for xx in range(3, 13):
            selo[yy][xx] = "g"
    selo[3][7] = "K"                                     # one lone edge outline
    sel_rows = ["".join(r) for r in selo]
    check("lint: lone outline pixel on a sparse outline is NOT flagged",
          not any("isolated outline" in f
                  for f in lint_pix.lint(sel_rows, json.loads(spec.read_text()))))
    hard = [["."] * 16 for _ in range(16)]
    for xx in range(3, 13):
        hard[3][xx] = hard[12][xx] = "K"
    for yy in range(3, 13):
        hard[yy][3] = hard[yy][12] = "K"
    for yy in range(4, 12):
        for xx in range(4, 12):
            hard[yy][xx] = "g"
    hard[8][8] = "K"                                     # stray interior dot
    hard_rows = ["".join(r) for r in hard]
    check("lint: stray interior outline dot on a hard outline IS flagged",
          any("isolated outline" in f
              for f in lint_pix.lint(hard_rows, json.loads(spec.read_text()))))

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

    # ---- gaps 1-4 + animation deep-dive (v0.24) ----
    specd2 = json.loads(spec.read_text())

    # gap 4: light-direction lint - tl-lit sphere passes, br-lit is flagged
    lt = tmp / "lt.pix"
    lb = tmp / "lb.pix"
    run(draw_pix.main, ["--spec", str(spec), "--out", str(tmp / "lbase.pix"),
                        "--circle", "16,16,12,b,fill", "--force"])
    run(shade_form.main, [str(tmp / "lbase.pix"), "--spec", str(spec),
                          "--region", "b", "--material", "blue", "--form",
                          "sphere", "--light", "tl", "--out", str(lt),
                          "--force"])
    run(shade_form.main, [str(tmp / "lbase.pix"), "--spec", str(spec),
                          "--region", "b", "--material", "blue", "--form",
                          "sphere", "--light", "br", "--out", str(lb),
                          "--force"])
    check("light lint: correctly-lit asset passes",
          not any("light direction" in f for f in
                  lint_pix.lint(check_sprite.parse_pix(lt), specd2)))
    check("light lint: opposite-lit asset is flagged",
          any("light direction" in f for f in
              lint_pix.lint(check_sprite.parse_pix(lb), specd2)))

    # gap 3: craft_score discriminates disciplined vs machine-y output
    crows_clean = check_sprite.parse_pix(lt)
    noisy = [list(r) for r in crows_clean]
    flips = 0
    for yy in range(len(noisy)):
        for xx in range(len(noisy[0])):
            if noisy[yy][xx] == "b" and (xx * 7 + yy * 13) % 5 == 0:
                noisy[yy][xx] = "c"                  # adjacent-tone speckle
                flips += 1
    c_clean = craft_score.score(crows_clean, specd2)["overall"]
    c_noisy = craft_score.score(["".join(r) for r in noisy], specd2)["overall"]
    check("craft_score: clean asset outscores speckled asset",
          flips > 10 and c_clean > c_noisy)
    check("craft_score main runs + brief emits regeneration constraints",
          run(craft_score.main, [str(lt), "--spec", str(spec)]) == 0
          and run(craft_score.main, [str(lt), "--spec", str(spec),
                                     "--brief"]) == 0)
    check("verify --min-craft gates",
          run(verify.main, [str(lt), "--spec", str(spec), "--strict",
                            "--min-craft", "101"]) == 1
          and run(verify.main, [str(lt), "--spec", str(spec), "--strict",
                                "--min-craft", "1"]) == 0)

    # gap 2: providers - hf fails gracefully without a token; command
    # provider substitutes {ref_png} (img2img hook)
    import os as _os
    _os.environ.pop("HF_TOKEN", None)
    _os.environ.pop("HUGGINGFACE_TOKEN", None)
    check("generate_pixel --provider hf without token fails gracefully",
          run(generate_pixel.main, ["x", "--spec", str(spec), "--out",
                                    str(tmp / "hf.pix"), "--provider", "hf",
                                    "--force"]) == 2)
    refpix = tmp / "refgen.pix"
    check("generate_pixel command provider substitutes {ref_png}",
          run(generate_pixel.main, ["a blob", "--spec", str(spec), "--out",
                                    str(refpix), "--provider", "command",
                                    "--ref", str(gen), "--cmd",
                                    "cp {ref_png} {out_png}", "--force"]) == 0
          and run(check_sprite.main, [str(refpix), "--spec", str(spec)]) == 0)

    # gap 1: charset - conform a 3-pose set from existing images + gates
    rawdir = tmp / "rawset"
    rawdir.mkdir()
    for i, pose in enumerate(["front", "left", "walk_0"]):
        pimg = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        for yy in range(20, 100):
            for xx in range(20 + i, 100 + i):
                pimg.putpixel((xx, yy), (56, 183, 100, 255))
        for yy in range(40, 46):
            for xx in range(44, 50):
                pimg.putpixel((xx + i, yy), (26, 28, 44, 255))
        pimg.save(rawdir / f"{pose}.png")
    setdir = tmp / "set"
    check("charset conforms a pose set from --images-dir and gates pass",
          run(charset.main, ["--spec", str(spec), "--character", "a blob",
                             "--poses", "front,left,walk_0", "--out-dir",
                             str(setdir), "--images-dir", str(rawdir),
                             "--contain", "--strict", "--min-uniformity",
                             "50"]) == 0
          and (setdir / "front.pix").exists()
          and (setdir / "walk_0.pix").exists())
    check("charset prompt-only emits per-pose prompts",
          run(charset.main, ["--spec", str(spec), "--character", "a blob",
                             "--poses", "front,walk_0,walk_1", "--out-dir",
                             str(tmp / "set2")]) == 0)

    # style sets: different subjects, one locked template (the field-failure
    # mode: a 6-icon set where the model reinvented the shared cube per cell)
    check("charset --subjects emits one prompt per subject (';' separated)",
          run(charset.main, ["--spec", str(spec), "--subjects",
                             "a plant, small;a heart;an open book",
                             "--template", "inside a wireframe cube",
                             "--out-dir", str(tmp / "ss")]) == 0)
    # 8-way directional set with NO 3D tools: compass poses -> facing prompts
    import contextlib as _ctx, io as _io
    _buf = _io.StringIO()
    with _ctx.redirect_stdout(_buf):
        charset.main(["--spec", str(spec), "--character", "a slime",
                      "--poses", "s,e,n,w", "--out-dir", str(tmp / "dirs")])
    dtext = _buf.getvalue()
    check("charset directional poses produce per-facing prompts (no 3D)",
          "facing" in dtext and dtext.count("## ") == 4
          and "north" in dtext and "east" in dtext)
    # direction x motion combo: s_0 keeps BOTH facing and frame semantics
    combo = charset.pose_phrase("s_0", ["s_0", "s_1", "e_0", "e_1"])
    check("charset s_0 combo = facing south + walking frame 1 of 2",
          "south" in combo and "frame 1 of 2" in combo)

    # Track 2: blender_snippet emits valid, parameterized Blender Python
    import blender_snippet
    snip = tmp / "snip.py"
    check("blender_snippet blockout emits compilable, parameterized code",
          run(blender_snippet.main,
              ["--mode", "blockout", "--out-dir", "//raw", "--parts",
               "sphere,body,0 0 0.5,0.5,#2b52c0;cube,base,0 0 0,0.8,#12143b",
               "--directions", "s,e,n,w", "--frames", "2", "--res", "256",
               "--out", str(snip)]) == 0
          and compile(snip.read_text(), "s", "exec") is not None
          and "'body'" in snip.read_text()                # parts embedded
          and "'#2b52c0'" in snip.read_text()             # flat color
          and "PIXY_RENDER_DONE" in snip.read_text()
          and "['s', 'e', 'n', 'w']" in snip.read_text())
    snip2 = tmp / "snip2.py"
    check("blender_snippet render mode + bad parts rejected",
          run(blender_snippet.main,
              ["--mode", "render", "--frames", "6", "--anim-step", "10",
               "--out", str(snip2)]) == 0
          and "FRAMES = 6" in snip2.read_text()
          and run(blender_snippet.main,
                  ["--mode", "blockout", "--parts", "torus,x,0 0 0,1",
                   "--out", str(tmp / "bad.py")]) == 2)
    check("charset rejects --poses together with --subjects (and neither)",
          run(charset.main, ["--spec", str(spec), "--poses", "front",
                             "--subjects", "a heart", "--out-dir",
                             str(tmp / "ss2")]) == 2
          and run(charset.main, ["--spec", str(spec), "--out-dir",
                                 str(tmp / "ss3")]) == 2)
    # derived specs carry REAL conventions (not a DRAFT disclaimer that
    # would leak into generation prompts); the warning moved to review_note
    dD = json.loads(dspec2.read_text())
    check("derived spec conventions are prompt-usable (DRAFT in review_note)",
          "DRAFT" not in dD.get("conventions", "DRAFT")
          and "DRAFT" in dD.get("review_note", ""))

    # animation deep-dive: animate_fx cycles from one base sprite
    fxout = tmp / "fx"
    check("animate_fx hover writes N valid moving frames + gif",
          run(animate_fx.main, [str(lt), "--spec", str(spec), "--fx", "hover",
                                "--frames", "4", "--amp", "2", "--out",
                                str(fxout), "--gif", str(tmp / "fx.gif"),
                                "--fps", "8", "--force"]) == 0
          and (tmp / "fx.gif").exists()
          and check_sprite.parse_pix(Path(f"{fxout}_1.pix"))
          != check_sprite.parse_pix(Path(f"{fxout}_0.pix")))
    facegrid = [["."] * 32 for _ in range(32)]
    for yy in range(6, 26):
        for xx in range(8, 24):
            facegrid[yy][xx] = "g"
    for ex in (12, 19):                                  # two 2x2 'K' eyes
        for dy in (0, 1):
            for dx in (0, 1):
                facegrid[10 + dy][ex + dx] = "K"
    facepix = tmp / "face.pix"
    check_sprite.write_pix(["".join(r) for r in facegrid], facepix)
    blout = tmp / "bl"
    run(animate_fx.main, [str(facepix), "--spec", str(spec), "--fx", "blink",
                          "--frames", "6", "--eye-char", "K", "--out",
                          str(blout), "--force"])
    blink_counts = []
    for i in range(6):
        fp = Path(f"{blout}_{i}.pix")
        if fp.exists():
            blink_counts.append(sum(r.count("K")
                                    for r in check_sprite.parse_pix(fp)))
    check("animate_fx blink closes the eyes on exactly one frame",
          len(blink_counts) == 6
          and sum(1 for c in blink_counts if c < max(blink_counts)) == 1)
    flout = tmp / "fl"
    run(animate_fx.main, [str(lt), "--spec", str(spec), "--fx", "flash",
                          "--frames", "3", "--out", str(flout), "--force"])
    f0 = check_sprite.parse_pix(Path(f"{flout}_0.pix"))
    f0used = {c for r in f0 for c in r if c != "."}
    check("animate_fx flash frame 0 is a single bright silhouette",
          len(f0used) == 1)
    check("anim_score --loop runs over an fx cycle",
          run(anim_score.main, [f"{fxout}_0.pix", f"{fxout}_1.pix",
                                f"{fxout}_2.pix", f"{fxout}_3.pix", "--spec",
                                str(spec), "--loop"]) == 0)

    # pixyfly: one command image -> spec -> conform -> render -> gate -> gif
    flysrc = tmp / "flysrc.png"
    fimg = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    import math as _m2
    for yy in range(160):
        for xx in range(160):
            d = _m2.hypot(xx - 80, yy - 80)
            if d < 56:
                lv = max(0.0, min(1.0, 0.5 + 0.5 * ((80 - xx) + (80 - yy)) / 80))
                fimg.putpixel((xx, yy), (int(30 + 40 * lv), int(120 + 130 * lv),
                                         int(60 + 60 * lv), 255))
    for ex in (66, 94):                                  # eyes
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                if dx * dx + dy * dy <= 12:
                    fimg.putpixel((ex + dx, 74 + dy), (20, 22, 40, 255))
    fimg.save(flysrc)
    flydir = tmp / "fly"
    rc = run(pixyfly.main, [str(flysrc), "--name", "blob", "--out-dir",
                            str(flydir), "--colors", "15", "--canvas",
                            "48x48", "--denoise", "med", "--outline", "spec",
                            "--fx", "hover", "--frames", "4", "--gif",
                            "--force"])
    check("pixyfly one command produces spec+pix+png",
          rc == 0 and (flydir / "blob.spec.json").exists()
          and (flydir / "blob.pix").exists()
          and (flydir / "blob.png").exists())
    check("pixyfly conformed asset is valid in its derived spec",
          run(check_sprite.main, [str(flydir / "blob.pix"), "--spec",
                                  str(flydir / "blob.spec.json")]) == 0)
    check("pixyfly produced the animation cycle + gif",
          (flydir / "blob_hover.gif").exists()
          and (flydir / "blob_hover_0.pix").exists())
    check("pixyfly --strict gates on --min-craft",
          run(pixyfly.main, [str(flysrc), "--name", "b2", "--out-dir",
                             str(tmp / "fly2"), "--colors", "15", "--canvas",
                             "48x48", "--strict", "--min-craft", "101"]) == 1
          and run(pixyfly.main, [str(flysrc), "--name", "b3", "--out-dir",
                                 str(tmp / "fly3"), "--colors", "15",
                                 "--canvas", "48x48", "--strict",
                                 "--min-craft", "1"]) == 0)

    # ---- v0.26: finish line, tileable, golden corpus, fuzz, perf ----

    # charset --animate: walk_0..walk_2 -> gif + sheet + aseprite export
    setdir3 = tmp / "set3"
    rawdir2 = tmp / "rawwalk"
    rawdir2.mkdir(exist_ok=True)
    for i in range(3):
        pimg = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        for yy in range(30, 100):
            for xx in range(30 + i * 2, 90 + i * 2):
                pimg.putpixel((xx, yy), (56, 183, 100, 255))
        pimg.save(rawdir2 / f"walk_{i}.png")
    check("charset --animate finishes to gif+sheet+aseprite export",
          run(charset.main, ["--spec", str(spec), "--character", "a blob",
                             "--poses", "walk_0,walk_1,walk_2", "--out-dir",
                             str(setdir3), "--images-dir", str(rawdir2),
                             "--contain", "--animate", "walk", "--fps", "8",
                             "--export", "aseprite"]) == 0
          and (setdir3 / "walk.gif").exists()
          and (setdir3 / "walk_sheet.png").exists()
          and (setdir3 / "walk.json").exists())

    # imageify --tileable: a noisy-edged tile becomes wrap-seamless
    tsrc = tmp / "tilesrc.png"
    timg2 = Image.new("RGB", (64, 64), (56, 183, 100))
    for yy in range(64):                                  # mismatched edges
        if yy % 3 == 0:
            timg2.putpixel((63, yy), (38, 92, 66))
            timg2.putpixel((0, yy), (96, 220, 140))
    timg2.save(tsrc)
    tilespec = tmp / "tile.spec.json"
    run(init_spec.main, ["--out", str(tilespec), "--preset", "tileset",
                         "--force"])
    import json as _json
    td = _json.loads(tilespec.read_text())
    td["background"] = "#1a1c2c"
    tilespec.write_text(_json.dumps(td))
    tpix = tmp / "tile_conform.pix"
    check("imageify --tileable produces a wrap-clean tile",
          run(imageify.main, [str(tsrc), "--spec", str(tilespec), "--out",
                              str(tpix), "--no-crop", "--tileable",
                              "--denoise", "none", "--force"]) == 0
          and all(r[0] == r[-1]
                  for r in check_sprite.parse_pix(tpix)))

    # quality golden corpus: a deterministic shaded-blob conform must match
    # the committed golden .pix exactly - catches silent quality regressions
    # in BOX/feature-reinjection/denoise/quantize tuning
    import math as _m3
    gsrc = tmp / "golden_src.png"
    gimg4 = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    for yy in range(96):
        for xx in range(96):
            d = _m3.hypot(xx - 48, yy - 48)
            if d < 34:
                lv = max(0.0, min(1.0, 0.5 + 0.5 * ((48 - xx) + (48 - yy)) / 48))
                gimg4.putpixel((xx, yy), (int(26 + 33 * lv), int(60 + 123 * lv),
                                          int(150 + 96 * lv), 255))
    for ex in (40, 56):
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if dx * dx + dy * dy <= 5:
                    gimg4.putpixel((ex + dx, 44 + dy), (26, 28, 44, 255))
    gimg4.save(gsrc)
    gpix = tmp / "golden_out.pix"
    run(imageify.main, [str(gsrc), "--spec", str(spec), "--out", str(gpix),
                        "--denoise", "med", "--force"])
    golden_file = Path(__file__).parent / "golden" / "shaded_blob.pix"
    if not golden_file.exists():                          # first run: record
        golden_file.parent.mkdir(exist_ok=True)
        golden_file.write_text(gpix.read_text(), encoding="utf-8")
    check("quality golden: conform output matches the committed corpus",
          check_sprite.parse_pix(gpix)
          == check_sprite.parse_pix(golden_file))

    # fuzz/property: seeded random images x specs -> conform must always
    # yield a valid grid or a clean nonzero exit (never crash), and the
    # result must render
    import random as _rnd
    rng = _rnd.Random(42)
    fuzz_ok = True
    for trial in range(8):
        fw = rng.choice((1, 7, 33, 64, 200))
        fh = rng.choice((1, 9, 33, 64))
        fimg2 = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        for _ in range(min(fw * fh, 120)):
            fimg2.putpixel((rng.randrange(fw), rng.randrange(fh)),
                           (rng.randrange(256), rng.randrange(256),
                            rng.randrange(256), rng.choice((0, 255))))
        fsrc = tmp / f"fuzz{trial}.png"
        fimg2.save(fsrc)
        fpix = tmp / f"fuzz{trial}.pix"
        fspec = rng.choice((spec, gb, tilespec))
        try:
            rc = run(imageify.main, [str(fsrc), "--spec", str(fspec), "--out",
                                     str(fpix), "--denoise",
                                     rng.choice(("none", "med", "max")),
                                     "--contain", "--force"])
        except Exception:
            fuzz_ok = False
            break
        if rc == 0:
            if run(check_sprite.main, [str(fpix), "--spec", str(fspec)]) != 0:
                fuzz_ok = False
                break
            if run(render_sprite.main, [str(fpix), "--spec", str(fspec),
                                        "--out", str(tmp / "fz.png")]) != 0:
                fuzz_ok = False
                break
        elif rc != 2:
            fuzz_ok = False
            break
    check("fuzz: 8 random image/spec combos -> valid grid or clean error",
          fuzz_ok)

    # perf guard: a 512px ordered-dither conform stays under 12s (memoized)
    import time as _time
    big = tmp / "big.png"
    bimg = Image.new("RGBA", (700, 700), (0, 0, 0, 0))
    for yy in range(40, 660):
        for xx in range(40, 660):
            bimg.putpixel((xx, yy), (xx % 256, yy % 256, (xx + yy) % 256, 255))
    bimg.save(big)
    bspec = tmp / "big.spec.json"
    run(init_spec.main, ["--out", str(bspec), "--preset", "poster", "--force"])
    t0 = _time.time()
    rc = run(imageify.main, [str(big), "--spec", str(bspec), "--out",
                             str(tmp / "big.pix"), "--dither", "--contain",
                             "--denoise", "none", "--force"])
    dt = _time.time() - t0
    check(f"perf: 512px ordered-dither conform under 12s ({dt:.1f}s)",
          rc == 0 and dt < 12)

    # calibrator emits the init_spec wiring
    cal2 = tmp / "cal2.html"
    run(detail_calibrator.main, ["--out", str(cal2), "--force"])
    check("calibrator wires sliders to an init_spec command",
          "init_spec.py" in cal2.read_text(encoding="utf-8"))

    # frames_to_pixel: a rendered 3D frame sequence (2 dirs x 3 frames) ->
    # conformed in-spec frames + a directions x frames sheet + gate
    r3d = tmp / "r3d"
    r3d.mkdir()
    import math as _m4
    for d in ("s", "e"):
        for f in range(3):
            im3 = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            cx = 48 + (f - 1) * 4
            for yy in range(96):
                for xx in range(96):
                    if _m4.hypot(xx - cx, yy - 48) < 30:
                        lv = max(0.0, min(1.0, 0.5 + 0.5 * ((cx - xx)
                                 + (48 - yy)) / 42))
                        im3.putpixel((xx, yy), (int(30 + 60 * lv),
                                     int(90 + 120 * lv), int(150 + 90 * lv),
                                     255))
            im3.save(r3d / f"{d}_{f}.png")
    r3dspec = tmp / "r3d.spec.json"
    run(analyze_sample.main, [str(r3d / "s_1.png"), "--out", str(r3dspec),
                              "--colors", "15", "--canvas", "48x48",
                              "--background", "transparent", "--force"])
    r3dout = tmp / "r3d_out"
    check("frames_to_pixel conforms a 3D sequence to a directional sheet",
          run(frames_to_pixel.main, [str(r3d), "--spec", str(r3dspec),
                                     "--out-dir", str(r3dout), "--directions",
                                     "s,e", "--frames", "3", "--denoise",
                                     "med", "--min-uniformity", "50"]) == 0
          and (r3dout / "sheet_sheet.png").exists()
          and (r3dout / "sheet_sheet.json").exists()
          and (r3dout / "s_0.pix").exists()
          and run(check_sprite.main, [str(r3dout / "s_0.pix"), "--spec",
                                      str(r3dspec)]) == 0)
    check("frames_to_pixel sheet is directions x frames (2 rows x 3 cols)",
          json.loads((r3dout / "sheet_sheet.json").read_text())["count"] == 6)
    # add a 4th frame to 's' only, so 's' is complete but 'e' misses e_3:
    # the sheet assembles from 's', and --strict fails on the missing frame
    (r3d / "s_3.png").write_bytes((r3d / "s_2.png").read_bytes())
    check("frames_to_pixel --strict fails on a missing frame",
          run(frames_to_pixel.main, [str(r3d), "--spec", str(r3dspec),
                                     "--out-dir", str(tmp / "r3d_x"),
                                     "--directions", "s,e", "--frames", "4",
                                     "--strict", "--min-uniformity", "0"]) == 1)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
