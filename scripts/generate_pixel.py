#!/usr/bin/env python3
"""Generate a pixel-art asset from a text prompt via an image model, then
conform it into the locked spec.

Usage:
    # 1) host agent has its own image tool (Claude tool / GPT image / Gemini):
    generate_pixel.py "a wizard frog with a staff" --spec pixy.spec.json \
        --out frog.pix --prompt-only
    #   -> prints a tuned pixel-art prompt; run it in your image tool, save the
    #      PNG, then: imageify.py that.png --spec pixy.spec.json --out frog.pix

    # 2) call a provider directly (needs an API key in the environment):
    generate_pixel.py "a wizard frog" --spec pixy.spec.json --out frog.pix \
        --provider openai --dither

    # 3) any local model / ComfyUI / SD via a command template:
    generate_pixel.py "a wizard frog" --spec pixy.spec.json --out frog.pix \
        --provider command --cmd 'sd --prompt {prompt} --out {out_png}'

This is the *front* half of the image-first path. Pixel-art quality that
rivals a reference image comes from an image model, not from an LLM typing an
ASCII grid by hand. The hard part - keeping every asset on ONE locked palette,
canvas size, and cut-out - is done deterministically afterward by imageify.py,
so the consistency contract still holds: the model supplies the picture, the
spec supplies the constraints.

The prompt is built from the spec so the model is steered toward the project's
look: native resolution, the exact palette hexes, and the transparency rule.

Providers:
    prompt-only  print the tuned prompt and stop (default if no key/--cmd)
    openai       OpenAI Images API (env OPENAI_API_KEY)
    command      run any shell command; {prompt}/{out_png} are substituted
    file         use an already-generated raster (--image) and just conform it

Exit codes: 0 = ok, 2 = usage/IO error, 3 = Pillow/provider unavailable.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec  # noqa: E402


def build_prompt(user_prompt: str, spec: dict) -> str:
    """Compose an image-model prompt that steers toward the locked style."""
    w = int(spec["canvas"]["width"])
    h = int(spec["canvas"]["height"])
    legend = spec.get("legend", {})
    hexes = ", ".join(legend.values())
    transparent = spec.get("background", "transparent") == "transparent"
    light = spec.get("shading", {}).get("light", "tl")
    light_word = {"tl": "top-left", "tr": "top-right", "bl": "bottom-left",
                  "br": "bottom-right", "t": "top", "b": "bottom",
                  "l": "left", "r": "right"}.get(light, "top-left")
    bg = ("a flat solid pure black (#000000) background for easy cut-out"
          if transparent else
          f"a solid {spec.get('background')} background")
    # The spec's conventions are the project's style contract - feed them to
    # the image model so the raster already matches the intended look.
    style = str(spec.get("conventions", "")).strip()
    return (
        f"{user_prompt}. "
        f"High-quality pixel art sprite, single centered subject, "
        f"about {w}x{h} native pixel resolution, clean readable silhouette, "
        f"crisp hard-edged pixels with deliberate shading and a 3-5 tone ramp, "
        f"light source from the {light_word}. "
        f"Restricted palette of {len(legend)} colors: {hexes}. "
        + (f"Style contract: {style} " if style else "")
        + f"{bg}. No text, no watermark, no UI, no drop shadow on the ground, "
        f"no border frame. Centered with even margins."
    )


def gen_openai(prompt: str, out_png: Path, size: str) -> None:
    """Call the OpenAI Images API and write the PNG. Stdlib urllib only."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SpriteError("OPENAI_API_KEY is not set")
    body = json.dumps({
        "model": os.environ.get("PIXY_OPENAI_MODEL", "gpt-image-1"),
        "prompt": prompt, "n": 1, "size": size,
        "background": "transparent",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations", data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise SpriteError(f"OpenAI API error {e.code}: {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        raise SpriteError(f"network error reaching OpenAI: {e.reason}")
    data = payload.get("data", [{}])[0]
    if "b64_json" in data:
        out_png.write_bytes(base64.b64decode(data["b64_json"]))
    elif "url" in data:
        with urllib.request.urlopen(data["url"], timeout=120) as r:
            out_png.write_bytes(r.read())
    else:
        raise SpriteError("OpenAI response had no image data")


def gen_hf(prompt: str, out_png: Path) -> None:
    """Call the Hugging Face serverless Inference API (text-to-image) and
    write the PNG. Stdlib urllib only. Env: HF_TOKEN (or HUGGINGFACE_TOKEN),
    optional PIXY_HF_MODEL (default FLUX.1-schnell)."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        raise SpriteError("HF_TOKEN is not set")
    model = os.environ.get("PIXY_HF_MODEL", "black-forest-labs/FLUX.1-schnell")
    req = urllib.request.Request(
        f"https://api-inference.huggingface.co/models/{model}",
        data=json.dumps({"inputs": prompt}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise SpriteError(f"HF API error {e.code}: {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        raise SpriteError(f"network error reaching Hugging Face: {e.reason}")
    if data[:4] != b"\x89PNG" and data[:2] != b"\xff\xd8":
        raise SpriteError(f"HF returned non-image data: {data[:200]!r}")
    out_png.write_bytes(data)


def gen_command(prompt: str, out_png: Path, cmd: str,
                ref: Path | None = None) -> None:
    """Run an arbitrary image-gen command. {prompt}, {out_png} and {ref_png}
    are substituted - {ref_png} enables img2img / reference-conditioned
    generation with local models (character set consistency)."""
    filled = cmd.replace("{prompt}", shlex.quote(prompt)) \
                .replace("{out_png}", shlex.quote(str(out_png)))
    if "{ref_png}" in filled:
        if not ref:
            raise SpriteError("--cmd uses {ref_png} but no --ref was given")
        filled = filled.replace("{ref_png}", shlex.quote(str(ref)))
    proc = subprocess.run(filled, shell=True)
    if proc.returncode != 0:
        raise SpriteError(f"image command failed (exit {proc.returncode})")
    if not out_png.exists():
        raise SpriteError(f"image command did not write {out_png}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", help="what to draw, in natural language")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--out", type=Path, required=True, help="output .pix")
    p.add_argument("--provider", choices=("prompt-only", "openai", "hf",
                                          "command", "file"),
                   default="prompt-only")
    p.add_argument("--prompt-only", action="store_true",
                   help="shorthand for --provider prompt-only")
    p.add_argument("--cmd", help="shell template for --provider command")
    p.add_argument("--image", type=Path,
                   help="existing raster for --provider file")
    p.add_argument("--ref", type=Path,
                   help="character reference image: substituted as {ref_png} "
                        "in --cmd (img2img), and noted in the prompt so every "
                        "pose stays the SAME character")
    p.add_argument("--size", default="1024x1024",
                   help="image-model output size (default 1024x1024)")
    p.add_argument("--keep-png", type=Path,
                   help="also save the raw generated PNG here")
    # conform pass-through
    p.add_argument("--dither", action="store_true",
                   help="dither to the locked palette - adds scatter; only for "
                        "smooth gradients, not clean flat art")
    p.add_argument("--denoise", choices=("none", "low", "med", "high", "max"),
                   default="low",
                   help="clean stray pixels off flat areas, line-preserving "
                        "(default low)")
    p.add_argument("--denoise-area", type=int, default=None, metavar="N",
                   help="absorb same-color blobs smaller than N px (stronger "
                        "than 'max'; line-preserving)")
    p.add_argument("--denoise-guard", type=int, default=150, metavar="DIST",
                   help="feature protection: only absorb strays within DIST "
                        "color distance of the surround (default 150)")
    p.add_argument("--no-keep-features", action="store_true",
                   help="disable high-contrast feature re-injection on "
                        "downscale")
    p.add_argument("--simplify", choices=("none", "low", "med", "high"),
                   default="none",
                   help="reduce tones/colors and chunk the grid")
    p.add_argument("--outline", metavar="CHAR",
                   help="finish with a clean 1px outline ('spec' = the spec's "
                        "outline color)")
    p.add_argument("--outline-mode", choices=("hard", "selout"),
                   default="hard",
                   help="selout = retro selective outline (lit edges keep a "
                        "darker self-color)")
    p.add_argument("--dither-mode", choices=("ordered", "fs"),
                   default="ordered",
                   help="ordered = retro Bayer weave (default); fs = modern "
                        "error diffusion")
    p.add_argument("--contain", action="store_true",
                   help="aspect-preserving fit (avoid stretching)")
    p.add_argument("--bg-tolerance", type=float, default=42.0)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.prompt_only:
        args.provider = "prompt-only"
    try:
        spec = load_spec(args.spec)
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    prompt = build_prompt(args.prompt, spec)
    if args.ref:
        prompt += (" SAME character as the reference image: identical "
                   "colors, proportions, face, and design - only the pose "
                   "changes.")

    if args.provider == "prompt-only":
        print("# Pixel-art prompt (run this in your image tool, save the PNG,")
        print("# then conform it):")
        print()
        print(prompt)
        print()
        print(f"#   python scripts/imageify.py YOUR.png --spec {args.spec} "
              f"--out {args.out} {'--dither ' if args.dither else ''}"
              f"{'--denoise ' + args.denoise + ' ' if args.denoise != 'low' else ''}"
              f"{'--simplify ' + args.simplify + ' ' if args.simplify != 'none' else ''}"
              f"{'--contain ' if args.contain else ''}--force")
        return 0

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2

    tmp_png = args.keep_png
    cleanup = None
    if tmp_png is None and args.provider in ("openai", "hf", "command"):
        fd, name = tempfile.mkstemp(suffix=".png", prefix="pixy_gen_")
        os.close(fd)
        tmp_png = Path(name)
        cleanup = tmp_png
    try:
        if args.provider == "openai":
            gen_openai(prompt, tmp_png, args.size)
        elif args.provider == "hf":
            gen_hf(prompt, tmp_png)
        elif args.provider == "command":
            if not args.cmd:
                raise SpriteError("--provider command requires --cmd")
            gen_command(prompt, tmp_png, args.cmd, args.ref)
        elif args.provider == "file":
            if not args.image or not args.image.exists():
                raise SpriteError("--provider file requires an existing --image")
            tmp_png = args.image

        # Deterministic conform step (shared with imageify.py).
        import imageify
        outline = args.outline
        if outline == "spec":
            outline = spec.get("shading", {}).get("outline") \
                or spec.get("outline", {}).get("char")
        if outline and outline not in spec["legend"]:
            raise SpriteError(f"--outline {outline!r} not in the spec legend")
        img = imageify.Image.open(tmp_png)
        img.load()
        rows = imageify.conform(
            img, spec, dither=args.dither, bg_tol=args.bg_tolerance,
            resample="box", crop=True, contain=args.contain, clean=True,
            simplify=args.simplify, denoise=args.denoise,
            denoise_area=args.denoise_area, outline=outline,
            guard=args.denoise_guard,
            keep_features=not args.no_keep_features,
            dither_mode=args.dither_mode, outline_mode=args.outline_mode)
        errs = imageify.validate_grid(rows, spec)
        if errs:
            raise SpriteError("conformed grid invalid: " + "; ".join(errs))
        imageify.write_pix(rows, args.out,
                           header=f"generated: {args.prompt[:48]}")
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except SystemExit:                                  # Pillow missing
        print("error: Pillow is required for the conform step", file=sys.stderr)
        return 3
    finally:
        if cleanup is not None and cleanup.exists():
            try:
                cleanup.unlink()
            except OSError:
                pass

    transparent = str(spec["transparent_char"])
    used = sorted({c for row in rows for c in row if c != transparent})
    print(f"wrote {args.out}  ({spec['canvas']['width']}x"
          f"{spec['canvas']['height']} grid, {len(used)} colors)")
    if args.keep_png:
        print(f"  raw image kept at {args.keep_png}")
    print("  next: render_sprite.py to view, detail_score.py to grade, "
          "edit the .pix to refine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
