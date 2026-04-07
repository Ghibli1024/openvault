---
name: xhs-favorites-to-obsidian
description: Use when exporting Xiaohongshu favorites into an Obsidian-ready Markdown archive with semantic taxonomy, collection indexes, and repeatable merge sync.
---

# 小红书收藏到 Obsidian

## Overview

Core purpose: convert exported Xiaohongshu HTML lists into a local Markdown archive under `小红书/`.

This skill is modeled after `$x-to-obsidian`, but it no longer treats browser crawling as the primary input. The preferred path is local HTML export files for `收藏` and `喜欢`, then sync into Obsidian.

## Fixed defaults in this version

- scope: exported `收藏` and exported `喜欢`
- depth: HTML-provided title/content/author/type/likes/cover only
- output: independent archive
- sync: repeatable incremental sync
- source role: semantic taxonomy + source indexes coexist
- classification: `auto` only
- default target root: `/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources`
- default taxonomy note: `/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources/书签库/ROOT分类目录.md`

## Required inputs

Collect and confirm these before running:

1. `favorites-html`
2. `liked-html` optional
3. `target-root`
4. `mode`: `merge` or `create`
5. `title-language`: `zh` or `en`
6. `confirm`: explicit execution confirmation such as `run`

Do not ask the user for a classification rule source unless the default taxonomy path is missing and there is no local `小红书/04 领域/ROOT分类目录.md`.
Do not assume defaults for `merge` vs `create`.

## Intake style

Ask in a short one-question-at-a-time flow.

Use compact option prompts for enum-like choices:

- `mode`
  - `merge`: update existing archive, refresh source membership, move removed notes into `07 废弃`
  - `create`: rebuild archive from current export only
- `title-language`
  - `zh`: Chinese headings and date/month labels
  - `en`: English headings where supported

When the current workspace already has an obvious target root, propose it first instead of asking the user to reconstruct the full path manually.
If the user provides a path ending in `/小红书`, treat it as the intended final output folder, normalize `target-root` to its parent directory, and explicitly confirm that interpretation before running.

## Workflow

1. Confirm `favorites-html`.
2. If available, confirm `liked-html`.
3. Confirm `target-root`.
4. Confirm `mode`.
5. Confirm `title-language`.
6. Confirm `run`.
7. Run export:

```bash
python3 /Users/Totoro/.codex/skills/xhs-favorites-to-obsidian/scripts/export_xhs_favorites.py \
  --favorites-html "/path/to/收藏.html" \
  --liked-html "/path/to/喜欢.html" \
  --output-json "$CODEX_HOME/state/xhs-favorites/latest-export.json"
```

8. Run sync:

```bash
python3 /Users/Totoro/.codex/skills/xhs-favorites-to-obsidian/scripts/sync_xhs_favorites.py \
  --input-json "$CODEX_HOME/state/xhs-favorites/latest-export.json" \
  --target-root "/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources" \
  --mode merge \
  --classification auto \
  --title-language zh
```

9. Read the JSON summary and report:
  - final notes
  - moved to 废弃
  - top domains
  - source count
  - output root

## Current crawler behavior

- Preferred input is plugin-exported HTML.
- `收藏` and `喜欢` can be imported separately, then merged by `note_id`.
- Browser-driven enrichment remains best-effort only and should not be the default because it can trigger platform risk controls.
- If enrichment is attempted, it may reuse:

```bash
opencli xiaohongshu note <full-note-url> -f json
```

Always keep the full note URL with `xsec_token` when available. Do not downgrade to a bare note ID for enrichment. For HTML-only imports, `xsec_token` is usually unavailable, so `fetch_status` should remain `partial`.

## Output contract

Final structure under `XX/小红书/`:

- `01 日期/`
- `02 作者/`
- `03 来源/`
- `04 领域/`
- `05 粗分类/`
- `06 搜索/`
- `07 废弃/`
- `04 领域/ROOT分类目录.md`
- `Dashboard.md`

`07 废弃/` is a stable managed root. Do not create a visible helper note inside it. If it would otherwise be empty, only a hidden internal placeholder file may be present.

Each active note frontmatter includes at least:

- `platform`
- `note_id`
- `title`
- `author_id`
- `author_name`
- `edited_at`
- `note_type`
- `source`
- `canonical_url`
- `source_actions`
- `domain`
- `likes`
- `collects`
- `comments`
- `cover_url`
- `media_urls`
- `fetch_status`
- `tags`
- `imported_at`

## Validation checklist

After running, ensure:

1. Root contains `01 日期`, `02 作者`, `03 来源`, `04 领域`, `05 粗分类`, `06 搜索`, `07 废弃`, `Dashboard.md`.
2. `final_note_files == final_notes`.
3. `04 领域/ROOT分类目录.md` exists.
4. `03 来源/Index.md` exists and lists active sources such as `收藏` and `喜欢`.
5. `05 粗分类/Index.md` exists and at least one coarse bucket file is generated.
6. `Dashboard.md` contains month stats, domain stats, source stats, and coarse category stats.
7. If only HTML input is provided, items may legitimately remain `partial`.
8. `07 废弃/` exists and does not expose a visible helper note; if needed for persistence, only a hidden internal placeholder file may be present.
