#!/usr/bin/env python3
"""Check the environment and tell the user which track is ready (+ how to fix).

Usage:
    pixy_doctor.py            # human report
    pixy_doctor.py --json     # machine-readable

Pixy has two tracks; this reports what each needs and what is present, so an
agent can pick a track in the intake interview instead of failing mid-pipeline:

  Track 1 (pure LLM + image model): needs an image generator - the HOST agent's
           own image tool, OR an API key (OPENAI_API_KEY / HF_TOKEN), OR a
           local command. Pillow for the conform/render half.
  Track 2 (3D): needs Blender. As long as Blender is installed - on PATH OR in
           a standard location (Windows "Program Files", a macOS .app bundle,
           Steam/snap/flatpak), this script finds it - Pixy runs it HEADLESS
           (`blender --background --python ...`) - no MCP, no GUI, no 3D
           skills. A blender-mcp server is an alternative (agent drives a
           running Blender). Without Blender at all -> use Track 1.
           (Set PIXY_BLENDER to force a specific Blender binary.)

It never installs anything; it prints the exact platform-appropriate command
so the user (or agent, with consent) can run it.

Exit codes: 0 = at least one track ready, 1 = neither ready, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys

from blender_locate import blender_install_hint, find_blender


def _py_ok():
    return sys.version_info >= (3, 9)


def _have(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def install_hint(what):
    if what == "blender":
        return blender_install_hint()
    if what == "pillow":
        return "python -m pip install Pillow"
    if what == "blender-mcp":
        return ("optional - only if you want the agent to drive an already-"
                "open Blender; install a blender-mcp server and add it to your "
                "MCP client. NOT required: headless Blender already works.")
    return ""


def check():
    blender = find_blender()        # PATH, then standard install locations
    has_key = bool(os.environ.get("OPENAI_API_KEY")
                   or os.environ.get("HF_TOKEN")
                   or os.environ.get("HUGGINGFACE_TOKEN"))
    pillow = _have("PIL")
    # blender-mcp is detected by the host, not this script; report unknown.
    checks = [
        ("python>=3.9", _py_ok(), "core", None if _py_ok() else "upgrade Python"),
        ("Pillow", pillow, "conform/render (both tracks)",
         None if pillow else install_hint("pillow")),
        ("image API key (OPENAI_API_KEY / HF_TOKEN)", has_key,
         "Track 1 auto-generation (optional if the host has its own image tool)",
         None if has_key else "export OPENAI_API_KEY=... or HF_TOKEN=... "
         "(or let the host agent generate images itself)"),
        ("Blender (PATH or standard install)", bool(blender),
         f"Track 2 headless render (found: {blender})" if blender
         else "Track 2 headless render (no MCP / no 3D skills needed)",
         None if blender else install_hint("blender")),
    ]
    # Track readiness. Track 1's image source can be the host agent's own tool,
    # which this script cannot see - so Track 1 is "ready if Pillow" and we note
    # the image-source requirement.
    track1 = pillow
    track2 = pillow and bool(blender)
    return {
        "platform": platform.system(),
        "checks": [{"name": n, "ok": ok, "unlocks": u, "fix": f}
                   for n, ok, u, f in checks],
        "track1_ready": track1,
        "track1_note": ("conform/render ready; provide an image source - the "
                        "host agent's image tool, an API key, or "
                        "--provider command"),
        "track2_ready": track2,
        "track2_note": (f"Blender found at {blender} - runs headless, no MCP "
                        "needed" if track2 else
                        "install Blender (above); a blender-mcp server is an "
                        "optional alternative, not required"),
        "blender": blender or None,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    r = check()
    if args.json:
        print(json.dumps(r, indent=2))
        return 0 if (r["track1_ready"] or r["track2_ready"]) else 1

    print(f"Pixy environment ({r['platform']})\n")
    for c in r["checks"]:
        mark = "OK  " if c["ok"] else "MISS"
        print(f"  [{mark}] {c['name']}  - {c['unlocks']}")
        if c["fix"]:
            print(f"         fix: {c['fix']}")
    print()
    print(f"  Track 1 (pure LLM + image model): "
          f"{'READY' if r['track1_ready'] else 'NOT READY'}")
    print(f"         {r['track1_note']}")
    print(f"  Track 2 (3D via Blender):         "
          f"{'READY' if r['track2_ready'] else 'NOT READY'}")
    print(f"         {r['track2_note']}")
    print(f"\n  blender-mcp: {install_hint('blender-mcp')}")
    return 0 if (r["track1_ready"] or r["track2_ready"]) else 1


if __name__ == "__main__":
    sys.exit(main())
