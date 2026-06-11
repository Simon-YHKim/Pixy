---
name: pixy-index
description: Build a searchable HTML library of all pixel-art assets in a project
---

Build the asset library for the project directory: $ARGUMENTS (default: the
current project's asset output dir).

Run:
    python scripts/pixy_index.py <DIR> --out pixy-library.html --json pixy-catalog.json --force

Then summarize: total assets, sets, average craft, and any assets flagged
`drift` / `invalid` / `no-spec`. Open the HTML for the user (search by name,
filter by set / min craft). Offer to re-run the Loop on low-craft or drifted
assets.
