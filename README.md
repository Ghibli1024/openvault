# openvault

[![README-English](https://img.shields.io/badge/README-English-2d6cdf?style=for-the-badge)](README.md)
[![README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87](https://img.shields.io/badge/README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-555555?style=for-the-badge)](README.zh-CN.md)
[![Local-first](https://img.shields.io/badge/local--first-private-2F7A5D?style=for-the-badge)](#privacy-and-safety)

`openvault` is a local-first agent skill that turns browser bookmarks and social favorites into one Obsidian-ready Markdown resources library.

It is for people who do not want four disconnected export piles. Give your agent a bookmark HTML export, Xiaohongshu HTML export, local Bilibili favorites, or X likes JSON; `openvault` routes the job, preserves your local taxonomy when it exists, and writes the result into a durable Markdown archive.

```text
Bookmarks / Xiaohongshu / Bilibili / X
        -> openvault
        -> <resources-root>/{书签,小红书,B站,X,搜索,废弃}
```

[Install](#install) · [Use it](#use-it) · [Supported sources](#supported-sources) · [Output preview](#output-preview) · [Develop](#develop)

---

## Install

Install the skill with the open agent skills CLI:

```bash
npx skills add Ghibli1024/openvault -g -a codex
```

Useful variants:

```bash
# List what the repository exposes before installing
npx skills add Ghibli1024/openvault --list

# Install for every detected compatible agent
npx skills add Ghibli1024/openvault --all
```

Restart Codex or your target agent after installation so the new `openvault` skill is discovered.

## Use It

Ask naturally:

```text
Use openvault to import this bookmarks HTML into <resources-root>.
Use openvault to sync my Bilibili favorites into <resources-root>.
Use openvault to import these Xiaohongshu favorites and likes HTML files.
Use openvault to import this X likes JSON.
Use openvault to search "AI design tools" across <resources-root>.
Use openvault to clean the rubbish queue under <resources-root>.
```

The root [SKILL.md](SKILL.md) is the only agent entry. Source-specific details live under `sources/*/WORKFLOW.md` and are loaded only after routing.

## Supported Sources

| Source | Input | Main output | Best for |
|---|---|---|---|
| Bookmarks | Netscape-style browser bookmark HTML from Chrome, Edge, Firefox, or similar exporters | `书签/` category tree with `ROOT分类目录.md` | Long-lived web resource library |
| Xiaohongshu | Exported favorites HTML and optional likes HTML | `小红书/` with date, author, source, taxonomy, coarse-category, and dashboard views | Inspiration, lifestyle, visual references |
| Bilibili | Current favorites from the local logged-in browser environment | `B站/` with date, uploader, folder, taxonomy, coarse-category, and dashboard views | Video resource library |
| X Likes | Likes JSON from an upstream exporter | `X/` with date, author, taxonomy, and dashboard views | Information-stream capture |

## Output Preview

`openvault` expects a shared resources root like this:

```text
<resources-root>/
├── 书签/
│   ├── ROOT分类目录.md
│   ├── Index.md
│   └── <taxonomy folders>/
├── 小红书/
│   ├── 01 日期/
│   ├── 02 作者/
│   ├── 03 来源/
│   ├── 04 领域/
│   ├── 05 粗分类/
│   └── Dashboard.md
├── B站/
│   ├── 01 日期/
│   ├── 02 UP主/
│   ├── 03 收藏夹/
│   ├── 04 领域/
│   ├── 05 粗分类/
│   └── Dashboard.md
├── X/
│   ├── 01 Date/
│   ├── 02 Author/
│   ├── 03 Domain/
│   └── Dashboard.md
├── 搜索/
└── 废弃/
```

Example sync summary shape:

```text
source: bookmarks
input: <path-to-export.html>
output: <resources-root>/书签
taxonomy: existing ROOT分类目录.md
mode: merge
created: 42
updated: 8
removed: 3
```

## Core Rules

### One Skill Entry

`openvault` exposes one root `SKILL.md`. It detects the source, then reads the matching source workflow:

- `sources/bookmarks/WORKFLOW.md`
- `sources/xhs/WORKFLOW.md`
- `sources/bilibili/WORKFLOW.md`
- `sources/x-likes/WORKFLOW.md`

### Preserve Local Taxonomy

When a target archive already has `ROOT分类目录.md`, treat it as the source of truth. Incoming exports can add evidence, but they should not silently replace the user's classification tree.

Precedence:

1. Explicit taxonomy or rules path from the user
2. Existing local archive `ROOT分类目录.md`
3. Source workflow default taxonomy fallback

### Global Search And Rubbish

Search and manual rubbish are shared at the resources-root level:

- `搜索/` stores cross-source search result notes.
- `废弃/` stores local editorial removal intent.

Manual rubbish is not the same as authoritative upstream deletion. If the user explicitly asks for a local-vs-cloud authoritative sync, a source workflow may remove missing items differently. Otherwise, `废弃/` remains the manual curation queue.

## Privacy And Safety

`openvault` is intentionally local-first.

- Repository examples use placeholders such as `<resources-root>` and `<path-to-export>`.
- Raw exports, generated notes, account names, URLs, and browsing history may be sensitive.
- Do not commit personal exports, generated archives, state files, or vault-specific absolute paths to a public repository unless you have sanitized them.
- Bookmark, Xiaohongshu, and X workflows operate on user-provided export files.
- The Bilibili workflow relies on the local logged-in browser environment instead of storing credentials in the repository.

## Repository Layout

```text
openvault/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── managed-archive-policy.md
│   └── taxonomy-policy.md
├── scripts/
│   ├── detect_source.py
│   ├── search_resources.py
│   └── vault_runtime.py
├── sources/
│   ├── bilibili/
│   ├── bookmarks/
│   ├── x-likes/
│   └── xhs/
└── tests/
```

Important files:

| Path | Purpose |
|---|---|
| `SKILL.md` | Single agent entry and router |
| `sources/*/WORKFLOW.md` | Source-specific operating instructions |
| `references/taxonomy-policy.md` | Shared taxonomy precedence |
| `references/managed-archive-policy.md` | Shared managed-archive cleanup expectations |
| `scripts/detect_source.py` | Lightweight source detection helper |
| `scripts/vault_runtime.py` | Shared resources-root path and migration helpers |
| `scripts/search_resources.py` | Cross-source Markdown search helper |

## Develop

Run the test suite with the standard-library runner:

```bash
GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main python3 -m unittest discover -s tests
python3 -m unittest discover -s sources/bookmarks/tests
python3 -m unittest discover -s sources/x-likes/tests
python3 -m unittest discover -s sources/xhs/tests
python3 -m unittest discover -s sources/bilibili/tests
```

Verify skill discovery:

```bash
npx skills add . --list
```

Expected result: one available skill named `openvault`.

## Limitations

- Supported inputs still depend on source-specific exporters or local browser state.
- The skill does not provide semantic RAG search by default.
- It does not normalize every source into an identical schema.
- Global `废弃/` semantics depend on later sync passes to remove items from generated source views.
