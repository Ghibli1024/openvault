---
name: html-bookmarks-to-markdown
description: Convert bookmark-style HTML exports into a locally stored Markdown archive with compact indexes, preserved category structure, incremental sync, and pending-description tracking for newly added links.
---

# HTML Bookmarks Markdown Sync

## Overview

Use this skill when the user provides a bookmark-style HTML file and wants:
- each URL explained in plain language,
- the original HTML category/folder structure preserved,
- future HTML exports compared against prior runs,
- Markdown output that stays in sync over time,
- or a second external HTML file imported into an existing archive with dedupe and category reuse.

This skill is modeled after the same "parse -> diff -> enrich -> sync" idea as the X-likes-to-Markdown workflow, but targets bookmark HTML exports instead of JSON post data.

## Defaults

Assume these unless the user asks otherwise:
- mode: `merge`
- title language: `zh`
- layout: `compact`
- preserve the HTML category structure exactly
- only newly added or still-undescribed URLs need fresh explanations

For `compact` layout:
- keep sync state outside the rendered archive by default
- keep `02 Links/` and `03 Domains/` inside the archive folder; only machine-state files belong in `state-root`
- keep domain indexes lightweight; do not duplicate full per-link detail there
- keep category indexes flattened for Obsidian: avoid deep nested category folders inside the vault
- when the target archive is inside an Obsidian vault under `.../iCloud~md~obsidian/Documents/<VaultName>/`, default the external state root to `.../iCloud~md~obsidian/Documents/<container-name>-state/` so it sits alongside the vault rather than inside it

If the user explicitly wants a single self-contained folder:
- keep the archive folder name exactly as requested, for example `Bookmarks`
- override `state-root` into the archive folder itself, preferably as `<target-root>/<container-name>/_state/`
- keep `00 Reports/`, `01 Categories/`, `02 Links/`, `03 Domains/`, `Dashboard.md`, and `_state/` all under that one archive folder
- when this archive lives inside iCloud/Obsidian, update those managed top-level paths in place instead of deleting and recreating the whole archive root

## Required User Decision

Before running, confirm where the archive should be stored.

`target-root` rules:
- Accept either an absolute path or a relative path.
- If the user gives a relative path, resolve it relative to the current working directory.
- If the user says "alongside X Likes" or a similar existing folder reference, infer the parent directory from that known path and state the inferred absolute path before running.
- If the user says something ambiguous such as `my notes folder`, do not guess between local home, Obsidian vault, or another location. Ask the user which path they want.
- Do not assume Obsidian unless the user explicitly says Obsidian, vault, or gives an Obsidian path.
- `state-root` may also be overridden explicitly; otherwise compact mode uses the default external-state rule above.

## Output Contract

The generated archive lives at:
`<target-root>/<container-name>/`

Default `compact` layout output:
- `01 Categories/`
- `02 Links/`
- `03 Domains/`
- `00 Reports/`
- `Dashboard.md`
- external state root containing:
  - `state.json`
  - `latest-summary.json`
  - `pending_annotations.json`
  - `excluded_links.json`

Single-folder compact variant when the user asks everything to live under one folder:
- `01 Categories/`
- `02 Links/`
- `03 Domains/`
- `00 Reports/`
- `Dashboard.md`
- `_state/` containing:
  - `state.json`
  - `latest-summary.json`
  - `pending_annotations.json`
  - `excluded_links.json`

Behavior:
- `01 Categories/` mirrors the HTML folder structure with `Index.md` files.
- `02 Links/` is a small set of shard files, not one file per URL.
- `03 Domains/` is a small set of lightweight shard files, not one file per host.
- `01 Categories/` should use a flattened category-note layout in compact mode: top-level category folders plus branch notes, not thousands of nested folders.
- `00 Reports/` contains `New Links.md`, `Changed Links.md`, `Removed Links.md`, and `Excluded Links.md`.
- `Excluded Links.md` records links filtered out as obvious noise so the cleanup stays auditable.
- compact-layout sync state should live outside the vault/archive to avoid Obsidian indexing large machine-state files.
- if the user asks for a single-folder archive, move the machine-state directory inside the archive instead of using a sibling `-state` directory.
- after every write, verify the archive top level contains only the canonical managed paths plus `_state/`; suffix copies such as `01 Categories 2`, `03 Domains 2`, or `Dashboard 2.md` are conflict artifacts and should be removed.
- `Dashboard.md` should include a compact principal-category overview for quick review.
- Index files should be outline-friendly in Obsidian: keep grouping headings such as `## host`, and render each web entry as its own heading block such as `### page title` instead of a plain bullet list.
- Compact category notes should preserve the original hierarchy as headings inside notes rather than as deeply nested filesystem folders.
- Stdout and `state-root/latest-summary.json` should stay compact; detailed URL lists belong in the Markdown reports, not the terminal summary.

Legacy `per-url` layout is optional and should only be used when the user explicitly wants one Markdown file per URL and accepts the indexing cost.

## Workflow

1. Confirm the HTML path and target root.
   The target root may be absolute or relative, but it must be explicit or safely inferable.
2. Confirm the layout.
   Use `compact` by default. Use `per-url` only if the user explicitly wants one note per URL.
3. Run the sync script in `merge` mode unless the user explicitly wants a rebuild.
4. Read the JSON summary from stdout or `state-root/latest-summary.json`.
   The summary should surface counts, the collapsed summary-root path, and principal categories.
