---
name: pixy-learn
description: Record a control/runtime mistake learned this session into references/runtime-lessons.md and ship it to GitHub (commit, push, PR, merge on green CI). Use after you hit and fixed a launch/quoting/permission/engine-API/GPU/headless/computer-use gotcha so the skill never repeats it.
---

Pixy improves itself: every control- or runtime-level mistake that wasn't
obvious from the docs gets captured in the repo, not just this session. Run
this whenever you hit AND fixed such a gotcha (NOT for art-craft feedback —
that goes through the Loop / vision-qa).

## 1. Record

Append a **Symptom -> Cause -> Fix** entry (terse, one copy-pasteable line or
snippet) to `references/runtime-lessons.md`, under the right section
(Blender API / Process control / Computer-use), newest first. Add a new section
heading if the lesson is a new category. One lesson per entry.

If the lesson is mechanical enough to bake into a tool (e.g. a node lookup or
device-enable pattern), also harden the relevant `scripts/*.py` so the fix is
automatic, then note "(baked into <script>)" in the entry.

## 2. Ship it (the skill is a git repo — keep lessons in the repo)

The user has standing approval for Pixy to push and merge its own lessons.
Always gate the merge on green CI; never force-push.

    git checkout -b lesson/<short-slug>
    git add references/runtime-lessons.md   # + any hardened scripts/docs
    # if you changed code: bump version in .claude-plugin/plugin.json + SKILL.md
    #                      and add a CHANGELOG.md entry
    git commit            # docs(lessons): <slug>  — end with the Co-Authored-By trailer
    git push -u origin lesson/<short-slug>
    gh pr create --fill
    gh pr checks --watch  # wait for green (the integration + ASCII + doc-lint gates)
    gh pr merge --squash --delete-branch
    git checkout main && git pull --ff-only origin main

If CI is red, fix the cause (a docs-only lesson should never break it — most
likely a broken reference link, or a stray tools/scripts count number in a
gate-scanned doc) and re-push before merging.

## Scope

- Yes: "Start-Process mangled the spaced path", "BLENDER_EEVEE_NEXT enum gone in
  5.x", "open_application spawned a new default instance", "Cycles ran on CPU".
- No: "eyes look too green", "shell reads flat" — those are craft, handled by
  craft_score + vision-qa, not lessons.
