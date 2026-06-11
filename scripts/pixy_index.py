#!/usr/bin/env python3
"""Index a pixel-art project into a searchable asset library.

Usage:
    pixy_index.py PROJECT_DIR --out library.html [--json catalog.json]
    pixy_index.py out/ recolors/ --spec hero.spec.json --out library.html

As a project grows, finding the right asset gets hard. This scans for every
`.pix`, resolves each one's spec, and catalogs it - name, set, canvas, colors
used, craft score, spec fingerprint (drift), and a thumbnail - into a machine
JSON and a self-contained, filterable HTML library (search by name, filter by
set / spec / min craft). No dependencies in the output page.

Spec resolution per asset, in order: --spec, a sibling `<stem>.spec.json`,
any single `*.spec.json` in the same folder, else the nearest one walking up.
Assets with no resolvable spec are listed but not rendered/scored.

Exit codes: 0 = written, 2 = usage/IO error, 3 = Pillow missing.
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sprite import SpriteError, load_spec, parse_pix, validate_grid  # noqa: E402
import craft_score  # noqa: E402
import style_lock  # noqa: E402

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("error: Pillow is required. Install: python -m pip install Pillow",
          file=sys.stderr)
    sys.exit(3)

from render_sprite import render  # noqa: E402


def find_pix(roots):
    seen = set()
    out = []
    for r in roots:
        if r.is_file() and r.suffix == ".pix":
            cands = [r]
        else:
            cands = sorted(r.rglob("*.pix"))
        for p in cands:
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                out.append(p)
    return out


def resolve_spec(pix: Path, explicit: Path | None, cache: dict):
    if explicit:
        return explicit
    sib = pix.with_suffix(".spec.json")
    if sib.exists():
        return sib
    d = pix.parent
    here = sorted(d.glob("*.spec.json"))
    if len(here) == 1:
        return here[0]
    for up in [d, *d.parents]:
        ss = sorted(up.glob("*.spec.json"))
        if len(ss) == 1:
            return ss[0]
    return None


def set_name(pix: Path, root: Path):
    """A grouping label: the parent folder relative to root, or the filename
    prefix for sequence assets (walk_0 -> walk, s_3 -> s-dir)."""
    stem = pix.stem
    base, _, idx = stem.rpartition("_")
    rel = pix.parent.relative_to(root) if root in pix.parents or root == pix.parent else pix.parent
    folder = str(rel) if str(rel) != "." else pix.parent.name
    if idx.isdigit() and base:
        return f"{folder}/{base}"
    return folder


def thumb_b64(rows, spec, target=64):
    img = render(rows, spec, 1).convert("RGBA")
    s = max(1, target // max(img.width, img.height))
    if s > 1:
        img = img.resize((img.width * s, img.height * s), Image.NEAREST)
    b = io.BytesIO()
    img.save(b, "PNG")
    return base64.b64encode(b.getvalue()).decode()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("roots", type=Path, nargs="+", help="project dir(s) or .pix")
    p.add_argument("--spec", type=Path, help="force one spec for all assets")
    p.add_argument("--out", type=Path, help="output HTML library")
    p.add_argument("--json", type=Path, dest="json_out",
                   help="also write the catalog as JSON")
    p.add_argument("--title", default="Pixy Asset Library")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if not args.out and not args.json_out:
        print("error: pass --out and/or --json", file=sys.stderr)
        return 2
    for o in (args.out, args.json_out):
        if o and o.exists() and not args.force:
            print(f"error: {o} exists; pass --force", file=sys.stderr)
            return 2

    root = min((r if r.is_dir() else r.parent for r in args.roots),
               key=lambda d: len(d.parts))
    pix_files = find_pix(args.roots)
    if not pix_files:
        print("error: no .pix files found", file=sys.stderr)
        return 2

    spec_cache: dict[Path, dict] = {}
    catalog = []
    for pix in pix_files:
        entry = {"path": str(pix), "name": pix.stem,
                 "set": set_name(pix, root)}
        sp = resolve_spec(pix, args.spec, spec_cache)
        try:
            rows = parse_pix(pix)
        except SpriteError as e:
            entry.update(status="unreadable", error=str(e))
            catalog.append(entry)
            continue
        if sp is None:
            entry.update(status="no-spec",
                         canvas=f"{len(rows[0])}x{len(rows)}")
            catalog.append(entry)
            continue
        try:
            if sp not in spec_cache:
                spec_cache[sp] = load_spec(sp)
            spec = spec_cache[sp]
            errs = validate_grid(rows, spec)
            if errs:
                raise SpriteError("; ".join(errs))
        except SpriteError as e:
            entry.update(status="invalid", spec=str(sp), error=str(e))
            catalog.append(entry)
            continue
        used = sorted({c for r in rows for c in r
                       if c != spec["transparent_char"]})
        cscore = craft_score.score(rows, spec)
        stamp = style_lock.read_stamp(pix)
        cur = spec.get("spec_id")
        entry.update(
            status="ok", spec=str(sp),
            canvas=f"{spec['canvas']['width']}x{spec['canvas']['height']}",
            colors=len(used),
            palette=[spec["legend"][c] for c in used if c in spec["legend"]],
            craft=cscore["overall"], grade=cscore["grade"],
            drift=(stamp is not None and cur is not None and stamp != cur),
            thumb=thumb_b64(rows, spec))
        catalog.append(entry)

    ok = [e for e in catalog if e["status"] == "ok"]
    sets = sorted({e["set"] for e in catalog})
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps({"count": len(catalog), "sets": sets,
                        "assets": catalog}, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out} ({len(catalog)} assets)")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(build_html(catalog, sets, ok, args.title),
                            encoding="utf-8")
        avg = round(sum(e["craft"] for e in ok) / len(ok)) if ok else 0
        print(f"wrote {args.out}  ({len(catalog)} assets, {len(sets)} sets, "
              f"avg craft {avg})")
    return 0


def build_html(catalog, sets, ok, title):
    avg = round(sum(e["craft"] for e in ok) / len(ok)) if ok else 0
    cards = []
    for e in catalog:
        st = e["status"]
        if st == "ok":
            sw = "".join(
                f'<i style="background:{html.escape(c)}"></i>'
                for c in e.get("palette", [])[:16])
            badge = (' <b class="drift">drift</b>' if e.get("drift") else "")
            cards.append(
                f'<div class="card" data-set="{html.escape(e["set"])}" '
                f'data-name="{html.escape(e["name"].lower())}" '
                f'data-craft="{e["craft"]}">'
                f'<img src="data:image/png;base64,{e["thumb"]}">'
                f'<div class="nm">{html.escape(e["name"])}{badge}</div>'
                f'<div class="mt">{html.escape(e["set"])} &middot; {e["canvas"]} &middot; '
                f'{e["colors"]}c &middot; craft {e["craft"]} ({html.escape(e["grade"])})</div>'
                f'<div class="pal">{sw}</div></div>')
        else:
            cards.append(
                f'<div class="card bad" data-set="{html.escape(e["set"])}" '
                f'data-name="{html.escape(e["name"].lower())}" data-craft="0">'
                f'<div class="nm">{html.escape(e["name"])}</div>'
                f'<div class="mt">{html.escape(st)}: '
                f'{html.escape(str(e.get("error", e.get("canvas", ""))))[:60]}</div></div>')
    opts = "".join(f'<option value="{html.escape(s)}">{html.escape(s)}</option>'
                   for s in sets)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
 body{{background:#15161f;color:#e8e8ee;font:14px system-ui,sans-serif;margin:0;padding:20px}}
 h1{{font-size:19px;margin:0 0 2px}} .sub{{color:#8b95b2;margin-bottom:14px}}
 .bar{{position:sticky;top:0;background:#15161f;padding:8px 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;z-index:2}}
 input,select{{background:#0e0f17;color:#cfe;border:1px solid #2a2d44;border-radius:6px;padding:6px 8px}}
 .grid{{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}}
 .card{{width:150px;background:#1b1d2b;border:1px solid #2a2d44;border-radius:8px;padding:8px;text-align:center}}
 .card.bad{{border-color:#b13e53}} .card img{{width:96px;height:96px;image-rendering:pixelated;background:#0e0f17;border-radius:4px}}
 .nm{{font-weight:700;margin-top:6px;font-size:13px;word-break:break-all}} .mt{{color:#8b95b2;font-size:11px;margin-top:2px}}
 .drift{{color:#ffcd75}} .pal{{margin-top:5px;line-height:0}} .pal i{{display:inline-block;width:9px;height:9px;border-radius:2px}}
 .val{{color:#a7f070}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="sub">{len(catalog)} assets &middot; {len(sets)} sets &middot; avg craft {avg}</div>
<div class="bar">
  <input id="q" placeholder="search name..." oninput="flt()">
  <select id="set" onchange="flt()"><option value="">all sets</option>{opts}</select>
  <label>min craft <span class="val" id="cv">0</span>
    <input type="range" id="cf" min="0" max="100" value="0" oninput="flt()" style="width:120px"></label>
  <span id="n" class="val"></span>
</div>
<div class="grid" id="g">{''.join(cards)}</div>
<script>
function flt(){{
  var q=document.getElementById('q').value.toLowerCase();
  var s=document.getElementById('set').value;
  var c=+document.getElementById('cf').value;
  document.getElementById('cv').textContent=c;
  var n=0;
  document.querySelectorAll('.card').forEach(function(el){{
    var ok=(!q||el.dataset.name.indexOf(q)>=0)&&(!s||el.dataset.set===s)&&(+el.dataset.craft>=c);
    el.style.display=ok?'':'none'; if(ok)n++;
  }});
  document.getElementById('n').textContent=n+' shown';
}}
flt();
</script></body></html>
"""


if __name__ == "__main__":
    sys.exit(main())
