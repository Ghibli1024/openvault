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

## Installation

This repository is intentionally zero-dependency (Python stdlib only). Clone or download it, then run the scripts directly:

```bash
python3 scripts/sync_bookmark_html.py --help
```

Optional: use a virtual environment if you prefer isolating Python tooling, but it is not required.

## Quick Start

1. Export bookmarks from your browser as an HTML file (Chrome/Edge/Firefox all support a bookmark HTML export; the format is typically Netscape-style).
2. Run an initial build:

```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --layout compact \
  --mode create
```

3. Open the generated `Dashboard.md` under `<target-root>/<container-name>/` and browse from there.
4. For later updates, re-export the HTML and use `--mode merge` (the default) to preserve existing descriptions/history.

## Main Workflows

### 1. Standard HTML sync

Use this when a bookmark HTML export is the source of truth and you want to build or update a Markdown archive.

Supports:

- `create`: rebuild from HTML only
- `merge`: preserve existing descriptions/history and sync incrementally

Two flags that matter in practice:

- `--missing-policy keep|remove` (default: `keep`)
  In `merge` mode, `keep` retains prior links that are missing from the new HTML export. Use `remove` only if you treat the HTML file as a complete snapshot and want deletions applied.
- `--archive-profile full|categories-only` (default: `full`)
  `full` generates the dashboard, reports, and shard indexes described below. `categories-only` renders only nested category folders (useful if you want the smallest possible footprint).

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

Note: the exact structure depends on `--archive-profile` and `--layout`. The sections below describe the default `--archive-profile full` + `--layout compact` output.

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

Tip: most options are discoverable via `--help`, and `--state-root` is optional. If you do set it, keep it stable across runs because it stores incremental sync state (`state.json`, summaries, pending annotations, etc.).

Example:

```bash
python3 scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh \
  --state-root "/path/to/archive-root/Bookmarks/_state" \
  --missing-policy keep
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

## Privacy

This is a local-first workflow: the scripts read your exported HTML and write Markdown/JSON files to disk. There is no network access, telemetry, or external service dependency in the default workflows.

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

## Troubleshooting

- If you see unexpected deletions after a merge, check whether `--missing-policy remove` was used. The default `keep` is safer when your exported HTML is incomplete.
- If incremental sync behaves oddly, verify that you are reusing the same `--state-root` across runs, or let the script pick its default and keep that directory intact.
- If the archive lives in a sync folder (iCloud/Dropbox/OneDrive), run the structure check after syncs to catch conflict copies early (for example `Dashboard 2.md` or `01 Categories 2/`).
- When in doubt, run the script with `--help` and reduce to the minimal flags (`--input-html`, `--target-root`) to confirm the environment is sound.

## Contributing

Issues and PRs are welcome. If you report a bug, it helps to include:

- which script you ran and the exact CLI flags
- the `latest-summary.json` (and other state files) from the archive `_state/` folder
- a minimal sanitized HTML export snippet if possible

## License

This project is licensed under the MIT License.

See:

- [LICENSE](LICENSE)
