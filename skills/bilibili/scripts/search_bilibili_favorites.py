#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DATE_DIRNAME = "01 日期"
SEARCH_DIRNAME = "06 搜索"


@dataclass
class SearchRecord:
    title: str
    rel_path: Path
    record_id: str
    bvid: str
    up_name: str
    fav_time: str
    folders: str
    domain: str
    source: str
    content: str


def parse_frontmatter(note_path: Path) -> Tuple[Dict[str, Any], str]:
    text = note_path.read_text(encoding="utf-8", errors="ignore")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    values: Dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key or not raw_value:
            continue
        try:
            import json

            values[key] = json.loads(raw_value)
        except Exception:
            values[key] = raw_value.strip('"').strip("'")
    return values, text[match.end() :]


def sanitize_filename(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]', " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "search"


def load_records(archive_root: Path) -> List[SearchRecord]:
    date_root = archive_root / DATE_DIRNAME
    records: List[SearchRecord] = []
    for note in date_root.rglob("*.md"):
        if note.name == "Index.md":
            continue
        frontmatter, body = parse_frontmatter(note)
        record_id = str(frontmatter.get("record_id", "")).strip()
        if not record_id:
            continue
        folders = frontmatter.get("folder_names", [])
        domain_parts = frontmatter.get("domain_parts", [])
        video_url = str(frontmatter.get("video_url", "")).strip()
        records.append(
            SearchRecord(
                title=str(frontmatter.get("title") or note.stem),
                rel_path=note.relative_to(archive_root),
                record_id=record_id,
                bvid=str(frontmatter.get("bvid", "")),
                up_name=str(frontmatter.get("up_name", "")),
                fav_time=str(frontmatter.get("fav_time", "")),
                folders=" / ".join(folders) if isinstance(folders, list) else str(folders),
                domain=" / ".join(domain_parts) if isinstance(domain_parts, list) else str(domain_parts),
                source=video_url,
                content=body,
            )
        )
    return records


def match_records(records: List[SearchRecord], query: str) -> List[SearchRecord]:
    terms = [term.lower() for term in query.split() if term.strip()]
    if not terms:
        return []
    matched: List[SearchRecord] = []
    for record in records:
        haystack = "\n".join(
            [
                record.title,
                record.bvid,
                record.up_name,
                record.folders,
                record.domain,
                record.source,
                record.content,
            ]
        ).lower()
        if all(term in haystack for term in terms):
            matched.append(record)
    return sorted(matched, key=lambda item: (item.fav_time, item.record_id), reverse=True)


def unique_output_path(search_root: Path, base_name: str) -> Path:
    candidate = search_root / f"{base_name}.md"
    counter = 2
    while candidate.exists():
        candidate = search_root / f"{base_name} ({counter}).md"
        counter += 1
    return candidate


def write_search_note(archive_root: Path, query: str, matched: List[SearchRecord], note_title: str | None = None) -> Path:
    search_root = archive_root.parent / "搜索"
    search_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = note_title or f"{datetime.now().strftime('%Y-%m-%d')} - {query}"
    output_path = unique_output_path(search_root, sanitize_filename(title))

    lines = [
        "---",
        f'query: "{query}"',
        f"count: {len(matched)}",
        'tags: ["bilibili-favorite", "search-result"]',
        "---",
        "",
        f"# {title}",
        "",
        f"- 检索词：`{query}`",
        f"- 生成时间：`{timestamp}`",
        f"- 命中数量：`{len(matched)}`",
        "",
        "## 结果",
        "",
    ]

    for record in matched:
        lines.append(f"- [[{record.rel_path.as_posix()}|{record.title}]]")
        lines.append(f"  UP主：{record.up_name or '未知'} | 日期：{record.fav_time or '未知'} | 领域：{record.domain or '未分类'}")
        if record.folders:
            lines.append(f"  收藏夹：{record.folders}")
        if record.source:
            lines.append(f"  链接：{record.source}")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search existing Bilibili favorite notes and write results into the global 搜索 root.")
    parser.add_argument("--archive-root", required=True, help="Path to B站收藏 root")
    parser.add_argument("--query", required=True, help="Search terms")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of results to write")
    parser.add_argument("--note-title", help="Optional output note title")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_root = Path(args.archive_root).expanduser().resolve()
    records = load_records(archive_root)
    matched = match_records(records, args.query)[: args.limit]
    output_path = write_search_note(archive_root, args.query, matched, args.note_title)
    print(f"results={len(matched)}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
