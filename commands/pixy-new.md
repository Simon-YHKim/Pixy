---
name: pixy-new
description: Start a new pixel-art asset or set (runs the Pixy intake + pipeline)
---

Invoke the **pixy-the-pixel-art** skill to create pixel art for: $ARGUMENTS

Follow SKILL.md exactly:
1. Run `python scripts/pixy_doctor.py` to see which tracks are ready, and pick
   Track 1 (pure LLM + image model) or Track 2 (Blender) accordingly.
2. Print the intake brief-and-assumptions block and confirm.
3. Dispatch to the right pipeline (P1-P7), lock a spec first, and run the Loop
   (craft_score + lint + vision-QA) to a SHIP verdict before showing the user.
Deliver the asset(s) with the evidence line (craft N/100, lint, verdict).
