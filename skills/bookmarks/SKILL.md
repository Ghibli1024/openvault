---
name: html-bookmarks-to-markdown
description: Convert bookmark-style HTML exports into a locally stored Markdown category tree driven by a user-owned taxonomy, prioritizing semantic classification from the chosen local taxonomy over the incoming HTML folder structure, with a built-in default taxonomy for new users and minimal state for future syncs.
---

# HTML Bookmarks Markdown Sync

## Overview

Use this skill when the user provides a bookmark-style HTML export and wants a Markdown bookmark archive whose primary output is a category tree.

The default workflow is now `categories-only`:
- classify links by a local reference Markdown taxonomy,
- render only category folders and `Index.md` files,
- keep minimal external state for future syncs,
- optimize for Obsidian indexing and search stability instead of feature breadth.

Taxonomy bootstrap rules:
- the working taxonomy file is named `ROOT分类目录.md`
- if the archive already has `ROOT分类目录.md`, use it by default on later runs
- if the user starts from an empty folder, first generate a candidate `ROOT分类目录.md` from the HTML tree
- then ask whether to keep that generated file or replace it with the built-in template
- the built-in template lives at `references/default_root_taxonomy.md`
- if the workflow must proceed non-interactively and no taxonomy file exists yet, fall back to the built-in template and write it into `ROOT分类目录.md`

Important classification rule:
- do **not** trust the incoming HTML folder structure as the primary classifier
- use the local taxonomy as the source of truth
- use page title, domain, URL tokens, and taxonomy semantics to infer meaning
- only reuse the HTML category path as a weak hint when it aligns closely with the local taxonomy

Legacy `full` mode still exists for compatibility, but it is no longer the recommended path.

## Defaults

Assume these unless the user asks otherwise:
- archive profile: `categories-only`
- taxonomy source: auto-detected `ROOT分类目录.md` when available
- taxonomy scope: `full`
- unmatched policy: `nearest`
- display category source: `reference`
- mode: `merge`
- title language: `zh`
- state root: `<container>/_state/`

`categories-only` output:
- `<target-root>/<container-name>/Index.md`
- `<target-root>/<container-name>/ROOT分类目录.md`
- `<target-root>/<container-name>/<一级主类>/.../Index.md`
- `<target-root>/<container-name>/_state/` containing:
  - `state.json`
  - `latest-summary.json`
  - `Index.md`

`categories-only` behavior:
- do not create `01 Categories/`
- do not create `02 Links/`
- do not create `03 Domains/`
- do not create `00 Reports/`
- do not create `Dashboard.md`
- do not create `pending_annotations.json`
- do not create `excluded_links.json`
- each directory gets an `Index.md`
- container root directly contains the primary category folders plus a root `Index.md`
- each `Index.md` lists only direct child categories and direct links
- link rows use a compact format such as `- [标题](URL) · \`host\``
- classification should prefer semantic matching against the local taxonomy tree
- HTML source folders should only influence placement when they are highly consistent with the local taxonomy
- root `Index.md` contains a `# 手动` section where the user can paste one URL per line
- on the next sync run, those manual URLs are classified and merged into the library, then removed from the `# 手动` list

Legacy `full` mode:
- keeps the older reports, link shards, domain indexes, and dashboard
- should only be used when the user explicitly wants the old archive shape

## Interaction Style

When the skill is triggered, use a short one-question-at-a-time flow by default.

Collect or confirm:
1. `input-html`
2. archive location
3. taxonomy reference Markdown
4. whether to keep default `archive-profile=categories-only`
5. whether to keep default `mode=merge`
6. final execution confirmation

If the user points to an existing archive and wants `merge`, inspect it first and preserve its established taxonomy unless they explicitly ask for a rewrite.

Every time this skill is used, tell the user which taxonomy source will be used:
- if `ROOT分类目录.md` already exists, say it will be used by default
- if it does not exist, say you will first create a candidate `ROOT分类目录.md` from the HTML and then let them choose between that candidate and the built-in template

## Required User Decision

Before running, confirm:
- where the archive should live
- which Markdown file is the classification reference

`target-root` rules:
- accept an absolute or relative path
- resolve relative paths against the current working directory
- if the user gives the final archive folder, normalize it into `target-root=<parent>` and `container-name=<basename>`
- do not guess ambiguous paths

The taxonomy reference should normally be one of:
- an AI-outline taxonomy note such as `ROOT分类目录.md` with `FORMAT: AI_OUTLINE_V1`
- fallback: a folder index note with `## 根目录` and `## 全路径检索索引`

