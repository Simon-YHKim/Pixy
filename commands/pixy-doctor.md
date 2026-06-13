---
name: pixy-doctor
description: Check the environment - which Pixy track is ready and how to enable the other
---

Run `python scripts/pixy_doctor.py` and report which track is ready.

If the user wants Track 2 (3D) but Blender is missing, show the exact
platform install command from the doctor output and offer to run it (with the
user's consent - it changes their system). The doctor finds Blender even when
it is not on PATH (standard Windows/macOS/Steam/snap/flatpak install locations,
or the `PIXY_BLENDER` override), and Track 2 then works headless
(`blender --background --python ...`); a blender-mcp server is an optional
alternative, never required. Never tell a non-3D user they must
learn Blender - route them to Track 1.
