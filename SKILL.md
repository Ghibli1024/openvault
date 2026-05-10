---
name: openvault
description: Use when a user wants to import, sync, search, or clean a local Obsidian or Markdown resources archive from browser bookmarks, Xiaohongshu exports, Bilibili favorites, or X likes.
---

# Openvault

Openvault is a local-first archive workflow. It turns bookmark exports and social favorites into one Markdown resources library while preserving source-specific layouts.

## When To Use

Use this skill when the user asks to:

- import browser bookmark HTML into a Markdown or Obsidian archive
- import Xiaohongshu favorites or likes HTML
- sync Bilibili favorites from a local logged-in browser
- import X or Twitter likes JSON
- search across a shared resources root
- clean or apply a shared rubbish/deletion queue

Do not use this skill for generic file conversion, non-archive scraping, or unrelated Obsidian note editing.

## Quick Start

If the user names a source directly, route to that workflow:

| User intent | Source workflow |
|---|---|
| `书签`, `bookmark`, `bookmarks.html` | `sources/bookmarks/WORKFLOW.md` |
| `小红书`, `Xiaohongshu`, `xhs` | `sources/xhs/WORKFLOW.md` |
| `B站`, `Bilibili` | `sources/bilibili/WORKFLOW.md` |
| `X likes`, `Twitter likes`, `likes.json` | `sources/x-likes/WORKFLOW.md` |

If a file path, filename, or pasted artifact name is available but the source is not obvious, run:

```bash
python3 scripts/detect_source.py \
  --text "<user request text>" \
  --path "/absolute/or/pasted/path"
```

If the helper returns a unique source, read only that source workflow. If it returns `ambiguous`, ask one targeted clarifying question.

## Shared Rules

- Read `references/taxonomy-policy.md` when merging into or reclassifying an existing archive.
- Read `references/managed-archive-policy.md` for Xiaohongshu, Bilibili, and X managed archives.
- Do not force bookmarks into the managed archive root layout; bookmarks keep the categories-only structure.
- Preserve an existing local `ROOT分类目录.md` unless the user explicitly asks to rewrite taxonomy.
- Treat global `搜索/` as the cross-source search result root.
- Treat global `废弃/` as the manual deletion queue, not as a dump for every upstream diff.

## Search And Rubbish

For global search, use:

```bash
python3 scripts/search_resources.py \
  --resources-root "<resources-root>" \
  --query "<query>"
```

When cleaning rubbish, inspect the shared `废弃/` folder first, then apply the routed source workflow only if the cleanup needs to affect generated source views.

## Reporting

After running a workflow, report:

- source and input path
- target root and final output folder
- mode, taxonomy source, and title language when relevant
- created, updated, removed, or moved-to-rubbish counts when the summary provides them
- exact verification command or generated summary file path