5. If `pending_annotations > 0`, fill descriptions only for those pending URLs.
6. Re-run the sync script with `--annotations-file`.
7. Verify that the generated Markdown reflects the updated HTML and that preserved descriptions were not lost.
8. For single-folder archives in iCloud/Obsidian, verify the top level contains only `00 Reports/`, `01 Categories/`, `02 Links/`, `03 Domains/`, `Dashboard.md`, and `_state/`.

Health-check command:
```bash
python3 scripts/check_bookmark_archive.py \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

## External Import Into Existing Archive

Use a dedicated external-import flow when the user says a new outside HTML file should be added into an existing archive such as `Bookmarks`.

Rules:
- treat the existing archive as the canonical source of truth for URLs already present
- do not let duplicate URLs from the external HTML overwrite or extend the existing category paths
- only import URLs that are new relative to the existing archive state
- classify new URLs by learning category-path mappings from duplicate URLs already present in both sources
- if a small number of URLs still cannot be mapped automatically, prefer a tiny explicit override rule over letting duplicate categories leak in
- after import, verify there are no top-level conflict copies with suffixes like ` 2` or ` 3`

Do not use the plain sync `merge` workflow for this case, because it can update category paths on duplicate URLs.

## Gradual Annotation

For large archives, annotate in batches instead of trying to describe everything in one pass.

Recommended strategy:
- work one category branch at a time
- start with a small branch to validate the wording style and sync loop
- keep each batch small enough to review comfortably

Use the batch filter helper:
```bash
python3 scripts/filter_pending_annotations.py \
  --pending-json "/path/to/state-root/pending_annotations.json" \
  --category-prefix "Research/AI Tools" \
  --output "/path/to/batches/ai-tools.json"
```

Then fill `description`, optional `note`, and optional `tags` in that batch file and re-run the main sync with `--annotations-file`.

## Bulk Autofill

When the user explicitly wants everything filled without waiting for review, use the autofill helper to generate first-pass descriptions for every remaining pending URL:

```bash
python3 scripts/autofill_annotations.py \
  --pending-json "/path/to/state-root/pending_annotations.json" \
  --output "/path/to/batches/autofill-all.json"
```

Then sync it back:

```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "HTML Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh \
  --annotations-file "/path/to/batches/autofill-all.json"
```

Use this only when the user clearly prefers speed over manual review, because these descriptions are heuristic first-pass summaries rather than hand-verified notes.

## Description Rules

For each pending URL:
- Keep the explanation short and practical.
- Prefer a one-sentence purpose statement.
- Use the HTML category path, page title, and domain as the first-pass evidence.
- Browse the URL only when the title/domain/category is too vague to infer the page's purpose reliably.
- Do not change the HTML category structure just because you would classify it differently yourself.

Good description examples:
- `OpenAI 的研究主页，用来查看最新研究项目、论文和技术进展。`
- `GitHub Actions 的产品页，用来了解 CI/CD 自动化能力和典型工作流。`

## Incremental Rules

- `merge` mode preserves old descriptions, notes, and tags.
- A URL missing from a later HTML export is marked as removed and listed in `Removed Links.md`.
- A new URL appears in `New Links.md` and `state-root/pending_annotations.json` until described.
- If the same URL appears in multiple HTML folders, keep one URL note and preserve all category paths on that note.

## Noise Filtering

Apply these noise filters by default before rendering:
- browser-internal schemes such as `chrome-extension://`
- separator hosts such as `separator.site` and `separator.mayastudios.com`
- separator-style titles made only of divider characters

Filtered links should:
- be excluded from main category, link, and domain indexes
- appear in `Excluded Links.md`
- be recorded in `state-root/excluded_links.json`
- not be counted as user-removed links in later `merge` runs

## Commands

First sync or later incremental sync:
```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "HTML Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh
```

Single-folder compact example:
```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

External HTML import into existing `Bookmarks`:
```bash
python3 scripts/import_external_bookmark_html.py \
  --input-html "/path/to/external-bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --title-language zh \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

Post-run structure check:
```bash
python3 scripts/check_bookmark_archive.py \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

Relative-path example:
```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "./exports/bookmarks.html" \
  --target-root "./notes" \
  --container-name "网页聚合" \
  --layout compact \
  --mode merge \
  --title-language zh
```

Import descriptions for pending URLs and re-render:
```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "HTML Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh \
  --annotations-file "/path/to/annotations.json"
```

Full rebuild from the latest HTML only:
```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "HTML Bookmarks" \
  --layout compact \
  --mode create \
  --title-language zh
```

Legacy per-URL layout:
```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "HTML Bookmarks" \
  --layout per-url \
  --mode merge \
  --title-language zh
```

## Annotation Template

Use `.sync-state/pending_annotations.json` as the working template.

Expected shape:
- `url`
- `title`
- `host`
- `category_paths`
- `description`
- `note`
- `tags`

An example file lives at:
`references/annotations.example.json`

## Validation Checklist

After each run, ensure:
1. `Dashboard.md` exists and shows the latest counts.
2. `pending_annotations` matches the size of the external `pending_annotations.json`.
3. Filtered noise links appear only in `Excluded Links.md`, not in the main indexes.
4. New HTML exports only create pending entries for genuinely new or still-undescribed URLs.
5. Existing descriptions survive later `merge` runs.
6. Category indexes still match the HTML folder structure.
