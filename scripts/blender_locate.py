#!/usr/bin/env python3
"""Locate a Blender executable without requiring it on PATH.

Track 2 (3D) only needs Blender to *exist* on the machine - it runs headless
(`blender --background --python ...`), no MCP and no GUI. But most installers
never put `blender` on PATH: Windows drops it in `Program Files\\Blender
Foundation\\Blender X.Y\\blender.exe`, macOS hides it inside a `.app` bundle,
Steam/snap/flatpak each use their own prefix. A PATH-only probe
(`shutil.which`) therefore reports Track 2 unavailable on a machine that has
Blender installed and ready.

This module checks, in order:
  1. an explicit override env var (PIXY_BLENDER, then BLENDER_PATH),
  2. PATH (`shutil.which`),
  3. the conventional install locations for the current OS.
When several versioned installs exist it returns the highest version.

Public API:
    find_blender(verify=False) -> str | None   # absolute path, or None
    blender_install_hint() -> str              # platform install command

`verify=True` additionally runs `<blender> --version` (short timeout) and only
returns a path that actually launches - use it when a false positive is worse
than a slow check. Pure standard library; safe to import from any script.
"""
from __future__ import annotations

import glob
import os
import platform
import re
import shutil
import subprocess

_ENV_VARS = ("PIXY_BLENDER", "BLENDER_PATH")
_VER_RE = re.compile(r"(\d+)\.(\d+)")


def _is_exe(path: str | None) -> bool:
    if not path or not os.path.isfile(path):
        return False
    if os.name == "nt":          # any existing .exe is launchable on Windows
        return True
    return os.access(path, os.X_OK)


def _version_key(path: str) -> tuple[int, int]:
    """Best-effort version parsed from a path (e.g. ...\\Blender 5.1\\... ->
    (5, 1)) so the newest install sorts first. Unversioned paths sort last."""
    matches = _VER_RE.findall(path)
    if not matches:
        return (0, 0)
    major, minor = matches[-1]
    return (int(major), int(minor))


def _windows_candidates() -> list[str]:
    bases = []
    for var in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        val = os.environ.get(var)
        if val and val not in bases:
            bases.append(val)
    if not bases:                               # env stripped: fall back
        bases = [r"C:\Program Files", r"C:\Program Files (x86)"]
    pats = []
    for base in bases:
        pats.append(os.path.join(base, "Blender Foundation", "Blender*",
                                 "blender.exe"))
        # Steam install (no version dir)
        pats.append(os.path.join(base, "Steam", "steamapps", "common",
                                 "Blender", "blender.exe"))
    # winget shim, if present
    local = os.environ.get("LOCALAPPDATA")
    if local:
        pats.append(os.path.join(local, "Microsoft", "WinGet", "Links",
                                 "blender.exe"))
    return pats


def _macos_candidates() -> list[str]:
    home = os.path.expanduser("~")
    return [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender*.app/Contents/MacOS/Blender",
        "/Applications/Blender/Blender.app/Contents/MacOS/Blender",
        os.path.join(home, "Applications", "Blender.app", "Contents",
                     "MacOS", "Blender"),
        os.path.join(home, "Applications", "Blender*.app", "Contents",
                     "MacOS", "Blender"),
    ]


def _linux_candidates() -> list[str]:
    home = os.path.expanduser("~")
    return [
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/snap/bin/blender",
        "/var/lib/flatpak/exports/bin/org.blender.Blender",
        os.path.join(home, ".local", "share", "flatpak", "exports", "bin",
                     "org.blender.Blender"),
        os.path.join(home, ".local", "bin", "blender"),
        "/opt/blender*/blender",
        "/opt/blender/blender",
    ]


def _platform_candidates() -> list[str]:
    sysname = platform.system()
    if sysname == "Windows":
        return _windows_candidates()
    if sysname == "Darwin":
        return _macos_candidates()
    return _linux_candidates()


def _runs(path: str) -> bool:
    try:
        out = subprocess.run([path, "--version"], capture_output=True,
                             text=True, timeout=25)
    except Exception:
        return False
    return out.returncode == 0 and "Blender" in (out.stdout or "")


def find_blender(verify: bool = False) -> str | None:
    """Return an absolute path to a Blender executable, or None.

    Honors PIXY_BLENDER / BLENDER_PATH, then PATH, then OS-standard install
    dirs (newest version first). With verify=True the path must also pass
    `--version`.
    """
    def _ok(p: str | None) -> str | None:
        if _is_exe(p) and (not verify or _runs(p)):  # type: ignore[arg-type]
            return os.path.abspath(p)                # type: ignore[arg-type]
        return None

    # 1) explicit override
    for var in _ENV_VARS:
        hit = _ok(os.environ.get(var))
        if hit:
            return hit

    # 2) PATH
    hit = _ok(shutil.which("blender"))
    if hit:
        return hit

    # 3) standard install locations (expand globs, newest version wins)
    found: list[str] = []
    for pattern in _platform_candidates():
        if any(ch in pattern for ch in "*?["):
            found.extend(glob.glob(pattern))
        elif os.path.isfile(pattern):
            found.append(pattern)
    for cand in sorted(set(found), key=_version_key, reverse=True):
        hit = _ok(cand)
        if hit:
            return hit
    return None


def blender_install_hint() -> str:
    """Platform-appropriate install command for Blender (never auto-runs)."""
    return {
        "Darwin": "brew install --cask blender   (or download blender.org)",
        "Linux": "sudo apt install blender   |  sudo snap install blender "
                 "--classic  |  flatpak install flathub org.blender.Blender",
        "Windows": "winget install BlenderFoundation.Blender   (or "
                   "blender.org)",
    }.get(platform.system(),
          "install Blender from https://www.blender.org/download/")


if __name__ == "__main__":      # quick manual probe: prints the path or a hint
    import sys
    verify = "--verify" in sys.argv[1:]
    bl = find_blender(verify=verify)
    if bl:
        print(bl)
        sys.exit(0)
    print("blender not found; install:", blender_install_hint())
    sys.exit(1)
