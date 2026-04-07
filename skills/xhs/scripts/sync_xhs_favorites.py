#!/usr/bin/env python3
"""
Sync exported Xiaohongshu favorites into an Obsidian-friendly Markdown archive.

Input JSON is the normalized export schema produced by export_xhs_favorites.py.
Output structure under: <target-root>/小红书/
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parent.parent
BASE_SYNC_PATH = SKILLS_DIR / "x-likes" / "scripts" / "sync_x_likes.py"

ROOT_DATE = "01 日期"
ROOT_AUTHOR = "02 作者"
ROOT_SOURCE = "03 来源"
ROOT_DOMAIN = "04 领域"
ROOT_COARSE = "05 粗分类"
ROOT_SEARCH = "06 搜索"
ROOT_RUBBISH = "07 废弃"
LEGACY_ROOT_MAPPINGS = {
    "01 Date": ROOT_DATE,
    "02 Author": ROOT_AUTHOR,
    "03 Domain": ROOT_DOMAIN,
    "04 Collections": ROOT_SOURCE,
    "05 Collections": ROOT_SOURCE,
    "04 Search": ROOT_SEARCH,
    "05 Search": ROOT_SEARCH,
    "05 Rubbish": ROOT_RUBBISH,
    "06 Rubbish": ROOT_RUBBISH,
}
DEFAULT_CONTAINER_NAME = "小红书"
DEFAULT_TARGET_ROOT = Path(
    "/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources"
)
DEFAULT_TAXONOMY_PATH = DEFAULT_TARGET_ROOT / "书签库" / "ROOT分类目录.md"
RUBBISH_KEEP_FILE = ".keep"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
COARSE_SPLIT_MAX_LINES = 50
COARSE_BUCKET_ORDER = [
    "AI与前沿科技",
    "学习成长",
    "工具效率",
    "商业职场",
    "生活见闻",
    "资源内容",
    "创作设计",
    "未分类",
]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_module(BASE_SYNC_PATH, "x_to_obsidian_base_sync")


@dataclass
class SourceMembership:
    collection_id: str
    name: str
    order: int = 0


@dataclass
class Record:
    note_id: str
    title: str
    title_preview: str
    author_id: str
    author_name: str
    profile_url: str
    note_time: str
    note_time_source: str
    note_type: str
    source: str
    canonical_url: str
    domain_parts: List[str]
    content: str
    likes: int
    collects: int
    comments: int
    cover_url: str
    media_urls: List[str]
    fetch_status: str
    source_actions: List[str] = field(default_factory=list)
    source_refs: List[SourceMembership] = field(default_factory=list)
    imported_at: str = ""


@dataclass
class CoarseBucketRule:
    name: str
    domain_prefixes: List[List[str]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Xiaohongshu favorites JSON to local Markdown structure.")
    parser.add_argument("--input-json", required=True, help="Path to exported Xiaohongshu favorites JSON")
    parser.add_argument("--target-root", default=str(DEFAULT_TARGET_ROOT), help="Root path XX. Output is XX/小红书/")
    parser.add_argument("--container-name", default=DEFAULT_CONTAINER_NAME, help="Container folder inside target root")
    parser.add_argument("--mode", choices=["merge", "create"], default="merge")
    parser.add_argument("--classification", choices=["auto"], default="auto")
    parser.add_argument("--title-language", choices=["zh", "en"], default="zh")
    parser.add_argument("--taxonomy-path", help="Path to AI_OUTLINE_V1 markdown taxonomy")
    return parser.parse_args()


def root_date_name() -> str:
    return ROOT_DATE


def root_author_name() -> str:
    return ROOT_AUTHOR


def root_domain_name() -> str:
    return ROOT_DOMAIN


def root_search_name() -> str:
    return ROOT_SEARCH


def root_rubbish_name() -> str:
    return ROOT_RUBBISH


def dashboard_name() -> str:
    return base.dashboard_name()


def index_name() -> str:
    return base.index_name()


def index_stem() -> str:
    return base.index_stem()


def fallback_note_title(note_id: str) -> str:
    prefix = "Post" if base.ACTIVE_LANG == "en" else "笔记"
    return f"{prefix} {note_id[-6:]}"


def note_time_from_note_id(note_id: object) -> str:
    raw = str(note_id or "").strip()
    if len(raw) < 8 or not re.fullmatch(r"[0-9a-fA-F_-]+", raw):
        return ""
    try:
        ts = int(raw[:8], 16)
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d")
    except (ValueError, OverflowError, OSError):
        return ""


def note_time_label() -> str:
    return "Time" if base.ACTIVE_LANG == "en" else "时间"


def source_title() -> str:
    return "Sources" if base.ACTIVE_LANG == "en" else "来源"


def source_label() -> str:
    return "Sources" if base.ACTIVE_LANG == "en" else "来源"


def coarse_title() -> str:
    return "Coarse Categories" if base.ACTIVE_LANG == "en" else "粗分类"


def unknown_date_year() -> str:
    return "Unknown Date" if base.ACTIVE_LANG == "en" else "未知日期"


def sorted_year_labels(labels: Sequence[str]) -> List[str]:
    valid = sorted([label for label in labels if re.fullmatch(r"\d{4}", label)], reverse=True)
    invalid = sorted([label for label in labels if not re.fullmatch(r"\d{4}", label)])
    return [*valid, *invalid]


def year_month_heading(year: str, month_num: int) -> str:
    if month_num > 0:
        return f"{year} / {base.month_label_from_number(month_num)}"
    return year


def section_content(text: str, heading: str) -> str:
    marker = f"\n## {heading}\n"
    start = text.find(marker)
    if start == -1:
        return ""
    pos = start + len(marker)
    nxt = text.find("\n## ", pos)
    if nxt == -1:
        return text[pos:].strip()
    return text[pos:nxt].strip()


def quote_inline_list(values: Sequence[str]) -> str:
    return "[" + ", ".join(base.quote_yaml(v) for v in values) + "]"


def collection_slug(name: str) -> str:
    clean = base.sanitize_filename(name).lower()
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"-+", "-", clean).strip("-")
    return clean or "collection"


def note_year(date_str: str) -> str:
    if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:4]
    return unknown_date_year()


def unique_note_path(dir_path: Path, base_name: str) -> Path:
    base_name = base.sanitize_filename(base_name).strip() or base.t("untitled")
    candidate = dir_path / f"{base_name}.md"
    n = 2
    while candidate.exists():
        candidate = dir_path / f"{base_name} ({n}).md"
        n += 1
    return candidate


def collection_page_filename(name: str, seen: set[str]) -> str:
    stem = base.sanitize_filename(name).strip() or "来源"
    candidate = stem
    n = 2
    while candidate.lower() in seen:
        candidate = f"{stem} ({n})"
        n += 1
    seen.add(candidate.lower())
    return candidate


def normalize_source_entry(value: object) -> SourceMembership:
    data = value if isinstance(value, dict) else {}
    return SourceMembership(
        collection_id=str(data.get("id", "") or data.get("collection_id", "")).strip(),
        name=str(data.get("name", "") or "未命名来源").strip() or "未命名来源",
        order=int(data.get("order", 0) or 0),
    )


def normalize_string_list(values: object) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            out.append(text)
    return out


def resolve_taxonomy_path(output_root: Path, taxonomy_path: Optional[Path]) -> Path:
    if taxonomy_path is not None:
        return taxonomy_path.expanduser().resolve()
    local_root = output_root / root_domain_name() / base.ROOT_TAXONOMY_FILENAME
    if local_root.exists():
        return local_root.resolve()
    if DEFAULT_TAXONOMY_PATH.exists():
        return DEFAULT_TAXONOMY_PATH.resolve()
    return base.DEFAULT_ROOT_TAXONOMY_PATH.resolve()


def ensure_local_root_taxonomy(output_root: Path, source_path: Path) -> None:
    domain_root = output_root / root_domain_name()
    domain_root.mkdir(parents=True, exist_ok=True)
    destination = domain_root / base.ROOT_TAXONOMY_FILENAME
    if source_path.resolve() == destination.resolve():
        return
    shutil.copy2(source_path, destination)


def classify_record(record: Record, rules: Dict[str, object]) -> List[str]:
    media_lines = [f"- media {idx + 1}: {url}" for idx, url in enumerate(record.media_urls)]
    parts, _tag, _topics = base.manual_classify(
        title=record.title or record.title_preview,
        content=record.content,
        source=record.canonical_url or record.source,
        rules=rules,
        media_lines=media_lines,
        existing_domain_parts=record.domain_parts,
    )
    return base.normalize_domain_parts(parts)


def parse_frontmatter(text: str) -> Tuple[Dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    block = text[4:end]
    body = text[end + 5 :]
    data = yaml.safe_load(block) or {}
    if not isinstance(data, dict):
        data = {}
    return data, body


def parse_existing_records(output_root: Path) -> Dict[str, Record]:
    records: Dict[str, Record] = {}
    date_root = output_root / root_date_name()
    if not date_root.exists():
        return records

    for note_path in sorted(date_root.rglob("*.md")):
        if note_path.name == index_name():
            continue
        text = note_path.read_text(encoding="utf-8", errors="ignore")
        fm, body = parse_frontmatter(text)
        note_id = str(fm.get("note_id", "")).strip()
        if not note_id:
            continue
        source_actions = [str(name).strip() for name in fm.get("source_actions", []) or [] if str(name).strip()]
        if not source_actions:
            source_actions = [str(name).strip() for name in fm.get("collections", []) or [] if str(name).strip()]
        raw_refs = fm.get("source_refs", []) or []
        source_refs = [
            normalize_source_entry(value)
            for value in raw_refs
            if isinstance(value, dict)
        ]
        if not source_refs:
            source_refs = [
                SourceMembership(collection_id="", name=name, order=index + 1)
                for index, name in enumerate(source_actions)
            ]
        records[note_id] = Record(
            note_id=note_id,
            title=str(fm.get("title", "")).strip() or base.normalize_title(str(fm.get("title", "")), fallback_note_title(note_id)),
            title_preview=str(fm.get("title", "")).strip(),
            author_id=str(fm.get("author_id", "")).strip(),
            author_name=str(fm.get("author_name", "")).strip(),
            profile_url=str(fm.get("profile_url", "")).strip(),
            note_time=str(fm.get("note_time", "")).strip() or note_time_from_note_id(note_id),
            note_time_source=str(fm.get("note_time_source", "")).strip() or ("note_id" if note_time_from_note_id(note_id) else ""),
            note_type=str(fm.get("note_type", "")).strip(),
            source=str(fm.get("source", "")).strip(),
            canonical_url=str(fm.get("canonical_url", "")).strip(),
            domain_parts=base.normalize_domain_parts(str(fm.get("domain", "")).split("/")) or ["其他"],
            content=section_content(body, "内容"),
            likes=int(fm.get("likes", 0) or 0),
            collects=int(fm.get("collects", 0) or 0),
            comments=int(fm.get("comments", 0) or 0),
            cover_url=str(fm.get("cover_url", "")).strip(),
            media_urls=normalize_string_list(fm.get("media_urls", [])),
            fetch_status=str(fm.get("fetch_status", "partial") or "partial"),
            source_actions=sorted(set(source_actions)),
            source_refs=sorted(source_refs, key=lambda item: (item.order, item.name.lower())),
            imported_at=str(fm.get("imported_at", "")).strip(),
        )
    return records


def parse_input_records(json_path: Path, rules: Dict[str, object]) -> Tuple[Dict[str, Record], Dict[str, int], str]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    notes = payload.get("notes", [])
    collections_payload = payload.get("sources") or payload.get("collections", [])
    run_meta = payload.get("run_meta", {}) if isinstance(payload.get("run_meta", {}), dict) else {}
    imported_at = str(run_meta.get("crawled_at", "generated-by-xhs-favorites-to-obsidian")).strip() or "generated-by-xhs-favorites-to-obsidian"

    collection_counts: Dict[str, int] = {}
    for item in collections_payload if isinstance(collections_payload, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name:
            collection_counts[name] = int(item.get("note_count_estimate", 0) or 0)

    out: Dict[str, Record] = {}
    for item in notes if isinstance(notes, list) else []:
        if not isinstance(item, dict):
            continue
        note_id = str(item.get("note_id", "")).strip()
        if not note_id:
            continue
        source_refs = sorted(
            [normalize_source_entry(v) for v in item.get("source_refs", []) or item.get("collections", []) or []],
            key=lambda col: (col.order, col.name.lower()),
        )
        source_actions = [str(value).strip() for value in item.get("source_actions", []) or [] if str(value).strip()]
        if not source_actions:
            source_actions = [ref.name for ref in source_refs if ref.name]
        record = Record(
            note_id=note_id,
            title=str(item.get("title", "")).strip(),
            title_preview=str(item.get("title_preview", "")).strip(),
            author_id=str(item.get("author_id", "")).strip(),
            author_name=str(item.get("author_name", "")).strip(),
            profile_url=str(item.get("profile_url", "")).strip(),
            note_time=str(item.get("note_time", "")).strip() or note_time_from_note_id(note_id),
            note_time_source=str(item.get("note_time_source", "")).strip() or ("note_id" if note_time_from_note_id(note_id) else ""),
            note_type=str(item.get("note_type", "")).strip(),
            source=str(item.get("note_url", "")).strip(),
            canonical_url=str(item.get("canonical_url", "")).strip(),
            domain_parts=[],
            content=str(item.get("content", "")).strip(),
            likes=int(item.get("likes", 0) or 0),
            collects=int(item.get("collects", 0) or 0),
            comments=int(item.get("comments", 0) or 0),
            cover_url=str(item.get("cover_url", "")).strip(),
            media_urls=normalize_string_list(item.get("media_urls", [])),
            fetch_status=str(item.get("fetch_status", "partial") or "partial"),
            source_actions=sorted(set(source_actions)),
            source_refs=source_refs,
            imported_at=imported_at,
        )
        record.domain_parts = classify_record(record, rules)
        out[note_id] = record
        for source_ref in source_refs:
            collection_counts.setdefault(source_ref.name, 0)
            collection_counts[source_ref.name] += 1

    return out, collection_counts, imported_at


def merge_records(existing: Optional[Record], incoming: Record, rules: Dict[str, object]) -> Record:
    if existing is None:
        incoming.domain_parts = classify_record(incoming, rules)
        return incoming

    use_incoming_detail = incoming.fetch_status == "full"
    source_actions = sorted(set(incoming.source_actions)) if incoming.source_actions else list(existing.source_actions)
    source_refs = (
        sorted(incoming.source_refs, key=lambda item: (item.order, item.name.lower()))
        if incoming.source_refs
        else sorted(existing.source_refs, key=lambda item: (item.order, item.name.lower()))
    )
    merged = Record(
        note_id=incoming.note_id,
        title=incoming.title or existing.title,
        title_preview=incoming.title_preview or existing.title_preview,
        author_id=incoming.author_id or existing.author_id,
        author_name=incoming.author_name or existing.author_name,
        profile_url=incoming.profile_url or existing.profile_url,
        note_time=incoming.note_time or existing.note_time,
        note_time_source=incoming.note_time_source or existing.note_time_source,
        note_type=incoming.note_type or existing.note_type,
        source=incoming.source or existing.source,
        canonical_url=incoming.canonical_url or existing.canonical_url,
        domain_parts=list(existing.domain_parts),
        content=incoming.content if use_incoming_detail else (incoming.content or existing.content),
        likes=incoming.likes if use_incoming_detail else existing.likes,
        collects=incoming.collects if use_incoming_detail else existing.collects,
        comments=incoming.comments if use_incoming_detail else existing.comments,
        cover_url=incoming.cover_url if (use_incoming_detail and incoming.cover_url) else (incoming.cover_url or existing.cover_url),
        media_urls=incoming.media_urls if use_incoming_detail else (incoming.media_urls or existing.media_urls),
        fetch_status="full" if incoming.fetch_status == "full" or existing.fetch_status == "full" else incoming.fetch_status,
        source_actions=source_actions,
        source_refs=source_refs,
        imported_at=incoming.imported_at or existing.imported_at,
    )
    merged.domain_parts = classify_record(merged, rules)
    return merged


def author_display(record: Record) -> str:
    if record.author_name and record.author_id:
        return f"{record.author_name} ({record.author_id})"
    return record.author_name or record.author_id or base.t("unknown_author")


def domain_rel_link(parts: Sequence[str]) -> str:
    clean = [base.sanitize_filename(p) for p in parts if p]
    if len(clean) == 1:
        return f"{root_domain_name()}/{clean[0]}"
    return f"{root_domain_name()}/{'/'.join(clean[:-1])}/{clean[-1]}"


def domain_parent_index_link(parts: Sequence[str]) -> str:
    clean = [base.sanitize_filename(p) for p in parts if p]
    if not clean:
        return f"{root_domain_name()}/{index_stem()}"
    return f"{root_domain_name()}/{'/'.join(clean)}/{index_stem()}"


def domain_abs_path(domain_root: Path, parts: Sequence[str]) -> Path:
    clean = [base.sanitize_filename(p) for p in parts if p]
    if len(clean) == 1:
        return domain_root / f"{clean[0]}.md"
    out_dir = domain_root
    for part in clean[:-1]:
        out_dir = out_dir / part
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{clean[-1]}.md"


def domain_parent_index_path(domain_root: Path, parts: Sequence[str]) -> Path:
    out_dir = domain_root
    for part in [base.sanitize_filename(p) for p in parts if p]:
        out_dir = out_dir / part
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / index_name()


def parse_rule_domain_prefix(value: str) -> List[str]:
    return [part.strip() for part in value.split("/") if part.strip()]


def default_coarse_rules() -> List[CoarseBucketRule]:
    return [
        CoarseBucketRule(
            "AI与前沿科技",
            domain_prefixes=[["工具", "人工智能"], ["工具", "编程开发"]],
            keywords=["ai", "agent", "deepseek", "openai", "claude", "cursor", "大模型", "智能体", "编程", "代码", "开发", "模型", "论文"],
        ),
        CoarseBucketRule(
            "学习成长",
            domain_prefixes=[["信息", "学习充电"]],
            keywords=["学习", "课程", "教程", "读书", "英语", "心理", "成长", "自律", "方法", "教育"],
        ),
        CoarseBucketRule(
            "工具效率",
            domain_prefixes=[["工具", "办公效率"], ["工具", "在线工具"], ["工具", "电脑装机"], ["工具", "软件APP"]],
            keywords=["办公", "工具", "插件", "软件", "app", "效率", "mac", "windows", "浏览器", "notion", "obsidian"],
        ),
        CoarseBucketRule(
            "商业职场",
            domain_prefixes=[["工具", "各行各业"]],
            keywords=["电商", "运营", "求职", "简历", "面试", "副业", "商业", "营销", "职场", "创业", "赚钱"],
        ),
        CoarseBucketRule(
            "生活见闻",
            domain_prefixes=[["信息", "生活百科"], ["信息", "热点资讯"]],
            keywords=["生活", "健康", "出行", "安全", "社会", "新闻", "情感", "避坑", "citywalk", "吃", "睡"],
        ),
        CoarseBucketRule(
            "资源内容",
            domain_prefixes=[["资源"], ["会员专享"]],
            keywords=["资源", "网盘", "游戏", "影视", "音乐", "动漫", "漫画", "导航", "会员"],
        ),
        CoarseBucketRule(
            "创作设计",
            domain_prefixes=[["素材"]],
            keywords=["剪辑", "设计", "海报", "素材", "摄影", "封面", "配色", "logo", "字体", "视频创作"],
        ),
    ]


def default_coarse_index_markdown() -> str:
    lines = [
        "# 粗分类目录",
        "",
        "FORMAT: XHS_COARSE_V1",
        "",
        "## 说明",
        "",
        "- 这个文档是 `05 粗分类/` 的唯一规则来源。",
        "- 以后如果你要调整粗分类，请直接编辑这里，再重新运行同步脚本。",
        "- 匹配按从上到下顺序执行；先命中的规则优先。",
        "- `domain-prefix` 用 `A / B` 的路径前缀表示。",
        "- `keyword` 为大小写不敏感的文本匹配。",
        "- 如果某条笔记没有命中任何规则，会落到 `未分类`。",
        f"- 如果某个粗分类文件生成后预计超过 `{COARSE_SPLIT_MAX_LINES}` 行，脚本会在该文件内部按细分类路径自动加 `##` / `###` 分段。",
        "",
        "## 分类规则",
        "",
    ]
    for rule in default_coarse_rules():
        lines.append(f"### {rule.name}")
        for prefix in rule.domain_prefixes:
            lines.append(f"- domain-prefix: {' / '.join(prefix)}")
        for keyword in rule.keywords:
            lines.append(f"- keyword: {keyword}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_coarse_index_markdown(path: Path) -> List[CoarseBucketRule]:
    rules: List[CoarseBucketRule] = []
    current: Optional[CoarseBucketRule] = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        heading = re.match(r"^###\s+(.+?)\s*$", stripped)
        if heading:
            current = CoarseBucketRule(name=heading.group(1).strip())
            rules.append(current)
            continue
        bullet = re.match(r"^-\s+([a-zA-Z-]+):\s*(.+?)\s*$", stripped)
        if not bullet or current is None:
            continue
        key, value = bullet.groups()
        if key.lower() == "domain-prefix":
            parts = parse_rule_domain_prefix(value)
            if parts:
                current.domain_prefixes.append(parts)
        elif key.lower() == "keyword":
            token = value.strip().lower()
            if token:
                current.keywords.append(token)
    return [rule for rule in rules if rule.name]


def coarse_index_path(root: Path) -> Path:
    return root / ROOT_COARSE / "Index.md"


def load_coarse_rules(existing_root: Optional[Path]) -> Tuple[List[CoarseBucketRule], str]:
    if existing_root is not None:
        candidate = coarse_index_path(existing_root)
        if candidate.exists():
            parsed = parse_coarse_index_markdown(candidate)
            if parsed:
                return parsed, candidate.read_text(encoding="utf-8")
    return default_coarse_rules(), default_coarse_index_markdown()


def ensure_coarse_index_doc(coarse_root: Path, source_text: str) -> None:
    coarse_root.mkdir(parents=True, exist_ok=True)
    (coarse_root / "Index.md").write_text(source_text, encoding="utf-8")


def bucket_row_lines(row: Dict[str, object], bucket_path: Path) -> List[str]:
    note_title = str(row["title"])
    rel_path = str(row["rel_path"])
    return [
        f"- [[{rel_path}|{note_title}]]",
        f"  作者：{row['author']}",
    ]


def estimate_bucket_lines(rows: Sequence[Dict[str, object]], bucket_path: Path) -> int:
    return 6 + sum(len(bucket_row_lines(row, bucket_path)) for row in rows)


def coarse_bucket_for_record(record: Record, rules: Optional[Sequence[CoarseBucketRule]] = None) -> str:
    parts = list(record.domain_parts)
    text = " ".join(
        part
        for part in [
            record.title,
            record.title_preview,
            record.content,
            record.author_name,
            record.note_type,
            " ".join(record.source_actions),
            " / ".join(parts),
        ]
        if part and str(part).strip()
    ).lower()
    active_rules = list(rules or default_coarse_rules())
    for rule in active_rules:
        if any(parts[: len(prefix)] == prefix for prefix in rule.domain_prefixes if prefix):
            return rule.name
    for rule in active_rules:
        if any(keyword in text for keyword in rule.keywords if keyword):
            return rule.name
    return "未分类"


def render_coarse_bucket_index(path: Path, title: str, rows: Sequence[Dict[str, object]]) -> None:
    lines = [
        f"# {title}",
        "",
        f"- {base.t('label_total')}: **{len(rows)}**",
        "",
    ]
    if estimate_bucket_lines(rows, path) <= COARSE_SPLIT_MAX_LINES:
        lines.extend(["## 列表", ""])
        for row in rows:
            lines.extend(bucket_row_lines(row, path))
        lines.append("")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    grouped: Dict[str, List[Dict[str, object]]] = {}
    for row in rows:
        parts = str(row["domain"]).split("/")
        second = parts[1] if len(parts) >= 2 else "未分类"
        grouped.setdefault(second, []).append(row)
    for second, second_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.extend([f"## {second}", ""])
        if estimate_bucket_lines(second_rows, path) > COARSE_SPLIT_MAX_LINES:
            third_grouped: Dict[str, List[Dict[str, object]]] = {}
            for row in second_rows:
                parts = str(row["domain"]).split("/")
                third = parts[2] if len(parts) >= 3 else "未分类"
                third_grouped.setdefault(third, []).append(row)
            for third, third_rows in sorted(third_grouped.items(), key=lambda item: (-len(item[1]), item[0])):
                lines.extend([f"### {third}", ""])
                for row in third_rows:
                    lines.extend(bucket_row_lines(row, path))
                lines.append("")
        else:
            for row in second_rows:
                lines.extend(bucket_row_lines(row, path))
            lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def render_coarse_domain_indexes(output_root: Path, note_rows: Sequence[Dict[str, object]], records: Dict[str, Record], existing_root: Optional[Path] = None) -> Dict[str, int]:
    coarse_root = output_root / ROOT_COARSE
    rules, source_text = load_coarse_rules(existing_root)
    ensure_coarse_index_doc(coarse_root, source_text)
    rows_by_id = {str(row["note_id"]): row for row in note_rows}
    buckets: Dict[str, List[Dict[str, object]]] = {}
    for note_id, record in records.items():
        bucket = coarse_bucket_for_record(record, rules)
        buckets.setdefault(bucket, []).append(rows_by_id[note_id])

    for label, rows in sorted(buckets.items(), key=lambda item: (COARSE_BUCKET_ORDER.index(item[0]) if item[0] in COARSE_BUCKET_ORDER else 999, -len(item[1]), item[0])):
        render_coarse_bucket_index(coarse_root / f"{base.sanitize_filename(label)}.md", label, rows)
    return {label: len(rows) for label, rows in buckets.items()}


def build_note_text(record: Record, title: str, domain_parts: Sequence[str], tags: Sequence[str]) -> str:
    source_names = [item.name for item in record.source_refs]
    media_urls = record.media_urls or ([record.cover_url] if record.cover_url else [])
    media_section = media_urls or ["- (无)"] if base.ACTIVE_LANG == "zh" else media_urls or ["- (none)"]
    source_link = record.canonical_url or record.source
    content = record.content or base.t("empty_content")

    return "\n".join(
        [
            "---",
            'platform: "xiaohongshu"',
            f"note_id: {base.quote_yaml(record.note_id)}",
            f"title: {base.quote_yaml(title)}",
            f"author_id: {base.quote_yaml(record.author_id)}",
            f"author_name: {base.quote_yaml(record.author_name)}",
            f"profile_url: {base.quote_yaml(record.profile_url)}",
            f"note_time: {base.quote_yaml(record.note_time)}",
            f"note_time_source: {base.quote_yaml(record.note_time_source)}",
            f"note_type: {base.quote_yaml(record.note_type)}",
            f"source: {base.quote_yaml(record.source)}",
            f"canonical_url: {base.quote_yaml(record.canonical_url)}",
            f"source_actions: {quote_inline_list(record.source_actions)}",
            f"source_refs: {json.dumps([{'id': item.collection_id, 'name': item.name, 'order': item.order} for item in record.source_refs], ensure_ascii=False)}",
            f"domain: {base.quote_yaml('/'.join(domain_parts))}",
            f"likes: {record.likes}",
            f"collects: {record.collects}",
            f"comments: {record.comments}",
            f"cover_url: {base.quote_yaml(record.cover_url)}",
            f"media_urls: {quote_inline_list(media_urls)}",
            f"fetch_status: {base.quote_yaml(record.fetch_status)}",
            f"tags: {quote_inline_list(tags)}",
            f"imported_at: {base.quote_yaml(record.imported_at)}",
            "---",
            "",
            f"# {title}",
            "",
            f"- {base.t('field_author')}: {author_display(record)}",
            f"- {note_time_label()}: {record.note_time}",
            f"- {base.t('field_source')}: {source_link}",
            f"- {base.t('field_domain')}: [[{domain_rel_link(domain_parts)}|{'/'.join(domain_parts)}]]",
            f"- {source_label()}: {', '.join(source_names) if source_names else '未知来源'}",
            "",
            "## 内容",
            "",
            content,
            "",
            "## 媒体链接",
            "",
            *media_section,
            "",
        ]
    )


def build_rubbish_note_text(record: Record, title: str) -> str:
    media_urls = record.media_urls or ([record.cover_url] if record.cover_url else [])
    return "\n".join(
        [
            "---",
            'platform: "xiaohongshu"',
            f"note_id: {base.quote_yaml(record.note_id)}",
            f"title: {base.quote_yaml(title)}",
            f"author_id: {base.quote_yaml(record.author_id)}",
            f"author_name: {base.quote_yaml(record.author_name)}",
            f"note_time: {base.quote_yaml(record.note_time)}",
            f"note_time_source: {base.quote_yaml(record.note_time_source)}",
            f"note_type: {base.quote_yaml(record.note_type)}",
            f"source: {base.quote_yaml(record.source)}",
            f"canonical_url: {base.quote_yaml(record.canonical_url)}",
            f"source_actions: {quote_inline_list(record.source_actions)}",
            f"source_refs: {json.dumps([{'id': item.collection_id, 'name': item.name, 'order': item.order} for item in record.source_refs], ensure_ascii=False)}",
            f"domain: {base.quote_yaml('/'.join(record.domain_parts))}",
            f"likes: {record.likes}",
            f"collects: {record.collects}",
            f"comments: {record.comments}",
            f"cover_url: {base.quote_yaml(record.cover_url)}",
            f"media_urls: {quote_inline_list(media_urls)}",
            f"fetch_status: {base.quote_yaml(record.fetch_status)}",
            f"tags: {quote_inline_list(['xhs-favorite', 'rubbish'])}",
            f"imported_at: {base.quote_yaml(record.imported_at)}",
            "---",
            "",
            f"# {title}",
            "",
            "## 内容",
            "",
            record.content or base.t("empty_content"),
            "",
        ]
    )


def render_structure(stage_root: Path, records: Dict[str, Record], collection_estimates: Dict[str, int], existing_root: Optional[Path] = None) -> Dict[str, object]:
    date_root = stage_root / root_date_name()
    author_root = stage_root / root_author_name()
    domain_root = stage_root / root_domain_name()
    source_root = stage_root / ROOT_SOURCE
    coarse_root = stage_root / ROOT_COARSE
    for root in (date_root, author_root, domain_root, source_root, coarse_root):
        root.mkdir(parents=True, exist_ok=True)

    note_rows: List[Dict[str, object]] = []
    url_rows: List[str] = []
    sorted_records = sorted(
        records.values(),
        key=lambda rec: (rec.note_time[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", rec.note_time) else "", rec.note_id),
        reverse=True,
    )

    for record in sorted_records:
        year = note_year(record.note_time)
        month_num = base.month_number(record.note_time)
        month_label = base.month_label_from_number(month_num)
        note_dir = date_root / year if month_num == 0 else date_root / year / month_label
        note_dir.mkdir(parents=True, exist_ok=True)

        domain_parts = base.normalize_domain_parts(record.domain_parts) or ["其他"]
        title = base.normalize_title(record.title or record.title_preview, fallback_note_title(record.note_id))
        note_path = unique_note_path(note_dir, title)

        tags = ["xhs-favorite", f"year/{year}"]
        if month_num:
            tags.append(f"month/{month_num}")
        tags.append(f"domain/{'/'.join(domain_parts)}")
        for action in record.source_actions:
            tags.append(f"source/{collection_slug(action)}")
        tags = sorted(set(tags))

        note_path.write_text(build_note_text(record, note_path.stem, domain_parts, tags), encoding="utf-8")

        rel = note_path.relative_to(stage_root).as_posix()
        note_rows.append(
            {
                "note_id": record.note_id,
                "title": note_path.stem,
                "author": record.author_name or record.author_id or base.t("unknown_author"),
                "author_id": record.author_id or base.t("unknown_author"),
                "note_time": record.note_time,
                "year": year,
                "month_num": month_num,
                "month": month_label if month_num > 0 else "",
                "domain": "/".join(domain_parts),
                "domain_top": domain_parts[0],
                "rel_path": rel,
                "domain_link": domain_rel_link(domain_parts),
                "url": record.canonical_url or record.source,
                "source_actions": list(record.source_actions),
            }
        )
        if record.canonical_url or record.source:
            url_rows.append(record.canonical_url or record.source)

    # Date indexes
    by_year: Dict[str, List[Dict[str, object]]] = {}
    for row in note_rows:
        by_year.setdefault(str(row["year"]), []).append(row)

    for year, rows in by_year.items():
        month_map: Dict[int, List[Dict[str, object]]] = {}
        for row in rows:
            month_map.setdefault(int(row["month_num"] or 0), []).append(row)

        month_order = sorted(month_map.keys(), reverse=True)
        year_lines = [
            "---",
            f"count: {len(rows)}",
            'tags: ["xhs-favorite", "index/date"]',
            "---",
            "",
            f"# {year}",
            "",
            f"{base.t('label_total')}: **{len(rows)}**",
            "",
        ]
        for month in month_order:
            month_label = base.month_label_from_number(month)
            month_rows = month_map[month]
            if month == 0:
                year_lines.extend(["## 条目", ""])
                for row in month_rows:
                    year_lines.append(f"- [[{row['rel_path']}|{row['title']}]]")
                year_lines.append("")
                continue
            month_lines = [
                "---",
                f"count: {len(month_rows)}",
                'tags: ["xhs-favorite", "index/date"]',
                "---",
                "",
                f"# {year} / {month_label}",
                "",
                f"{base.t('label_total')}: **{len(month_rows)}**",
                "",
                f"## {base.t('section_list')}",
                "",
            ]
            for row in month_rows:
                month_lines.append(f"- [[{row['rel_path']}|{row['title']}]]")
            month_lines.append("")
            month_dir = date_root / year / month_label
            (month_dir / index_name()).write_text("\n".join(month_lines), encoding="utf-8")
            year_lines.append(f"- [[{root_date_name()}/{year}/{month_label}/{index_stem()}|{year} / {month_label}]] ({len(month_rows)})")
        year_lines.append("")
        (date_root / year / index_name()).write_text("\n".join(year_lines), encoding="utf-8")

    date_index_lines = [
        "---",
        f"count: {len(note_rows)}",
        'tags: ["xhs-favorite", "index/date"]',
        "---",
        "",
        f"# {base.t('title_date')}",
        "",
        f"{base.t('label_total')}: **{len(note_rows)}**",
        "",
    ]
    for year in sorted_year_labels(list(by_year.keys())):
        date_index_lines.append(f"- [[{root_date_name()}/{year}/{index_stem()}|{year}]] ({len(by_year[year])})")
    date_index_lines.append("")
    (date_root / index_name()).write_text("\n".join(date_index_lines), encoding="utf-8")

    # Author indexes
    by_author: Dict[str, List[Dict[str, object]]] = {}
    for row in note_rows:
        by_author.setdefault(str(row["author_id"]), []).append(row)

    for author_id, rows in by_author.items():
        rows.sort(key=lambda row: (str(row["note_time"]), str(row["note_id"])), reverse=True)
        by_ym: Dict[Tuple[str, int], List[Dict[str, object]]] = {}
        for row in rows:
            by_ym.setdefault((str(row["year"]), int(row["month_num"] or 0)), []).append(row)
        lines = [
            "---",
            f"author_id: {base.quote_yaml(author_id)}",
            f"author_name: {base.quote_yaml(str(rows[0]['author']))}",
            f"count: {len(rows)}",
            'tags: ["xhs-favorite", "index/author"]',
            "---",
            "",
            f"# {rows[0]['author']}",
            "",
            f"{base.t('label_total')}: **{len(rows)}**",
            "",
        ]
        for year, month in sorted(by_ym.keys(), reverse=True):
            lines.append(f"## {year_month_heading(year, month)}")
            lines.append("")
            for row in by_ym[(year, month)]:
                lines.append(f"- [[{row['rel_path']}|{row['title']}]]")
            lines.append("")
        fname = base.sanitize_filename(author_id) or base.t("unknown_author")
        (author_root / f"{fname}.md").write_text("\n".join(lines), encoding="utf-8")

    author_index_lines = [
        "---",
        f"count: {len(by_author)}",
        'tags: ["xhs-favorite", "index/author"]',
        "---",
        "",
        f"# {base.t('title_author')}",
        "",
        f"{base.t('label_total_authors')}: **{len(by_author)}**",
        "",
        f"## {base.t('section_list')}",
        "",
    ]
    for author_id, rows in sorted(by_author.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        author_index_lines.append(f"- [[{root_author_name()}/{base.sanitize_filename(author_id)}|{rows[0]['author']}]] ({len(rows)})")
    author_index_lines.append("")
    (author_root / index_name()).write_text("\n".join(author_index_lines), encoding="utf-8")

    # Domain indexes
    by_domain: Dict[str, List[Dict[str, object]]] = {}
    for row in note_rows:
        by_domain.setdefault(str(row["domain"]), []).append(row)

    domain_items = sorted(by_domain.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    parent_children: Dict[Tuple[str, ...], Dict[Tuple[str, ...], int]] = {}
    by_domain_parts: Dict[Tuple[str, ...], List[Dict[str, object]]] = {}
    top_domain_counter: Dict[str, int] = {}

    for domain_key, rows in domain_items:
        parts = tuple(base.normalize_domain_parts(domain_key.split("/")))
        by_domain_parts[parts] = rows
        top_domain_counter[parts[0]] = top_domain_counter.get(parts[0], 0) + len(rows)
        for depth in range(1, len(parts)):
            parent = tuple(parts[:depth])
            child = tuple(parts[: depth + 1])
            parent_children.setdefault(parent, {})
            parent_children[parent][child] = parent_children[parent].get(child, 0) + len(rows)

    parent_keys = set(parent_children.keys())

    for domain_key, rows in domain_items:
        parts = tuple(base.normalize_domain_parts(domain_key.split("/")))
        if parts in parent_keys:
            continue
        lines = [
            "---",
            f"domain: {base.quote_yaml('/'.join(parts))}",
            f"count: {len(rows)}",
            'tags: ["xhs-favorite", "index/domain"]',
            "---",
            "",
            f"# {'/'.join(parts)}",
            "",
            f"{base.t('label_total')}: **{len(rows)}**",
            "",
        ]
        by_ym: Dict[Tuple[str, int], List[Dict[str, object]]] = {}
        for row in rows:
            by_ym.setdefault((str(row["year"]), int(row["month_num"] or 0)), []).append(row)
        for year, month in sorted(by_ym.keys(), reverse=True):
            lines.append(f"## {year_month_heading(year, month)}")
            lines.append("")
            for row in by_ym[(year, month)]:
                lines.append(f"- [[{row['rel_path']}|{row['title']}]]")
            lines.append("")
        domain_abs_path(domain_root, parts).write_text("\n".join(lines), encoding="utf-8")

    for parent, child_map in sorted(parent_children.items(), key=lambda kv: kv[0]):
        parent_path = domain_parent_index_path(domain_root, parent)
        direct_rows = sorted(
            by_domain_parts.get(parent, []),
            key=lambda row: (str(row["note_time"]), str(row["note_id"])),
            reverse=True,
        )
        lines = [
            "---",
            f"domain: {base.quote_yaml('/'.join(parent))}",
            f"count: {len(direct_rows) + sum(child_map.values())}",
            'tags: ["xhs-favorite", "index/domain"]',
            "---",
            "",
            f"# {'/'.join(parent)}",
            "",
        ]
        if direct_rows:
            lines.extend([f"## {base.t('section_notes')}", ""])
            for row in direct_rows:
                lines.append(f"- [[{row['rel_path']}|{row['title']}]]")
            lines.append("")
        lines.extend([f"## {base.t('section_subcategories')}", ""])
        for child, count in sorted(child_map.items(), key=lambda kv: (-kv[1], "/".join(kv[0]))):
            child_name = "/".join(child[len(parent):]) or child[-1]
            child_link = domain_parent_index_link(child) if child in parent_children else domain_rel_link(child)
            lines.append(f"- [[{child_link}|{child_name}]] ({count})")
        lines.append("")
        parent_path.write_text("\n".join(lines), encoding="utf-8")

    top_domains_sorted = sorted(top_domain_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    domain_root_lines = [
        "---",
        f"count: {len(top_domains_sorted)}",
        'tags: ["xhs-favorite", "index/domain"]',
        "---",
        "",
        f"# {base.t('title_domain')}",
        "",
        f"{base.t('label_total_domains')}: **{len(top_domains_sorted)}**",
        "",
        f"## {base.t('section_list')}",
        "",
    ]
    for top, count in top_domains_sorted:
        link = domain_parent_index_link([top]) if (top,) in parent_children else domain_rel_link([top])
        domain_root_lines.append(f"- [[{link}|{top}]] ({count})")
    domain_root_lines.append("")
    (domain_root / index_name()).write_text("\n".join(domain_root_lines), encoding="utf-8")

    # Source indexes
    by_collection: Dict[str, List[Dict[str, object]]] = {}
    for row in note_rows:
        for source_name in row["source_actions"]:
            by_collection.setdefault(str(source_name), []).append(row)

    collection_pages: Dict[str, str] = {}
    seen_collection_files: set[str] = set()
    for collection_name in sorted(by_collection.keys()):
        collection_pages[collection_name] = collection_page_filename(collection_name, seen_collection_files)

    for collection_name, rows in sorted(by_collection.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rows.sort(key=lambda row: (str(row["note_time"]), str(row["note_id"])), reverse=True)
        by_ym: Dict[Tuple[str, int], List[Dict[str, object]]] = {}
        for row in rows:
            by_ym.setdefault((str(row["year"]), int(row["month_num"] or 0)), []).append(row)
        lines = [
            "---",
            f"name: {base.quote_yaml(collection_name)}",
            f"slug: {base.quote_yaml(collection_slug(collection_name))}",
            f"count: {len(rows)}",
            f"note_count_estimate: {collection_estimates.get(collection_name, len(rows))}",
            'tags: ["xhs-favorite", "index/collection"]',
            "---",
            "",
            f"# {collection_name}",
            "",
            f"{base.t('label_total')}: **{len(rows)}**",
            "",
        ]
        for year, month in sorted(by_ym.keys(), reverse=True):
            lines.append(f"## {year} / {base.month_label_from_number(month)}")
            lines.append("")
            for row in by_ym[(year, month)]:
                lines.append(f"- [[{row['rel_path']}|{row['title']}]]")
            lines.append("")
        (source_root / f"{collection_pages[collection_name]}.md").write_text("\n".join(lines), encoding="utf-8")

    collection_index_lines = [
        "---",
        f"count: {len(by_collection)}",
        'tags: ["xhs-favorite", "index/collection"]',
        "---",
        "",
        f"# {source_title()}",
        "",
        f"总计: **{len(by_collection)}**",
        "",
        f"## {base.t('section_list')}",
        "",
    ]
    for collection_name, rows in sorted(by_collection.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        collection_index_lines.append(
            f"- [[{ROOT_SOURCE}/{collection_pages[collection_name]}|{collection_name}]] ({len(rows)})"
        )
    collection_index_lines.append("")
    (source_root / index_name()).write_text("\n".join(collection_index_lines), encoding="utf-8")

    coarse_counts = render_coarse_domain_indexes(stage_root, note_rows, records, existing_root=existing_root)

    # Dashboard
    month_counter: Dict[Tuple[str, int], int] = {}
    for row in note_rows:
        key = (str(row["year"]), int(row["month_num"] or 0))
        month_counter[key] = month_counter.get(key, 0) + 1
    month_items = sorted(month_counter.items(), key=lambda kv: (kv[0][0], kv[0][1]), reverse=True)
    collection_stats = sorted(by_collection.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    dashboard_lines = [
        "---",
        f"count: {len(note_rows)}",
        'tags: ["xhs-favorite", "dashboard"]',
        "---",
        "",
        "# 小红书收藏仪表盘" if base.ACTIVE_LANG == "zh" else "# XHS Favorites Dashboard",
        "",
        f"{base.t('label_total')}: **{len(note_rows)}**",
        "",
        f"- [[{root_date_name()}/{index_stem()}|{base.t('title_date')}]]",
        f"- [[{root_author_name()}/{index_stem()}|{'作者' if base.ACTIVE_LANG == 'zh' else 'Author'}]]",
        f"- [[{root_domain_name()}/{index_stem()}|{'领域' if base.ACTIVE_LANG == 'zh' else 'Domain'}]]",
        f"- [[{ROOT_SOURCE}/{index_stem()}|{source_title()}]]",
        f"- [[{ROOT_COARSE}/{index_stem()}|{coarse_title()}]]",
        "",
        f"## {base.t('section_month_stats')}",
        "",
    ]
    for (year, month), count in month_items:
        if month > 0:
            month_label = base.month_label_from_number(month)
            dashboard_lines.append(f"- [[{root_date_name()}/{year}/{month_label}/{index_stem()}|{year} / {month_label}]]: {count}")
        else:
            dashboard_lines.append(f"- [[{root_date_name()}/{year}/{index_stem()}|{year}]]: {count}")
    dashboard_lines.extend(["", f"## {base.t('section_domain_stats')}", ""])
    for top, count in top_domains_sorted:
        link = domain_parent_index_link([top]) if (top,) in parent_children else domain_rel_link([top])
        dashboard_lines.append(f"- [[{link}|{top}]]: {count}")
    dashboard_lines.extend(["", "## 来源统计", ""])
    for collection_name, rows in collection_stats:
        dashboard_lines.append(f"- [[{ROOT_SOURCE}/{collection_pages[collection_name]}|{collection_name}]]: {len(rows)}")
    dashboard_lines.extend(["", "## 粗分类统计", ""])
    for label, count in sorted(
        coarse_counts.items(),
        key=lambda item: (COARSE_BUCKET_ORDER.index(item[0]) if item[0] in COARSE_BUCKET_ORDER else 999, -item[1], item[0]),
    ):
        dashboard_lines.append(f"- [[{ROOT_COARSE}/{base.sanitize_filename(label)}|{label}]]: {count}")
    dashboard_lines.extend(["", f"## {base.t('section_urls')}", "", "<details>"])
    dashboard_lines.append(f"<summary>{base.t('summary_show_all_urls').format(count=len(url_rows))}</summary>")
    dashboard_lines.append("")
    dashboard_lines.extend(url_rows)
    dashboard_lines.extend(["", "</details>", ""])
    (stage_root / dashboard_name()).write_text("\n".join(dashboard_lines), encoding="utf-8")

    return {
        "top_domains": top_domains_sorted,
        "top_domain_count": len(top_domains_sorted),
        "month_items": [(f"{year} / {base.month_label_from_number(month)}", count) for (year, month), count in month_items],
        "collection_items": [(name, len(rows)) for name, rows in collection_stats],
        "collection_count": len(by_collection),
        "coarse_counts": coarse_counts,
        "url_count": len(url_rows),
        "note_rows": note_rows,
        "max_domain_depth": max((len(key.split("/")) for key in by_domain.keys()), default=1),
        "max_domain_leaf_size": max((len(rows) for rows in by_domain.values()), default=0),
        "oversized_leaf_count": sum(1 for rows in by_domain.values() if len(rows) > base.MAX_DOMAIN_FILE_SIZE),
    }


def render_rubbish(stage_root: Path, removed_records: Sequence[Record]) -> int:
    rubbish_root = stage_root / root_rubbish_name()
    if not removed_records:
        ensure_managed_roots(stage_root)
        return 0
    rubbish_root.mkdir(parents=True, exist_ok=True)
    for record in removed_records:
        year = note_year(record.note_time)
        month_label = base.month_label_from_number(base.month_number(record.note_time))
        note_dir = rubbish_root / year if base.month_number(record.note_time) == 0 else rubbish_root / year / month_label
        note_dir.mkdir(parents=True, exist_ok=True)
        title = base.normalize_title(record.title or record.title_preview, fallback_note_title(record.note_id))
        note_path = unique_note_path(note_dir, title)
        note_path.write_text(build_rubbish_note_text(record, note_path.stem), encoding="utf-8")
    (rubbish_root / RUBBISH_KEEP_FILE).unlink(missing_ok=True)
    return len(removed_records)


def migrate_legacy_root_layout(output_root: Path) -> None:
    for old_name, new_name in LEGACY_ROOT_MAPPINGS.items():
        old_path = output_root / old_name
        new_path = output_root / new_name
        if not old_path.exists():
            continue
        if new_path.exists():
            if old_path.is_dir():
                base.merge_dir_tree(old_path, new_path)
                shutil.rmtree(old_path)
            else:
                base.merge_path_file(old_path, new_path)
                old_path.unlink()
            continue
        old_path.rename(new_path)


def replace_target(output_root: Path, stage_root: Path) -> None:
    removable = {
        root_date_name(),
        root_author_name(),
        root_domain_name(),
        ROOT_SOURCE,
        ROOT_COARSE,
        dashboard_name(),
    }
    backup_dir = Path(tempfile.mkdtemp(prefix="xhs-favorites-replace-"))
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        for entry in sorted(output_root.iterdir(), key=lambda path: path.name):
            normalized_name = base.strip_duplicate_suffix(entry.name)
            if entry.name not in removable and normalized_name not in removable:
                continue
            shutil.move(str(entry), str(backup_dir / entry.name))

        for name in (root_date_name(), root_author_name(), root_domain_name(), ROOT_SOURCE, ROOT_COARSE, dashboard_name()):
            source = stage_root / name
            if source.exists():
                shutil.move(str(source), str(output_root / name))

        for name in (root_search_name(), root_rubbish_name()):
            source = stage_root / name
            if not source.exists():
                continue
            target = output_root / name
            if target.exists():
                base.merge_dir_tree(source, target)
            else:
                shutil.move(str(source), str(target))
    finally:
        shutil.rmtree(backup_dir, ignore_errors=True)

    ensure_managed_roots(output_root)


def ensure_managed_roots(output_root: Path) -> None:
    search_root = output_root / root_search_name()
    rubbish_root = output_root / root_rubbish_name()
    search_root.mkdir(parents=True, exist_ok=True)
    rubbish_root.mkdir(parents=True, exist_ok=True)

    keep_file = rubbish_root / RUBBISH_KEEP_FILE
    visible_entries = [entry for entry in rubbish_root.iterdir() if not entry.name.startswith(".")]
    if visible_entries:
        keep_file.unlink(missing_ok=True)
    else:
        keep_file.write_text("", encoding="utf-8")


def normalize_output_tree(output_root: Path) -> None:
    base.normalize_date_tree(output_root / root_date_name())
    base.normalize_author_tree(output_root / root_author_name())
    base.normalize_domain_tree(output_root / root_domain_name())
    base.cleanup_duplicate_suffix_files(output_root / root_date_name())
    base.cleanup_duplicate_suffix_files(output_root / root_domain_name())
    base.cleanup_duplicate_suffix_files(output_root / ROOT_SOURCE)
    base.cleanup_duplicate_suffix_files(output_root / ROOT_COARSE)
    base.cleanup_duplicate_suffix_files(output_root / root_search_name())
    base.cleanup_duplicate_suffix_files(output_root / root_rubbish_name())
    base.cleanup_root_duplicate_files(output_root)
    base.cleanup_empty_duplicate_dirs(output_root / root_date_name())
    base.cleanup_empty_duplicate_dirs(output_root / root_domain_name())
    base.cleanup_empty_duplicate_dirs(output_root / ROOT_SOURCE)
    base.cleanup_empty_duplicate_dirs(output_root / ROOT_COARSE)
    base.cleanup_empty_duplicate_dirs(output_root / root_search_name())
    base.cleanup_empty_duplicate_dirs(output_root / root_rubbish_name())
    ensure_managed_roots(output_root)


def validate_output(output_root: Path, expected_notes: int) -> Tuple[int, int]:
    date_root = output_root / root_date_name()
    if not date_root.exists():
        return 0, 0
    md_count = 0
    note_count = 0
    for note_path in date_root.rglob("*.md"):
        md_count += 1
        if note_path.name == index_name():
            continue
        text = note_path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r'^note_id:\s*".+"$', text, re.MULTILINE):
            note_count += 1
    if note_count != expected_notes:
        raise RuntimeError(f"favorite note count mismatch after write: {note_count} != expected {expected_notes}")
    return md_count, note_count


def sync_archive(
    input_json: Path,
    target_root: Path,
    mode: str = "merge",
    classification: str = "auto",
    title_language: str = "zh",
    taxonomy_path: Optional[Path] = None,
    container_name: str = DEFAULT_CONTAINER_NAME,
) -> Dict[str, object]:
    if classification != "auto":
        raise ValueError("Only classification=auto is supported in this version")

    base.set_active_language(title_language)

    input_json = Path(input_json).expanduser().resolve()
    target_root = Path(target_root).expanduser().resolve()
    output_root = target_root / container_name

    if not input_json.exists():
        raise FileNotFoundError(f"input JSON not found: {input_json}")

    taxonomy_source = resolve_taxonomy_path(output_root, Path(taxonomy_path).expanduser().resolve() if taxonomy_path else None)
    if not taxonomy_source.exists():
        raise FileNotFoundError(f"taxonomy file not found: {taxonomy_source}")
    taxonomy_rules = base.load_manual_rules(taxonomy_source)

    migrate_legacy_root_layout(output_root)
    existing = parse_existing_records(output_root) if mode == "merge" else {}
    incoming, collection_estimates, imported_at = parse_input_records(input_json, taxonomy_rules)

    merged: Dict[str, Record] = {}
    for note_id, incoming_record in incoming.items():
        merged[note_id] = merge_records(existing.get(note_id), incoming_record, taxonomy_rules)

    removed_ids = sorted(set(existing.keys()) - set(incoming.keys()))
    removed_records = [existing[note_id] for note_id in removed_ids]

    local_build_root = base.local_build_root_for_target(target_root, container_name)
    if local_build_root is not None:
        stage_parent = local_build_root.parent
        if local_build_root.exists():
            shutil.rmtree(local_build_root)
        local_build_root.mkdir(parents=True, exist_ok=True)
        stage_root = local_build_root
    else:
        stage_parent = Path(tempfile.mkdtemp(prefix="xhs-favorites-sync-"))
        stage_root = stage_parent / container_name
        stage_root.mkdir(parents=True, exist_ok=True)

    try:
        render_result = render_structure(stage_root, merged, collection_estimates, existing_root=output_root if mode == "merge" else None)
        rubbish_moved = render_rubbish(stage_root, removed_records)
        replace_target(output_root, stage_root)
        ensure_local_root_taxonomy(output_root, taxonomy_source)
        normalize_output_tree(output_root)
        md_count, note_count = validate_output(output_root, len(merged))
    finally:
        if local_build_root is None:
            shutil.rmtree(stage_parent, ignore_errors=True)

    summary = {
        "input_json": str(input_json),
        "output_root": str(output_root),
        "mode": mode,
        "classification": classification,
        "title_language": title_language,
        "taxonomy_source": str(taxonomy_source),
        "existing_before": len(existing),
        "incoming": len(incoming),
        "final_notes": len(merged),
        "final_note_files": note_count,
        "final_md_files_under_date": md_count,
        "rubbish_moved": len(removed_records),
        "collection_count": render_result["collection_count"],
        "top_domains": render_result["top_domains"],
        "top_domain_count": render_result["top_domain_count"],
        "month_stats": render_result["month_items"],
        "collection_stats": render_result["collection_items"],
        "url_count": render_result["url_count"],
        "max_domain_leaf_size": render_result["max_domain_leaf_size"],
        "max_domain_depth": render_result["max_domain_depth"],
        "oversized_leaf_count": render_result["oversized_leaf_count"],
        "imported_at": imported_at,
    }
    return summary


def main() -> None:
    args = parse_args()
    summary = sync_archive(
        input_json=Path(args.input_json),
        target_root=Path(args.target_root),
        mode=args.mode,
        classification=args.classification,
        title_language=args.title_language,
        taxonomy_path=Path(args.taxonomy_path) if args.taxonomy_path else None,
        container_name=args.container_name,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
