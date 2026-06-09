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
import animate, export_engine, batch, shade_form  # noqa: E402
import text_pix, nine_slice, tilemap, compose_scene  # noqa: E402
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

    # trace --derive: reproduce a render with an auto-matched palette + spec
    derived, dspec = tmp / "derived.pix", tmp / "derived.spec.json"
    check("trace --derive builds spec + faithful pix",
          run(trace_image.main, [str(png1), "--derive", "6", "--out-spec",
                                 str(dspec), "--out", str(derived),
                                 "--force"]) == 0
          and dspec.exists()
          and run(check_sprite.main, [str(derived), "--spec",
                                      str(dspec)]) == 0)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
