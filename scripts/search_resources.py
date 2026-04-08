#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import vault_runtime


@dataclass
class SearchMatch:
    source_name: str
    rel_path: Path
    title: str
    body: str
    frontmatter: dict[str, str]


def parse_frontmatter(note_path: Path) -> tuple[dict[str, str], str]:
    return vault_runtime.parse_frontmatter(note_path.read_text(encoding="utf-8", errors="ignore"))


def sanitize_filename(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]', " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "search"


def load_source_matches(resources_root: Path, source_name: str) -> List[SearchMatch]:
    matches: List[SearchMatch] = []
    for note_path in vault_runtime.iter_searchable_notes(resources_root, source_name):
        frontmatter, body = parse_frontmatter(note_path)
        title = frontmatter.get("title") or note_path.stem
        matches.append(
            SearchMatch(
                source_name=source_name,
                rel_path=note_path.relative_to(resources_root),
                title=title,
                body=body,
                frontmatter=frontmatter,
            )
        )
    return matches


def load_rubbish_matches(resources_root: Path, source_name: Optional[str] = None) -> List[SearchMatch]:
    rubbish_root = vault_runtime.global_rubbish_root(resources_root)
    if not rubbish_root.exists():
        return []

    matches: List[SearchMatch] = []
    for note_path in rubbish_root.rglob("*.md"):
        frontmatter, body = parse_frontmatter(note_path)
        sources = vault_runtime.note_candidate_sources(resources_root, note_path)
        if source_name and source_name not in sources:
            continue
        matches.append(
            SearchMatch(
                source_name="废弃",
                rel_path=note_path.relative_to(resources_root),
                title=frontmatter.get("title") or note_path.stem,
                body=body,
                frontmatter=frontmatter,
            )
        )
    return matches


def search_resources(resources_root: Path, query: str, source_name: Optional[str] = None) -> List[SearchMatch]:
    resources_root = resources_root.expanduser().resolve()
    terms = [term.lower() for term in query.split() if term.strip()]
    if not terms:
        return []

    candidate_sources = [source_name] if source_name else ["书签", "小红书", "B站", "X"]
    matches: List[SearchMatch] = []
    for candidate in candidate_sources:
        if candidate is None:
            continue
        matches.extend(load_source_matches(resources_root, candidate))
    matches.extend(load_rubbish_matches(resources_root, source_name))

    filtered: List[SearchMatch] = []
    for match in matches:
        haystack = "\n".join(
            [
                match.title,
                match.rel_path.as_posix(),
                "\n".join(f"{key}: {value}" for key, value in sorted(match.frontmatter.items())),
                match.body,
            ]
        ).lower()
        if all(term in haystack for term in terms):
            filtered.append(match)
    return filtered


def write_search_note(resources_root: Path, query: str, matched: List[SearchMatch], source_name: Optional[str] = None) -> Path:
    resources_root = resources_root.expanduser().resolve()
    search_root = vault_runtime.global_search_root(resources_root)
    search_root.mkdir(parents=True, exist_ok=True)
    scope = source_name or "全部资源"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"{datetime.now().strftime('%Y-%m-%d')} - {scope} - {query}"
    output = vault_runtime.unique_flat_file_path(search_root, f"{sanitize_filename(title)}.md", scope, None)

    lines = [
        "---",
        f'query: "{query}"',
        f'count: {len(matched)}',
        f'scope: "{scope}"',
        "---",
        "",
        f"# {scope} 搜索结果",
        "",
        f"- 检索词：`{query}`",
        f"- 范围：`{scope}`",
        f"- 生成时间：`{timestamp}`",
        f"- 命中数量：`{len(matched)}`",
        "",
        "## 结果",
        "",
    ]

    for item in matched:
        lines.append(f"- [{item.source_name}] [[{item.rel_path.as_posix()}|{item.title}]]")
        source_url = item.frontmatter.get("canonical_url") or item.frontmatter.get("source") or item.frontmatter.get("video_url") or item.frontmatter.get("url")
        if source_url:
            lines.append(f"  链接：{source_url}")
    lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search openvault resources and write the result note into the global 搜索 root.")
    parser.add_argument("--resources-root", required=True, help="Resources root containing 书签/小红书/B站/X")
    parser.add_argument("--query", required=True, help="Search terms")
    parser.add_argument("--source-name", help="Optional source name to limit results")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resources_root = Path(args.resources_root).expanduser().resolve()
    matched = search_resources(resources_root, query=args.query, source_name=args.source_name)
    output = write_search_note(resources_root, query=args.query, matched=matched, source_name=args.source_name)
    print(f"results={len(matched)}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
