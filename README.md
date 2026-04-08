# openvault

[![README-English](https://img.shields.io/badge/README-English-2d6cdf?style=for-the-badge)](README.md)
[![README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87](https://img.shields.io/badge/README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-555555?style=for-the-badge)](README.zh-CN.md)

`openvault` is a local-first Codex plugin for turning bookmark exports and social favorites into a structured Markdown resources library.

It is designed for a single visible plugin entry plus a small set of internal canonical workflows:

- one visible router skill: `archive-router`
- four internal canonical source skills:
  - `bookmarks`
  - `xhs`
  - `bilibili`
  - `x-likes`

The plugin's current operating model is:

- one visible entry in the Codex UI
- one shared resources root
- source-specific sync/import engines underneath
- global `search/` and `rubbish/` behavior across sources

## What The Plugin Does

`openvault` is for people who want one resources library instead of a pile of unrelated exports.

Given supported source inputs, it can:

- import browser bookmark HTML into a Markdown archive
- sync Xiaohongshu favorites or likes exports into Markdown
- sync Bilibili favorites into Markdown
- sync X likes JSON exports into Markdown
- keep source-specific browsing views where useful
- apply existing taxonomy notes instead of replacing them silently
- write search results into a shared global search folder
- use a shared global rubbish folder as the manual removal queue
- keep the whole workflow local to your machine and vault

## Current Information Architecture

The plugin assumes a shared resources root similar to:

```text
<resources-root>/
├── 书签/
├── 小红书/
├── B站/
├── X/
├── 搜索/
└── 废弃/
```

The four source roots keep their source-specific main views. For example:

- `书签/` keeps the bookmark archive layout and taxonomy files
- `小红书/` keeps date, author, source, taxonomy, coarse-category, and dashboard views
- `B站/` keeps date, uploader, folder, taxonomy, coarse-category, and dashboard views
- `X/` keeps date, author, taxonomy, and dashboard views

The global roots are intentionally shared:

- `搜索/`
  Stores cross-source search result notes
- `废弃/`
  Stores manual removal notes, raw URLs, or moved notes that should be filtered out from later sync output

## Supported Inputs

### Bookmarks

Input:

- bookmark-style HTML exports from browsers such as Chrome, Edge, Firefox, or similar Netscape-style exporters

Output:

- a Markdown archive under `书签/`
- local taxonomy-driven category structure
- compact category browsing optimized for vault use

### Xiaohongshu

Input:

- exported HTML files for favorites and optionally likes

Output:

- a Markdown archive under `小红书/`
- date, author, source, taxonomy, coarse-category, and dashboard views

### Bilibili

Input:

- current Bilibili favorites from the local logged-in browser environment

Output:

- a Markdown archive under `B站/`
- date, uploader, folder, taxonomy, coarse-category, and dashboard views

### X Likes

Input:

- exported likes JSON from an upstream exporter

Output:

- a Markdown archive under `X/`
- date, author, taxonomy, and dashboard views

## Core Behaviors

### 1. Single Visible Entry

The Codex UI should expose only one visible plugin entry:

- `archive-router`

That entry is responsible for routing import, sync, search, and rubbish-cleanup requests to the correct canonical workflow.

### 2. Source-Specific Sync, Shared Library Semantics

The plugin does not force all sources into one identical disk layout.

Instead:

- source-specific engines keep the views that are useful for that source
- shared rules apply at the resources-root level

Examples of shared rules:

- search results belong in the shared `搜索/`
- manual removal intent belongs in the shared `废弃/`
- implicit full-library search should search across all source roots

### 3. Manual Rubbish vs. Upstream Deletion

`openvault` distinguishes between two different deletion meanings:

- manual rubbish
  A local editorial decision. A note or URL placed in the global `废弃/` should be filtered out from later generated views.
- authoritative upstream deletion
  When a user explicitly asks for a local-vs-cloud authoritative sync, missing local items may be moved to the operating system trash instead of being written into the shared `废弃/`.

This distinction exists so the shared `废弃/` folder stays a manual curation queue rather than a catch-all for every sync diff.

### 4. Taxonomy Preservation

The plugin tries to preserve an archive's existing taxonomy whenever that taxonomy already exists locally.

Typical behavior:

- keep a local `ROOT分类目录.md` when present
- prefer an existing local archive taxonomy over silently inventing a parallel one
- use source-specific defaults only when no local taxonomy exists

## Privacy And Safety

This plugin is intentionally local-first.

### Privacy principles

- examples in this repository use placeholders such as `<resources-root>` and `<path-to-export>`
- personal vault paths should not be hardcoded into documentation or scripts unless a local runtime needs them internally
- raw exports, personal favorites, and generated notes may contain sensitive interests, account names, URLs, and browsing history
- keep the resources library on storage you control
- do not commit personal exports, generated archives, or state files into a public repository unless intentionally sanitized

### Credential handling

- bookmark, Xiaohongshu, and X workflows operate on user-provided export files
- the Bilibili workflow relies on the local logged-in browser environment instead of asking you to paste credentials into the repository
- the repository itself is not meant to store account secrets

### Cache refresh safety

The local cache refresh script updates Codex's cached plugin clone and reports:

- cache commit before refresh
- cache commit after refresh
- target commit
- visible skill count

This helps verify plugin visibility changes without exposing personal vault paths in the README.

## Repository Layout

```text
openvault/
├── .codex-plugin/
│   └── plugin.json
├── README.md
├── README.zh-CN.md
├── references/
│   ├── managed-archive-policy.md
│   └── taxonomy-policy.md
├── scripts/
│   ├── detect_source.py
│   ├── refresh_openvault_cache.py
│   ├── search_resources.py
│   └── vault_runtime.py
├── skills/
│   ├── archive-router/
│   ├── bilibili/
│   ├── bookmarks/
│   ├── x-likes/
│   └── xhs/
└── tests/
```

### Important files

- `.codex-plugin/plugin.json`
  Plugin metadata and visible UI behavior
- `scripts/detect_source.py`
  Lightweight source detection helper used by the router
- `scripts/vault_runtime.py`
  Shared runtime for resources-root migration, global search/rubbish handling, and shared path rules
- `scripts/search_resources.py`
  Global cross-source search helper
- `scripts/refresh_openvault_cache.py`
  Explicit local Codex cache refresh helper

## How To Use The Plugin

### In Codex UI

Use the single visible `openvault` entry for requests like:

- import a bookmarks HTML export into the resources root
- sync Xiaohongshu favorites into the resources root
- sync Bilibili favorites into the resources root
- import X likes JSON into the resources root
- search across the whole resources library
- clean up the shared rubbish folder

### Typical requests

Examples of the kind of requests the router is designed to understand:

- import bookmarks HTML into `<resources-root>`
- sync Bilibili favorites into `<resources-root>`
- import Xiaohongshu favorites into `<resources-root>`
- import X likes JSON into `<resources-root>`
- search `AI design tools` in `<resources-root>`
- clean up the rubbish queue under `<resources-root>`

## Refreshing The Local Codex Cache

If Codex UI still shows stale skill entries after the repository is updated, refresh the local cache clone explicitly.

Dry run:

```bash
python3 scripts/refresh_openvault_cache.py --dry-run
```

Actual refresh:

```bash
python3 scripts/refresh_openvault_cache.py
```

The script reports:

- whether the plugin is enabled in `~/.codex/config.toml`
- source repo commit
- cache clone commit before refresh
- target commit
- whether a refresh was needed
- visible skill count after refresh

This is the intended workflow when the local UI appears out of sync with the repository.

## Development Notes

The plugin intentionally keeps the canonical source workflows separate instead of forcing everything into one monolithic engine.

That tradeoff is deliberate:

- the visible UX remains simple
- source-specific sync logic can still evolve independently
- shared runtime rules stay centralized

## Limitations

- supported inputs still depend on source-specific exporters or local browser state
- the plugin does not attempt to normalize every source into an identical schema
- the plugin does not provide semantic RAG search by default
- the shared `废弃/` semantics depend on later sync passes to remove items from generated source views

## Historical Note

Historical source repositories and older workflow shapes are being retained temporarily as migration background while `openvault` becomes the canonical plugin home.
