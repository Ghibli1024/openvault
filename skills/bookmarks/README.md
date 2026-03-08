# html-bookmarks-to-markdown

[![README-English](https://img.shields.io/badge/README-English-2d6cdf?style=for-the-badge)](README.md)
[![README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87](https://img.shields.io/badge/README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-555555?style=for-the-badge)](README.zh-CN.md)

Convert bookmark-style HTML exports into a local Markdown archive with preserved categories, compact indexes, incremental sync, and optional annotation workflows.

This repository contains both:

- a Codex skill definition (`SKILL.md`)
- standalone Python scripts for sync, annotation, import, and health checks

It is designed for Obsidian-friendly Markdown, but the output remains editor-agnostic.

## What It Does

Given a bookmark HTML export from a browser such as Chrome, Edge, Firefox, or a Netscape-style exporter, this tool can:

- parse bookmark entries and preserve category structure
- sync HTML exports into a local Markdown archive
- keep URL-level dedupe across future syncs
- keep compact indexes instead of one file per URL
- preserve descriptions, notes, and tags across merges
- generate pending-annotation templates for new URLs
- autofill first-pass descriptions for large archives
- import a second external HTML file into an existing archive without polluting duplicate URLs
- verify archive structure after each run

## Repository Layout

```text
html-bookmarks-to-markdown/
├── README.md
├── README.zh-CN.md
├── LICENSE
├── SKILL.md
├── .gitignore
├── agents/
│   └── openai.yaml
├── references/
│   └── annotations.example.json
└── scripts/
    ├── sync_bookmark_html.py
    ├── autofill_annotations.py
    ├── filter_pending_annotations.py
    ├── import_external_bookmark_html.py
    └── check_bookmark_archive.py
```

## Requirements

- Python 3
- a bookmark HTML export

No external Python packages are required.

## Main Workflows

### 1. Standard HTML sync

Use this when a bookmark HTML export is the source of truth and you want to build or update a Markdown archive.

Supports:

- `create`: rebuild from HTML only
- `merge`: preserve existing descriptions/history and sync incrementally

### 2. Gradual annotation

Use the pending-annotation output when you want to fill descriptions in batches.

Helpers included:

- `autofill_annotations.py`
- `filter_pending_annotations.py`

### 3. External HTML import into an existing archive

Use this when you already have a canonical archive such as `Bookmarks/` and want to import another outside HTML file.

Rules of this workflow:

- existing URLs remain the source of truth
- duplicate URLs are skipped
- only new URLs are imported
- new URLs are mapped into the existing category system by learning from duplicates already present in both sources

### 4. Archive health check

Use the structure checker to confirm the top-level archive shape is still correct after sync/import operations.

## Output Structure

Archive root:

```text
<target-root>/<container-name>/
```

### Compact layout

Generated user-facing structure:

```text
Bookmarks/
├── 00 Reports/
├── 01 Categories/
├── 02 Links/
├── 03 Domains/
├── Dashboard.md
└── _state/           # optional when using the single-folder variant
```

Typical machine-state files:

```text
state.json
latest-summary.json
pending_annotations.json
excluded_links.json
```

### Meaning of top-level paths

- `00 Reports/`
  Sync/import reports such as new, changed, removed, and excluded links.
- `01 Categories/`
  Main browsing entry grouped by bookmark categories.
- `02 Links/`
  URL-oriented shard indexes.
- `03 Domains/`
  Host/domain-oriented shard indexes.
- `Dashboard.md`
  Summary page with stats and navigation.
- `_state/`
  Machine state for incremental sync and health checks.

## Core Scripts

### `scripts/sync_bookmark_html.py`

Primary sync entry point for standard HTML-to-Markdown conversion.

Example:

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

### `scripts/autofill_annotations.py`

Generate heuristic first-pass descriptions for every remaining pending URL.

Example:

```bash
python3 scripts/autofill_annotations.py \
  --pending-json "/path/to/Bookmarks/_state/pending_annotations.json" \
  --output "/path/to/Bookmarks/_state/batches/autofill-all.json"
```

### `scripts/filter_pending_annotations.py`

Filter pending annotation items by category branch for smaller review batches.

Example:

```bash
python3 scripts/filter_pending_annotations.py \
  --pending-json "/path/to/Bookmarks/_state/pending_annotations.json" \
  --category-prefix "Research/AI Tools" \
  --output "/path/to/batches/ai-tools.json"
```

### `scripts/import_external_bookmark_html.py`

Import another HTML export into an existing archive while skipping duplicates and reusing the current category system.

Example:

```bash
python3 scripts/import_external_bookmark_html.py \
  --input-html "/path/to/external-bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --state-root "/path/to/archive-root/Bookmarks/_state" \
  --title-language zh
```

### `scripts/check_bookmark_archive.py`

Validate top-level archive structure and required state files.

Example:

```bash
python3 scripts/check_bookmark_archive.py \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

## Annotation Flow

Recommended loop for large archives:

1. run the sync script
2. inspect `pending_annotations.json`
3. either:
   - autofill everything for speed
   - or filter by branch for manual review
4. re-run the sync script with `--annotations-file`

Example annotation payload:

- [references/annotations.example.json](references/annotations.example.json)

## As a Codex Skill

The skill definition is:

- [SKILL.md](SKILL.md)

The agent registration config is:

- [agents/openai.yaml](agents/openai.yaml)

Typical agent workflow:

1. confirm the HTML path
2. confirm the target root
3. choose `merge` or `create`
4. choose layout (`compact` by default)
5. run sync
6. inspect summary JSON
7. fill pending annotations if needed
8. verify final structure

## Why the Structure Check Matters

When the archive lives in iCloud/Obsidian-style directories, top-level conflict copies such as:

- `01 Categories 2`
- `03 Domains 2`
- `Dashboard 2.md`

should be treated as invalid artifacts, not legitimate output.

This repo includes a health-check command and the sync/import flows are designed to keep the top level restricted to the canonical managed paths.

## Typical Usage Patterns

### First build

```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/output" \
  --container-name "Bookmarks" \
  --layout compact \
  --mode create \
  --title-language zh \
  --state-root "/path/to/output/Bookmarks/_state"
```

### Later incremental update

```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/new-bookmarks.html" \
  --target-root "/path/to/output" \
  --container-name "Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh \
  --state-root "/path/to/output/Bookmarks/_state"
```

### Import a second bookmark export into the same archive

```bash
python3 scripts/import_external_bookmark_html.py \
  --input-html "/path/to/external-bookmarks.html" \
  --target-root "/path/to/output" \
  --container-name "Bookmarks" \
  --title-language zh \
  --state-root "/path/to/output/Bookmarks/_state"
```

## Notes

- The archive is Markdown first. Obsidian is a strong target, not a hard dependency.
- Compact layout is the recommended default for large collections.
- Per-URL layout remains a legacy option for users who explicitly want one note per URL.
- The external-import flow is safer than plain merge when duplicate URLs should remain untouched.

## License

This project is licensed under the MIT License.

See:

- [LICENSE](LICENSE)
