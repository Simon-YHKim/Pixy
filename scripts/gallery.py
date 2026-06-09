#!/usr/bin/env python3
"""Build an HTML review gallery of a .pix asset set with detail scores.

Usage:
    gallery.py *.pix --spec pixy.spec.json --out gallery.html

Renders every asset, scores its detail, and writes one self-contained HTML
page (base64 thumbnails, no dependencies) for eyeballing the whole set at
once: each card shows the sprite, its detail score and grade, sub-metrics,
and the top fix suggestion. A header summarizes the set - average detail,
shared canvas size, and any asset whose detail is well below the average -
so it is obvious which assets to regenerate and whether the set is uniform.

Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402
import detail_score  # noqa: E402

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("error: Pillow is required. Install: python -m pip install Pillow",
          file=sys.stderr)
    sys.exit(3)

from render_sprite import render  # noqa: E402

GRADE_COLOR = {"rich": "#38b764", "detailed": "#a7f070", "shaded": "#41a6f6",
               "basic": "#ffcd75", "flat/blocky": "#ef7d57", "empty": "#b13e53"}


def png_b64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sprites", type=Path, nargs="+", help=".pix files")
    p.add_argument("--spec", type=Path, required=True, help="pixy.spec.json")
    p.add_argument("--out", type=Path, required=True, help="output .html")
    p.add_argument("--title", default="Pixy asset gallery")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists; pass --force", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        scale = max(1, min(8, 192 // max(1, int(spec["canvas"]["width"]))))
        cards, scores = [], []
        for sp in args.sprites:
            rows = parse_pix(sp)
            errs = validate_grid(rows, spec)
            if errs:
                raise SpriteError(f"{sp}: {'; '.join(errs)}")
            img = render(rows, spec, scale)
            r = detail_score.score(rows, dict(spec))
            scores.append(r["overall"])
            metrics = " ".join(f"{k[:3]} {r['metrics'][k]*100:.0f}"
                               for k in detail_score.WEIGHTS)
            color = GRADE_COLOR.get(r["grade"], "#94b0c2")
            cards.append((html.escape(sp.name), png_b64(img), r["overall"],
                          html.escape(r["grade"]), color, html.escape(metrics),
                          html.escape(r["suggestions"][0])))
    except SpriteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    avg = sum(scores) / len(scores) if scores else 0
    cw, ch = spec["canvas"]["width"], spec["canvas"]["height"]
    outliers = [c[0] for c, s in zip(cards, scores) if s < avg - 15]
    summary = (f"{len(cards)} assets &middot; avg detail "
               f"<b>{avg:.0f}/100</b> &middot; canvas {cw}&times;{ch}")
    if outliers:
        summary += (" &middot; <span style='color:#ef7d57'>uneven: "
                    + ", ".join(outliers) + "</span>")

    card_html = "\n".join(
        f"""<div class="card">
  <div class="thumb"><img src="data:image/png;base64,{b64}" alt="{name}"></div>
  <div class="name">{name}</div>
  <div class="score"><span class="badge" style="background:{color}">{ov}</span>
    <span class="grade">{grade}</span></div>
  <div class="metrics">{metrics}</div>
  <div class="sug">{sug}</div>
</div>""" for (name, b64, ov, grade, color, metrics, sug) in cards)

    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{html.escape(args.title)}</title><style>
  body {{ background:#1a1c2c; color:#e8e8ee; font:14px system-ui,sans-serif;
         margin:0; padding:24px; }}
  h1 {{ font-size:18px; margin:0 0 4px; }}
  .sum {{ color:#94b0c2; margin-bottom:20px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
          gap:16px; }}
  .card {{ background:#252840; border-radius:8px; padding:12px; }}
  .thumb {{ display:flex; justify-content:center; align-items:center;
           height:160px; background:#0f1018 url('data:image/svg+xml;utf8,\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="8" \
height="8" fill="%23202234"/><rect x="8" y="8" width="8" height="8" \
fill="%23202234"/></svg>') repeat; border-radius:4px; }}
  .thumb img {{ image-rendering:pixelated; max-width:100%; max-height:100%; }}
  .name {{ margin-top:8px; font-weight:600; }}
  .score {{ margin-top:4px; }}
  .badge {{ color:#1a1c2c; font-weight:700; padding:1px 8px; border-radius:10px; }}
  .grade {{ color:#94b0c2; margin-left:6px; }}
  .metrics {{ color:#7b86a8; font-size:11px; margin-top:6px; }}
  .sug {{ color:#b6c0d8; font-size:12px; margin-top:6px; }}
</style></head><body>
<h1>{html.escape(args.title)}</h1>
<div class="sum">{summary}</div>
<div class="grid">
{card_html}
</div></body></html>
"""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(doc, encoding="utf-8")
    print(f"wrote {args.out}  ({len(cards)} assets, avg {avg:.0f}/100)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
