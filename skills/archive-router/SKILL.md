---
name: archive-router
description: Route Obsidian archive requests to the right source-specific workflow when the user wants to import bookmark HTML, Xiaohongshu favorites HTML, Bilibili favorites, or X likes JSON without remembering which skill to call.
---

# Archive Router

Use this as the single visible plugin entry for `openvault`.

## Routing Rules

- If the user explicitly names `书签`, `书签库`, `小红书`, `B站`, `Bilibili`, `X`, `X Likes`, or `Twitter/X likes`, route directly.
- If a file path, filename, or pasted artifact name is available, run:

```bash
python3 /Users/Totoro/plugins/openvault/scripts/detect_source.py \
  --text "<user request text>" \
  --path "/absolute/or/pasted/path"
```

- If the helper returns a unique source, continue with the matching wrapper skill immediately.
- If the helper returns `ambiguous`, ask exactly one targeted clarifying question and wait.
- Do not re-specify the full import workflow once routed. Load the matching wrapper skill and let it hand off to the canonical source skill.
- If the user asks to search without naming a specific source, search across the whole resources root and include the global `废弃/` folder.
- If the user asks to clean up `废弃`, treat the global `废弃/` folder as the only manual deletion queue. Do not recreate per-source `搜索/废弃` roots.

## Source Map

- `bookmarks` -> `$archive-bookmarks`
- `xhs` -> `$archive-xhs`
- `bilibili` -> `$archive-bilibili`
- `x-likes` -> `$archive-x-likes`

## Shared References

- Read `../../references/taxonomy-policy.md` when the routed workflow may merge into or reclassify an existing archive.
- Read `../../references/managed-archive-policy.md` for `小红书`, `B站`, and `X`.
- Do not force `书签` into the managed archive root layout.