Reference priority rules:
- if the archive already has `ROOT分类目录.md`, treat it as the source of truth on later runs
- if only a folder index exists, use that as a structural fallback
- do not let the new HTML export override the user's established taxonomy
- if no taxonomy file exists yet:
  - first generate `ROOT分类目录.md` from the HTML categories
  - ask the user whether to keep that generated file as the initial template or replace it with the built-in template
  - if they choose the built-in template, write `references/default_root_taxonomy.md` into `ROOT分类目录.md`

## Output Contract

For the default `categories-only` profile, the generated archive lives at:
`<target-root>/<container-name>/`

Expected top level:
- `Index.md`
- `ROOT分类目录.md`
- one directory per primary category from the taxonomy reference

Expected external state root:
- `state.json`
- `latest-summary.json`

`categories-only` mapping rules:
- strip legacy roots such as `书签工具栏 / 资源书签 / 历史书签根`
- treat `ROOT` as the logical root only, not a disk folder
- prefer semantic classification against the local taxonomy tree
- use title, domain, URL tokens, aliases, and node scope text as the main evidence
- reuse incoming HTML category names only as weak hints
- if semantic confidence is strong, place the link directly into the inferred taxonomy path even if the HTML folder disagrees
- if matching stops at a parent, attach the remaining source subtree under the nearest matched parent

Example:
- if a page is about “AI 帮用户预览沙发放进客厅后的效果”, it should go under `人工智能 / 图像生成 / 室内设计与空间渲染`
- this remains true even if the incoming HTML placed it under an unrelated folder

## Workflow

1. Confirm the HTML path, archive location, and taxonomy reference Markdown.
2. If `ROOT分类目录.md` already exists, use it as the default taxonomy.
3. If it does not exist, first generate a candidate `ROOT分类目录.md` from the incoming HTML.
4. Ask the user whether to keep the generated candidate or replace it with `references/default_root_taxonomy.md`.
5. Strip legacy bookmark roots and classify each bookmark semantically into the chosen taxonomy.
6. Read any URLs under the root `# 手动` section, classify them too, then clear that list.
7. Render only category directories with `Index.md` files.
8. Write minimal external state.
9. Validate with `check_bookmark_archive.py --archive-profile categories-only`.

Health-check command:
```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/check_bookmark_archive.py \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --state-root "/path/to/state-root" \
  --archive-profile categories-only
```

Legacy full-mode command:
```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --archive-profile full \
  --layout compact \
  --mode merge \
  --title-language zh
```

## Legacy Full-Mode Notes

The sections below describe older `full`-mode workflows such as external import, pending annotations, autofill, and report-heavy syncs. They are still useful when the user explicitly asks for the old archive shape, but they are no longer the default operating mode of this skill.

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
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/filter_pending_annotations.py \
  --pending-json "/path/to/state-root/pending_annotations.json" \
  --category-prefix "书签工具栏/资源书签/项目分支" \
  --output "/path/to/batches/project-branch.json"
```

Then fill `description`, optional `note`, and optional `tags` in that batch file and re-run the main sync with `--annotations-file`.

## Bulk Autofill

When the user explicitly wants everything filled without waiting for review, use the autofill helper to generate first-pass descriptions for every remaining pending URL:

```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/autofill_annotations.py \
  --pending-json "/path/to/state-root/pending_annotations.json" \
  --output "/path/to/batches/autofill-all.json"
```

Then sync it back:

```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/sync_bookmark_html.py \
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
- when merging into an existing archive, preserve the existing archive's language, folder naming, category organization, and report structure unless the user explicitly requests a rewrite
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
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "HTML Bookmarks" \
  --layout compact \
  --mode merge \
  --title-language zh
```

Single-folder compact example:
```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/sync_bookmark_html.py \
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
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/import_external_bookmark_html.py \
  --input-html "/path/to/external-bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --title-language zh \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

Post-run structure check:
```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/check_bookmark_archive.py \
  --target-root "/path/to/archive-root" \
  --container-name "Bookmarks" \
  --state-root "/path/to/archive-root/Bookmarks/_state"
```

Relative-path example:
```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/sync_bookmark_html.py \
  --input-html "./exports/bookmarks.html" \
  --target-root "./notes" \
  --container-name "网页聚合" \
  --layout compact \
  --mode merge \
  --title-language zh
```

Import descriptions for pending URLs and re-render:
```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/sync_bookmark_html.py \
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
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/sync_bookmark_html.py \
  --input-html "/path/to/bookmarks.html" \
  --target-root "/path/to/archive-root" \
  --container-name "HTML Bookmarks" \
  --layout compact \
  --mode create \
  --title-language zh
```

Legacy per-URL layout:
```bash
python3 /Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts/sync_bookmark_html.py \
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
