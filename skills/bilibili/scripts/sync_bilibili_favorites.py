#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
ROOT_TAXONOMY_FILENAME = "ROOT分类目录.md"
DEFAULT_CONTAINER_NAME = "B站"
DEFAULT_TAXONOMY_PATH = Path(
    "/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources/书签库/ROOT分类目录.md"
)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DATE_DIRNAME = "01 日期"
LEGACY_DATE_DIRNAMES = (DATE_DIRNAME, "01 Date")
AUTHOR_DIRNAME = "02 UP主"
LEGACY_AUTHOR_DIRNAMES = (AUTHOR_DIRNAME, "02 Author")
FOLDER_DIRNAME = "03 收藏夹"
LEGACY_FOLDER_DIRNAMES = (FOLDER_DIRNAME, "03 Folder")
DOMAIN_DIRNAME = "04 领域"
LEGACY_DOMAIN_DIRNAMES = (DOMAIN_DIRNAME, "04 Domain")
COARSE_DOMAIN_DIRNAME = "05 粗分类"
SEARCH_DIRNAME = "06 搜索"
LEGACY_SEARCH_DIRNAMES = (SEARCH_DIRNAME, "06 Search", "05 Search")
RUBBISH_DIRNAME = "07 废弃"
LEGACY_RUBBISH_DIRNAMES = (RUBBISH_DIRNAME, "07 Rubbish", "06 Rubbish")
RUBBISH_PLACEHOLDER = ".keep"
COARSE_SPLIT_MAX_LINES = 50
LANG_PACKS = {
    "zh": {
        "fallback_video_prefix": "视频",
        "note_link_label": "B站链接",
        "note_up_label": "UP主",
        "note_fav_time_label": "收藏时间",
        "note_publish_time_label": "发布时间",
        "note_folders_label": "来源收藏夹",
        "note_domain_label": "域分类",
        "note_cover_label": "封面",
        "note_intro_heading": "简介",
        "unknown": "未知",
        "no_intro": "暂无简介。",
        "bucket_count_label": "条目数",
        "bucket_items_heading": "条目",
        "dashboard_title": "B站收藏仪表盘",
        "dashboard_total": "总视频数",
        "dashboard_folders": "收藏夹数",
        "dashboard_new": "新增数量",
        "dashboard_month_heading": "按月统计",
        "dashboard_up_heading": "按 UP 主统计",
        "dashboard_folder_heading": "按收藏夹统计",
        "dashboard_domain_heading": "按 Domain 统计",
        "domain_uncategorized": "未分类",
        "unknown_up": "未知UP主",
        "untitled_folder": "未命名收藏夹",
    },
    "en": {
        "fallback_video_prefix": "Video",
        "note_link_label": "Bilibili URL",
        "note_up_label": "UP",
        "note_fav_time_label": "Favorited At",
        "note_publish_time_label": "Published At",
        "note_folders_label": "Source Folders",
        "note_domain_label": "Domain",
        "note_cover_label": "Cover",
        "note_intro_heading": "Summary",
        "unknown": "Unknown",
        "no_intro": "No summary available.",
        "bucket_count_label": "Items",
        "bucket_items_heading": "Entries",
        "dashboard_title": "Bilibili Favorites Dashboard",
        "dashboard_total": "Total Videos",
        "dashboard_folders": "Folder Count",
        "dashboard_new": "New Items",
        "dashboard_month_heading": "By Month",
        "dashboard_up_heading": "By UP",
        "dashboard_folder_heading": "By Folder",
        "dashboard_domain_heading": "By Domain",
        "domain_uncategorized": "Uncategorized",
        "unknown_up": "Unknown UP",
        "untitled_folder": "Untitled Folder",
    },
}
ACTIVE_LANG = "zh"
COARSE_BUCKET_ORDER = [
    "AI与前沿科技",
    "学习成长",
    "工具效率",
    "商业职场",
    "生活见闻",
    "资源内容",
    "创作设计",
]


@dataclass
class FavoriteRecord:
    record_id: str
    item_id: str
    bvid: str
    title: str
    video_url: str
    up_name: str
    fav_time: str
    publish_time: str
    intro: str
    cover_url: str
    folder_ids: List[str] = field(default_factory=list)
    folder_names: List[str] = field(default_factory=list)
    folder_refs: List[Dict[str, str]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    domain_parts: List[str] = field(default_factory=list)
    source_category_paths: List[List[str]] = field(default_factory=list)
    raw_media: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CoarseBucketRule:
    name: str
    domain_prefixes: List[List[str]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Bilibili favorites to local Obsidian Markdown structure.")
    parser.add_argument("--target-root", required=True, help="Root path XX. Output is XX/B站收藏/")
    parser.add_argument("--input-json", help="Optional JSON payload from the Bilibili fetch helper")
    parser.add_argument("--container-name", default=DEFAULT_CONTAINER_NAME, help="Container folder inside target root")
    parser.add_argument("--mode", choices=["merge", "create"], required=True)
    parser.add_argument("--classification", choices=["auto", "manual"], required=True)
    parser.add_argument("--manual-rules", help="Optional Markdown taxonomy path to override the default ROOT taxonomy")
    parser.add_argument("--title-language", choices=["zh", "en"], default="zh")
    parser.add_argument("--helper-script", help="Optional fetch helper script path")
    return parser.parse_args()


def set_active_language(lang: str) -> None:
    global ACTIVE_LANG
    ACTIVE_LANG = lang if lang in LANG_PACKS else "zh"


def t(key: str) -> str:
    return LANG_PACKS[ACTIVE_LANG][key]


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def dedupe_strings(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values:
        text = clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def sorted_strings(values: Iterable[str]) -> List[str]:
    return sorted(dedupe_strings(values), key=lambda item: item.casefold())


def normalize_folder_ref(folder_id: Any, folder_name: Any) -> Dict[str, str]:
    return {"id": clean_text(folder_id), "name": clean_text(folder_name)}


def dedupe_folder_refs(values: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[Tuple[str, str]] = set()
    out: List[Dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        item = normalize_folder_ref(value.get("id"), value.get("name"))
        if not item["id"] and not item["name"]:
            continue
        key = (item["id"], item["name"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return sorted(out, key=lambda item: (item["name"].casefold(), item["id"]))


def record_folder_refs(record: FavoriteRecord) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = list(record.folder_refs)
    if len(record.folder_ids) == len(record.folder_names):
        refs.extend({"id": folder_id, "name": folder_name} for folder_id, folder_name in zip(record.folder_ids, record.folder_names))
    elif record.folder_names:
        refs.extend({"id": "", "name": folder_name} for folder_name in record.folder_names)
    return dedupe_folder_refs(refs)


def dedupe_paths(values: Iterable[Sequence[str]]) -> List[List[str]]:
    seen: set[Tuple[str, ...]] = set()
    out: List[List[str]] = []
    for parts in values:
        clean_parts = tuple(clean_text(part) for part in parts if clean_text(part))
        if not clean_parts or clean_parts in seen:
            continue
        seen.add(clean_parts)
        out.append(list(clean_parts))
    return out


def sanitize_filename(value: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]', " ", clean_text(value))
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return text or "untitled"


def slug_suffix(record_id: str) -> str:
    return record_id[-6:] if len(record_id) >= 6 else record_id


def json_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


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
            values[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            values[key] = raw_value.strip('"').strip("'")
    return values, text[match.end() :]


def iso_from_epoch(raw_value: Any) -> str:
    if raw_value in (None, "", 0, "0"):
        return ""
    try:
        stamp = int(raw_value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(stamp, tz=timezone.utc).astimezone(SHANGHAI_TZ).isoformat(timespec="seconds")


def parse_iso_or_now(value: str) -> datetime:
    text = clean_text(value)
    if not text:
        return datetime.now(tz=SHANGHAI_TZ)
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(SHANGHAI_TZ)
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=SHANGHAI_TZ)
        return dt.astimezone(SHANGHAI_TZ)
    except ValueError:
        return datetime.now(tz=SHANGHAI_TZ)


def month_folder_name(dt: datetime) -> str:
    return f"{dt.month} 月"


def fallback_title(record_id: str) -> str:
    return f"{t('fallback_video_prefix')} {slug_suffix(record_id)}"


@lru_cache(maxsize=1)
def load_taxonomy_module():
    taxonomy_path = Path(__file__).resolve().parents[2] / "x-likes" / "scripts" / "taxonomy_reference.py"
    spec = importlib.util.spec_from_file_location("bilibili_taxonomy_reference", taxonomy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load taxonomy module from {taxonomy_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["bilibili_taxonomy_reference"] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_filters_module():
    filters_path = Path(__file__).resolve().with_name("bilibili_record_filters.py")
    spec = importlib.util.spec_from_file_location("bilibili_record_filters_runtime", filters_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load filters module from {filters_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["bilibili_record_filters_runtime"] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=16)
def load_taxonomy_reference(path: str):
    module = load_taxonomy_module()
    return module.parse_taxonomy_reference_markdown(Path(path))


def resolve_taxonomy_path(output_root: Path, classification: str, manual_rules_arg: Optional[str]) -> Path:
    del classification
    if manual_rules_arg:
        manual_path = Path(manual_rules_arg).expanduser().resolve()
        if manual_path.exists():
            return manual_path
        raise FileNotFoundError(f"manual taxonomy not found: {manual_path}")

    local_taxonomy = output_root / DOMAIN_DIRNAME / ROOT_TAXONOMY_FILENAME
    if local_taxonomy.exists():
        return local_taxonomy

    if DEFAULT_TAXONOMY_PATH.exists():
        return DEFAULT_TAXONOMY_PATH

    raise FileNotFoundError(f"default taxonomy not found: {DEFAULT_TAXONOMY_PATH}")


def ensure_local_root_taxonomy(output_root: Path, source_path: Path) -> None:
    domain_root = output_root / DOMAIN_DIRNAME
    domain_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, domain_root / ROOT_TAXONOMY_FILENAME)


def classify_domain_parts(record: FavoriteRecord, taxonomy_path: Path) -> List[str]:
    reference = load_taxonomy_reference(str(taxonomy_path))
    module = load_taxonomy_module()
    override = bilibili_override_domain_parts(record, reference)
    if override:
        return override
    record_dict = {
        "title": record.title,
        "content": " ".join(
            part
            for part in [
                record.intro,
                record.up_name,
                " ".join(record.folder_names),
                " ".join(record.tags),
                " ".join(record.keywords),
            ]
            if clean_text(part)
        ),
        "url": record.video_url,
        "host": urlparse(record.video_url).netloc,
        "source_category_paths": [],
    }
    chosen_path, _mode = module.classify_record_semantically(record_dict, reference)
    if chosen_path and chosen_path[0] == reference.root_label:
        return list(chosen_path[1:])
    return list(chosen_path)


def bilibili_override_domain_parts(record: FavoriteRecord, reference: Any) -> List[str]:
    text = " ".join(
        part
        for part in [
            record.title,
            record.intro,
            record.up_name,
            " ".join(record.folder_names),
            " ".join(record.tags),
            " ".join(record.keywords),
        ]
        if clean_text(part)
    ).lower()

    rules = [
        (
            any(token in text for token in ["拼多多", "天猫", "淘宝", "电商", "品牌店", "店铺运营"]),
            ["工具", "各行各业", "电商采销"],
        ),
        (
            any(token in text for token in ["吴恩达", "论文", "精读论文", "学习路线", "教程", "课程"]) and any(
                token in text for token in ["ai", "agent", "大模型", "deepseek", "人工智能"]
            ),
            ["信息", "学习充电", "AI学习指南"],
        ),
        (
            any(token in text for token in ["共享单车", "避坑", "出行", "安全提醒", "生活常识"]),
            ["信息", "生活百科", "个人生活"],
        ),
        (
            any(token in text for token in ["逆袭", "励志", "成长", "人生", "自律", "习惯", "心态"]),
            ["信息", "学习充电", "个人成长"],
        ),
    ]

    ref_paths = set(reference.reference_paths)
    for matched, desired in rules:
        if matched and (reference.root_label, *desired) in ref_paths:
            return desired
    return []


def media_value(media: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = media.get(key)
        if value is not None and clean_text(value):
            return clean_text(value)
    return ""


def is_empty_media_payload(media: Dict[str, Any]) -> bool:
    title = clean_text(media.get("title"))
    bvid = media_value(media, "bvid", "bv_id")
    intro = clean_text(media.get("intro"))
    cover = clean_text(media.get("cover") or media.get("pic"))
    if title or bvid:
        return False
    return not intro and not cover


def prune_unwanted_records(records: Dict[str, FavoriteRecord]) -> Tuple[Dict[str, FavoriteRecord], set[str]]:
    filters = load_filters_module()
    kept: Dict[str, FavoriteRecord] = {}
    removed: set[str] = set()
    for record_id, record in records.items():
        recordish = {
            "title": record.title,
            "video_url": record.video_url,
            "raw_media": record.raw_media,
        }
        if filters.is_invalid_bilibili_media(recordish):
            removed.add(record_id)
            continue
        if is_empty_media_payload(record.raw_media) and not record.video_url:
            removed.add(record_id)
            continue
        kept[record_id] = record
    return kept, removed


def record_from_media(folder_id: str, folder_name: str, media: Dict[str, Any], taxonomy_path: Path) -> FavoriteRecord:
    item_id = clean_text(media.get("id"))
    bvid = media_value(media, "bvid", "bv_id")
    record_id = bvid or item_id or hashlib.sha1(json.dumps(media, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    title = media_value(media, "title") or fallback_title(record_id)
    intro = media_value(media, "intro")
    video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else media_value(media, "short_link", "share_url")
    cover_url = media_value(media, "cover", "pic")
    upper = media.get("upper") if isinstance(media.get("upper"), dict) else {}
    up_name = clean_text(upper.get("name"))
    tags = dedupe_strings(media.get("tags", []) if isinstance(media.get("tags"), list) else [])
    keywords = dedupe_strings(media.get("keywords", []) if isinstance(media.get("keywords"), list) else [])
    source_category_paths = dedupe_paths([[folder_name]])
    folder_ref = normalize_folder_ref(folder_id, folder_name)
    record = FavoriteRecord(
        record_id=record_id,
        item_id=item_id or record_id,
        bvid=bvid,
        title=title,
        video_url=video_url or "",
        up_name=up_name,
        fav_time=iso_from_epoch(media.get("fav_time") or media.get("ctime")),
        publish_time=iso_from_epoch(media.get("pubtime") or media.get("ctime")),
        intro=intro,
        cover_url=cover_url,
        folder_ids=dedupe_strings([folder_ref["id"]]),
        folder_names=dedupe_strings([folder_ref["name"]]),
        folder_refs=dedupe_folder_refs([folder_ref]),
        tags=tags,
        keywords=keywords,
        domain_parts=[],
        source_category_paths=source_category_paths,
        raw_media=media,
    )
    record.domain_parts = classify_domain_parts(record, taxonomy_path)
    return record


def merge_record_values(base: FavoriteRecord, other: FavoriteRecord) -> FavoriteRecord:
    merged_folder_refs = dedupe_folder_refs([*record_folder_refs(base), *record_folder_refs(other)])
    merged = FavoriteRecord(
        record_id=base.record_id,
        item_id=other.item_id or base.item_id,
        bvid=other.bvid or base.bvid,
        title=other.title or base.title,
        video_url=other.video_url or base.video_url,
        up_name=other.up_name or base.up_name,
        fav_time=other.fav_time or base.fav_time,
        publish_time=other.publish_time or base.publish_time,
        intro=other.intro or base.intro,
        cover_url=other.cover_url or base.cover_url,
        folder_ids=sorted_strings([item["id"] for item in merged_folder_refs]),
        folder_names=sorted_strings([item["name"] for item in merged_folder_refs]),
        folder_refs=merged_folder_refs,
        tags=sorted_strings([*base.tags, *other.tags]),
        keywords=sorted_strings([*base.keywords, *other.keywords]),
        domain_parts=other.domain_parts or base.domain_parts,
        source_category_paths=dedupe_paths([*base.source_category_paths, *other.source_category_paths]),
        raw_media=other.raw_media or base.raw_media,
    )
    return merged


def normalize_payload(payload: Dict[str, Any], taxonomy_path: Path) -> Dict[str, FavoriteRecord]:
    records: Dict[str, FavoriteRecord] = {}
    items = payload.get("items", [])
    if not isinstance(items, list):
        return records
    filters = load_filters_module()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        media = entry.get("media")
        if not isinstance(media, dict):
            continue
        if filters.is_invalid_bilibili_media(entry) or filters.is_invalid_bilibili_media(media):
            continue
        if is_empty_media_payload(media):
            continue
        folder_id = clean_text(entry.get("folder_id"))
        folder_name = clean_text(entry.get("folder_name")) or t("untitled_folder")
        record = record_from_media(folder_id, folder_name, media, taxonomy_path)
        existing = records.get(record.record_id)
        records[record.record_id] = merge_record_values(existing, record) if existing else record
    return records


def merge_records(
    existing: Dict[str, FavoriteRecord],
    incoming: Dict[str, FavoriteRecord],
) -> Tuple[Dict[str, FavoriteRecord], set[str]]:
    merged = dict(existing)
    new_ids: set[str] = set()
    for record_id, record in incoming.items():
        if record_id in merged:
            merged[record_id] = merge_record_values(merged[record_id], record)
        else:
            merged[record_id] = record
            new_ids.add(record_id)
    return merged, new_ids


def sync_records_authoritative(
    existing: Dict[str, FavoriteRecord],
    incoming: Dict[str, FavoriteRecord],
) -> Tuple[Dict[str, FavoriteRecord], set[str], set[str]]:
    synced = dict(incoming)
    existing_ids = set(existing)
    incoming_ids = set(incoming)
    new_ids = incoming_ids - existing_ids
    removed_ids = existing_ids - incoming_ids
    return synced, new_ids, removed_ids


def favorite_record_from_frontmatter(frontmatter: Dict[str, Any]) -> Optional[FavoriteRecord]:
    record_id = clean_text(frontmatter.get("record_id"))
    if not record_id:
        return None
    raw_folder_refs = frontmatter.get("folder_refs", [])
    folder_refs = dedupe_folder_refs(raw_folder_refs if isinstance(raw_folder_refs, list) else [])
    if not folder_refs:
        folder_ids = frontmatter.get("folder_ids", [])
        folder_names = frontmatter.get("folder_names", [])
        if isinstance(folder_ids, list) and isinstance(folder_names, list) and len(folder_ids) == len(folder_names):
            folder_refs = dedupe_folder_refs(
                [{"id": folder_id, "name": folder_name} for folder_id, folder_name in zip(folder_ids, folder_names)]
            )
        else:
            folder_refs = dedupe_folder_refs([{"id": "", "name": name} for name in frontmatter.get("folder_names", [])])
    return FavoriteRecord(
        record_id=record_id,
        item_id=clean_text(frontmatter.get("item_id")) or record_id,
        bvid=clean_text(frontmatter.get("bvid")),
        title=clean_text(frontmatter.get("title")) or fallback_title(record_id),
        video_url=clean_text(frontmatter.get("video_url")),
        up_name=clean_text(frontmatter.get("up_name")),
        fav_time=clean_text(frontmatter.get("fav_time")),
        publish_time=clean_text(frontmatter.get("publish_time")),
        intro=clean_text(frontmatter.get("intro")),
        cover_url=clean_text(frontmatter.get("cover_url")),
        folder_ids=sorted_strings([item["id"] for item in folder_refs]),
        folder_names=sorted_strings([item["name"] for item in folder_refs]),
        folder_refs=folder_refs,
        tags=dedupe_strings(frontmatter.get("tags", [])),
        keywords=dedupe_strings(frontmatter.get("keywords", [])),
        domain_parts=dedupe_strings(frontmatter.get("domain_parts", [])),
        source_category_paths=dedupe_paths(frontmatter.get("source_category_paths", [])),
        raw_media=frontmatter.get("raw_media", {}) if isinstance(frontmatter.get("raw_media"), dict) else {},
    )


def parse_existing_records(date_root: Path) -> Dict[str, FavoriteRecord]:
    records: Dict[str, FavoriteRecord] = {}
    if not date_root.exists():
        return records
    for note in sorted(date_root.rglob("*.md")):
        if note.name == "Index.md":
            continue
        frontmatter, _body = parse_frontmatter(note)
        record = favorite_record_from_frontmatter(frontmatter)
        if record is None:
            continue
        records[record.record_id] = record
    return records


def markdown_link(from_path: Path, target_path: Path, label: str) -> str:
    relative = os.path.relpath(target_path, from_path.parent).replace(os.sep, "/")
    return f"[{label}]({relative})"


def note_filename(record: FavoriteRecord, used_names: set[str]) -> str:
    base = sanitize_filename(record.title)
    candidate = base
    if candidate in used_names:
        candidate = f"{base} - {slug_suffix(record.record_id)}"
    used_names.add(candidate)
    return f"{candidate}.md"


def primary_note_path(record: FavoriteRecord, output_root: Path, used_names_by_month: Dict[Tuple[str, str], set[str]]) -> Path:
    fav_dt = parse_iso_or_now(record.fav_time)
    year_name = str(fav_dt.year)
    month_name = month_folder_name(fav_dt)
    key = (year_name, month_name)
    used_names = used_names_by_month.setdefault(key, set())
    filename = note_filename(record, used_names)
    return output_root / DATE_DIRNAME / year_name / month_name / filename


def frontmatter_for_record(record: FavoriteRecord) -> Dict[str, Any]:
    return asdict(record)


def write_markdown(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_rule_domain_prefix(value: str) -> List[str]:
    return [clean_text(part) for part in value.split("/") if clean_text(part)]


def default_coarse_rules() -> List[CoarseBucketRule]:
    return [
        CoarseBucketRule(
            "AI与前沿科技",
            domain_prefixes=[["工具", "人工智能"], ["工具", "编程开发"]],
            keywords=["ai", "agent", "deepseek", "openai", "claude", "cursor", "coze", "n8n", "大模型", "智能体", "编程", "代码", "开发", "模型", "论文"],
        ),
        CoarseBucketRule(
            "学习成长",
            domain_prefixes=[["信息", "学习充电"]],
            keywords=["学习", "课程", "教程", "读书", "英语", "口语", "心理", "成长", "自律", "方法", "教育"],
        ),
        CoarseBucketRule(
            "工具效率",
            domain_prefixes=[["工具", "办公效率"], ["工具", "在线工具"], ["工具", "电脑装机"], ["工具", "软件APP"]],
            keywords=["办公", "工具", "插件", "软件", "app", "效率", "mac", "windows", "浏览器", "notion", "obsidian"],
        ),
        CoarseBucketRule(
            "商业职场",
            domain_prefixes=[["工具", "各行各业"]],
            keywords=["电商", "店铺", "运营", "求职", "简历", "面试", "副业", "商业", "财经", "营销", "职场", "创业", "赚钱"],
        ),
        CoarseBucketRule(
            "生活见闻",
            domain_prefixes=[["信息", "生活百科"], ["信息", "热点资讯"]],
            keywords=["生活", "健康", "出行", "安全", "社会", "新闻", "情感", "育儿", "吃", "睡", "避坑", "共享单车"],
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
        "FORMAT: BILIBILI_COARSE_V1",
        "",
        "## 说明",
        "",
        "- 这个文档是 `05 粗分类/` 的唯一规则来源。",
        "- 以后如果你要调整粗分类，请直接编辑这里，再重新运行同步脚本。",
        "- 匹配按从上到下顺序执行；先命中的规则优先。",
        "- `domain-prefix` 用 `A / B` 这样的路径前缀表示。",
        "- `keyword` 为大小写不敏感的文本匹配。",
        "- 如果某条视频没有命中任何规则，会落到 `未分类`。",
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
    lines = path.read_text(encoding="utf-8").splitlines()
    rules: List[CoarseBucketRule] = []
    current: Optional[CoarseBucketRule] = None
    for raw_line in lines:
        stripped = raw_line.strip()
        heading = re.match(r"^###\s+(.+?)\s*$", stripped)
        if heading:
            current = CoarseBucketRule(name=clean_text(heading.group(1)))
            rules.append(current)
            continue
        bullet = re.match(r"^-\s+([a-zA-Z-]+):\s*(.+?)\s*$", stripped)
        if not bullet or current is None:
            continue
        key, value = bullet.groups()
        key = key.lower()
        if key == "domain-prefix":
            parts = parse_rule_domain_prefix(value)
            if parts:
                current.domain_prefixes.append(parts)
        elif key == "keyword":
            token = clean_text(value).lower()
            if token:
                current.keywords.append(token)
    return [rule for rule in rules if rule.name]


def coarse_index_path(root: Path) -> Path:
    return root / COARSE_DOMAIN_DIRNAME / "Index.md"


def resolve_coarse_index_source(existing_root: Optional[Path]) -> Optional[Path]:
    if existing_root is None:
        return None
    candidate = coarse_index_path(existing_root)
    if candidate.exists():
        return candidate
    return None


def load_coarse_rules(existing_root: Optional[Path]) -> Tuple[List[CoarseBucketRule], str]:
    source = resolve_coarse_index_source(existing_root)
    if source is not None:
        rules = parse_coarse_index_markdown(source)
        if rules:
            return rules, source.read_text(encoding="utf-8")
    return default_coarse_rules(), default_coarse_index_markdown()


def ensure_coarse_index_doc(coarse_root: Path, source_text: str) -> Path:
    index_path = coarse_root / "Index.md"
    index_path.write_text(source_text, encoding="utf-8")
    return index_path


def resolve_existing_stable_root(existing_root: Optional[Path], candidate_names: Sequence[str]) -> Optional[Path]:
    if existing_root is None:
        return None
    for name in candidate_names:
        candidate = existing_root / name
        if candidate.exists():
            return candidate
    return None


def ensure_search_root(stage_root: Path, existing_root: Optional[Path] = None) -> Path:
    search_root = stage_root / SEARCH_DIRNAME
    if search_root.exists():
        shutil.rmtree(search_root)
    existing_search = resolve_existing_stable_root(existing_root, LEGACY_SEARCH_DIRNAMES)
    if existing_search is not None:
        shutil.copytree(existing_search, search_root)
    else:
        search_root.mkdir(parents=True, exist_ok=True)
    return search_root


def ensure_rubbish_root(stage_root: Path, existing_root: Optional[Path] = None) -> Path:
    rubbish_root = stage_root / RUBBISH_DIRNAME
    if rubbish_root.exists():
        shutil.rmtree(rubbish_root)
    existing_rubbish = resolve_existing_stable_root(existing_root, LEGACY_RUBBISH_DIRNAMES)
    if existing_rubbish is not None:
        shutil.copytree(existing_rubbish, rubbish_root)
    else:
        rubbish_root.mkdir(parents=True, exist_ok=True)
    placeholder = rubbish_root / RUBBISH_PLACEHOLDER
    if not placeholder.exists():
        placeholder.write_text("", encoding="utf-8")
    return rubbish_root


def render_primary_notes(output_root: Path, records: Dict[str, FavoriteRecord]) -> Dict[str, Path]:
    note_paths: Dict[str, Path] = {}
    used_names_by_month: Dict[Tuple[str, str], set[str]] = {}
    ordered = sorted(records.values(), key=lambda rec: (rec.fav_time, rec.record_id), reverse=True)
    for record in ordered:
        note_path = primary_note_path(record, output_root, used_names_by_month)
        frontmatter = frontmatter_for_record(record)
        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {json_scalar(value)}")
        lines.extend(
            [
                "---",
                "",
                f"# {record.title}",
                "",
                f"- {t('note_link_label')}：{record.video_url or 'N/A'}",
                f"- {t('note_up_label')}：{record.up_name or t('unknown')}",
                f"- {t('note_fav_time_label')}：{record.fav_time or t('unknown')}",
                f"- {t('note_publish_time_label')}：{record.publish_time or t('unknown')}",
                f"- {t('note_folders_label')}：{', '.join(record.folder_names) or t('unknown')}",
                f"- {t('note_domain_label')}：{' / '.join(record.domain_parts) if record.domain_parts else t('domain_uncategorized')}",
                f"- {t('note_cover_label')}：{record.cover_url or 'N/A'}",
                "",
                f"## {t('note_intro_heading')}",
                "",
                record.intro or t("no_intro"),
                "",
            ]
        )
        write_markdown(note_path, lines)
        note_paths[record.record_id] = note_path
    return note_paths


def render_bucket_index(
    path: Path,
    title: str,
    rows: Sequence[Tuple[str, FavoriteRecord, Path]],
) -> None:
    lines = [
        f"# {title}",
        "",
        f"- {t('bucket_count_label')}：`{len(rows)}`",
        "",
        f"## {t('bucket_items_heading')}",
        "",
    ]
    append_bucket_rows(lines, rows, path)
    lines.append("")
    write_markdown(path, lines)


def bucket_row_lines(record: FavoriteRecord, note_path: Path, bucket_path: Path) -> List[str]:
    lines = [f"- {markdown_link(bucket_path, note_path, record.title)}"]
    lines.append(f"  {t('note_up_label')}：{record.up_name or t('unknown')} | {t('note_fav_time_label')}：{record.fav_time or t('unknown')}")
    if record.video_url:
        lines.append(f"  {t('note_link_label')}：{record.video_url}")
    return lines


def append_bucket_rows(lines: List[str], rows: Sequence[Tuple[str, FavoriteRecord, Path]], bucket_path: Path) -> None:
    for record_id, record, note_path in rows:
        del record_id
        lines.extend(bucket_row_lines(record, note_path, bucket_path))


def estimate_bucket_lines(rows: Sequence[Tuple[str, FavoriteRecord, Path]], bucket_path: Path) -> int:
    base_lines = 6
    total = base_lines
    for _record_id, record, note_path in rows:
        total += len(bucket_row_lines(record, note_path, bucket_path))
    return total


def folder_catalog_from_payload(raw_folders: Any, records: Dict[str, FavoriteRecord]) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = []
    if isinstance(raw_folders, list):
        for item in raw_folders:
            if not isinstance(item, dict):
                continue
            refs.append(normalize_folder_ref(item.get("id"), item.get("title") or item.get("name")))
    for record in records.values():
        refs.extend(record.folder_refs)
    return dedupe_folder_refs(refs)


def flat_bucket_filename_map(refs: Sequence[Dict[str, str]]) -> Dict[Tuple[str, str], str]:
    casefold_counts: Dict[str, int] = {}
    for ref in refs:
        label = sanitize_filename(ref["name"] or ref["id"] or "bucket")
        casefold_counts[label.casefold()] = casefold_counts.get(label.casefold(), 0) + 1

    mapping: Dict[Tuple[str, str], str] = {}
    for ref in refs:
        label = sanitize_filename(ref["name"] or ref["id"] or "bucket")
        if casefold_counts[label.casefold()] > 1:
            label = f"{label} - {sanitize_filename(ref['id'] or 'bucket')}"
        mapping[(ref["id"], ref["name"])] = f"{label}.md"
    return mapping


def render_author_indexes(output_root: Path, records: Dict[str, FavoriteRecord], note_paths: Dict[str, Path]) -> None:
    buckets: Dict[str, List[Tuple[str, FavoriteRecord, Path]]] = {}
    for record_id, record in sorted(records.items()):
        author = record.up_name or t("unknown_up")
        buckets.setdefault(author, []).append((record_id, record, note_paths[record_id]))
    for author, rows in buckets.items():
        path = output_root / AUTHOR_DIRNAME / f"{sanitize_filename(author)}.md"
        render_bucket_index(path, author, rows)


def render_folder_indexes(
    output_root: Path,
    records: Dict[str, FavoriteRecord],
    note_paths: Dict[str, Path],
    folder_catalog: Sequence[Dict[str, str]],
) -> None:
    buckets: Dict[Tuple[str, str], List[Tuple[str, FavoriteRecord, Path]]] = {
        (ref["id"], ref["name"]): [] for ref in folder_catalog
    }
    for record_id, record in sorted(records.items()):
        refs = record_folder_refs(record)
        for ref in refs:
            buckets.setdefault((ref["id"], ref["name"]), []).append((record_id, record, note_paths[record_id]))

    filename_map = flat_bucket_filename_map(folder_catalog or [{"id": "", "name": t("untitled_folder")}])
    exact_name_counts: Dict[str, int] = {}
    for ref in folder_catalog:
        exact_name_counts[ref["name"]] = exact_name_counts.get(ref["name"], 0) + 1

    for ref in folder_catalog:
        key = (ref["id"], ref["name"])
        rows = buckets.get(key, [])
        title = ref["name"] or t("untitled_folder")
        if exact_name_counts.get(ref["name"], 0) > 1 and ref["id"]:
            title = f"{title} [fid:{ref['id']}]"
        filename = filename_map.get(key, f"{sanitize_filename(title)}.md")
        path = output_root / FOLDER_DIRNAME / filename
        render_bucket_index(path, title, rows)


def coarse_bucket_for_record(record: FavoriteRecord, rules: Optional[Sequence[CoarseBucketRule]] = None) -> str:
    parts = list(record.domain_parts)
    text = " ".join(
        part
        for part in [
            record.title,
            record.intro,
            record.up_name,
            " ".join(record.tags),
            " ".join(record.keywords),
            " / ".join(parts),
        ]
        if clean_text(part)
    ).lower()
    domain_path = parts
    active_rules = list(rules or default_coarse_rules())
    for rule in active_rules:
        if any(domain_path[: len(prefix)] == prefix for prefix in rule.domain_prefixes if prefix):
            return rule.name
    for rule in active_rules:
        if any(keyword in text for keyword in rule.keywords if keyword):
            return rule.name
    return t("domain_uncategorized")


def render_coarse_domain_indexes(
    output_root: Path,
    records: Dict[str, FavoriteRecord],
    note_paths: Dict[str, Path],
    existing_root: Optional[Path] = None,
) -> None:
    coarse_root = output_root / COARSE_DOMAIN_DIRNAME
    coarse_root.mkdir(parents=True, exist_ok=True)
    rules, source_text = load_coarse_rules(existing_root)
    ensure_coarse_index_doc(coarse_root, source_text)
    buckets: Dict[str, List[Tuple[str, FavoriteRecord, Path]]] = {}
    for record_id, record in sorted(records.items()):
        coarse_label = coarse_bucket_for_record(record, rules)
        buckets.setdefault(coarse_label, []).append((record_id, record, note_paths[record_id]))
    order = {label: index for index, label in enumerate([rule.name for rule in rules] or COARSE_BUCKET_ORDER)}
    for coarse_label, rows in sorted(buckets.items(), key=lambda item: (order.get(item[0], 999), -len(item[1]), item[0])):
        path = coarse_root / f"{sanitize_filename(coarse_label)}.md"
        render_coarse_bucket_index(path, coarse_label, rows)


def render_coarse_bucket_index(
    path: Path,
    title: str,
    rows: Sequence[Tuple[str, FavoriteRecord, Path]],
) -> None:
    lines = [
        f"# {title}",
        "",
        f"- {t('bucket_count_label')}：`{len(rows)}`",
        "",
    ]
    if estimate_bucket_lines(rows, path) <= COARSE_SPLIT_MAX_LINES:
        lines.extend([f"## {t('bucket_items_heading')}", ""])
        append_bucket_rows(lines, rows, path)
        lines.append("")
        write_markdown(path, lines)
        return

    grouped_by_second: Dict[str, List[Tuple[str, FavoriteRecord, Path]]] = {}
    for row in rows:
        record = row[1]
        second = record.domain_parts[1] if len(record.domain_parts) >= 2 else t("domain_uncategorized")
        grouped_by_second.setdefault(second, []).append(row)

    for second_label, second_rows in sorted(grouped_by_second.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.extend([f"## {second_label}", ""])
        subgroup_estimate = estimate_bucket_lines(second_rows, path)
        grouped_by_third: Dict[str, List[Tuple[str, FavoriteRecord, Path]]] = {}
        if subgroup_estimate > COARSE_SPLIT_MAX_LINES:
            for row in second_rows:
                record = row[1]
                third = record.domain_parts[2] if len(record.domain_parts) >= 3 else t("domain_uncategorized")
                grouped_by_third.setdefault(third, []).append(row)
        if grouped_by_third:
            for third_label, third_rows in sorted(grouped_by_third.items(), key=lambda item: (-len(item[1]), item[0])):
                lines.extend([f"### {third_label}", ""])
                append_bucket_rows(lines, third_rows, path)
                lines.append("")
        else:
            append_bucket_rows(lines, second_rows, path)
            lines.append("")
    write_markdown(path, lines)


def render_domain_indexes(output_root: Path, records: Dict[str, FavoriteRecord], note_paths: Dict[str, Path], taxonomy_path: Path) -> None:
    domain_root = output_root / DOMAIN_DIRNAME
    domain_root.mkdir(parents=True, exist_ok=True)
    ensure_local_root_taxonomy(output_root, taxonomy_path)

    reference = load_taxonomy_reference(str(taxonomy_path))
    branch_children: Dict[Tuple[str, ...], List[str]] = reference.children_by_parent

    leaf_rows: Dict[Tuple[str, ...], List[Tuple[str, FavoriteRecord, Path]]] = {}
    for record_id, record in sorted(records.items()):
        path_parts = tuple(record.domain_parts or [t("domain_uncategorized")])
        leaf_rows.setdefault(path_parts, []).append((record_id, record, note_paths[record_id]))

    for domain_parts, rows in leaf_rows.items():
        if len(domain_parts) == 1:
            leaf_path = domain_root / f"{sanitize_filename(domain_parts[-1])}.md"
        else:
            leaf_path = domain_root.joinpath(*[sanitize_filename(part) for part in domain_parts[:-1]]) / f"{sanitize_filename(domain_parts[-1])}.md"
        render_bucket_index(leaf_path, " / ".join(domain_parts), rows)

    paths_to_index: set[Tuple[str, ...]] = set()
    for parts in leaf_rows:
        for depth in range(1, len(parts)):
            paths_to_index.add(parts[:depth])

    for parts in sorted(paths_to_index, key=lambda item: (len(item), [part.lower() for part in item])):
        index_path = domain_root.joinpath(*[sanitize_filename(part) for part in parts]) / "Index.md"
        child_parts = (reference.root_label, *parts)
        lines = [f"# {' / '.join(parts)}", ""]
        direct_children = branch_children.get(tuple(child_parts), [])
        if direct_children:
            lines.extend(["## 子分类", ""])
            for child in direct_children:
                child_dir = index_path.parent / sanitize_filename(child)
                child_leaf = index_path.parent / f"{sanitize_filename(child)}.md"
                target = child_dir / "Index.md" if (tuple(parts) + (child,)) in paths_to_index else child_leaf
                lines.append(f"- {markdown_link(index_path, target, child)}")
            lines.append("")
        matching_rows = leaf_rows.get(parts, [])
        if matching_rows:
            lines.extend(["## 条目", ""])
            for _record_id, record, note_path in matching_rows:
                lines.append(f"- {markdown_link(index_path, note_path, record.title)}")
            lines.append("")
        write_markdown(index_path, lines)


def render_dashboard(
    output_root: Path,
    records: Dict[str, FavoriteRecord],
    new_record_ids: set[str],
    folder_catalog: Sequence[Dict[str, str]],
) -> None:
    month_counts: Dict[str, int] = {}
    author_counts: Dict[str, int] = {}
    domain_counts: Dict[str, int] = {}
    folder_counts: Dict[Tuple[str, str], int] = {(ref["id"], ref["name"]): 0 for ref in folder_catalog}
    exact_name_counts: Dict[str, int] = {}
    for ref in folder_catalog:
        exact_name_counts[ref["name"]] = exact_name_counts.get(ref["name"], 0) + 1
    for record in records.values():
        fav_dt = parse_iso_or_now(record.fav_time)
        month_key = f"{fav_dt.year}-{fav_dt.month:02d}"
        month_counts[month_key] = month_counts.get(month_key, 0) + 1
        author = record.up_name or t("unknown_up")
        author_counts[author] = author_counts.get(author, 0) + 1
        domain = " / ".join(record.domain_parts) if record.domain_parts else t("domain_uncategorized")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        for ref in record_folder_refs(record) or [{"id": "", "name": t("untitled_folder")}]:
            key = (ref["id"], ref["name"])
            folder_counts[key] = folder_counts.get(key, 0) + 1

    lines = [
        f"# {t('dashboard_title')}",
        "",
        f"- {t('dashboard_total')}：`{len(records)}`",
        f"- {t('dashboard_folders')}：`{len(folder_catalog)}`",
        f"- {t('dashboard_new')}：`{len(new_record_ids)}`",
        "",
        f"## {t('dashboard_month_heading')}",
        "",
    ]
    for month_key, count in sorted(month_counts.items(), reverse=True):
        lines.append(f"- {month_key}: {count}")
    lines.extend(["", f"## {t('dashboard_up_heading')}", ""])
    for author, count in sorted(author_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {author}: {count}")
    lines.extend(["", f"## {t('dashboard_folder_heading')}", ""])
    for (folder_id, folder_name), count in sorted(folder_counts.items(), key=lambda item: (-item[1], item[0][1], item[0][0])):
        display = folder_name or t("untitled_folder")
        if exact_name_counts.get(folder_name, 0) > 1 and folder_id:
            display = f"{display} [fid:{folder_id}]"
        lines.append(f"- {display}: {count}")
    lines.extend(["", f"## {t('dashboard_domain_heading')}", ""])
    for domain_name, count in sorted(domain_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {domain_name}: {count}")
    lines.append("")
    write_markdown(output_root / "Dashboard.md", lines)


def render_structure(
    output_root: Path,
    records: Dict[str, FavoriteRecord],
    new_record_ids: set[str],
    taxonomy_path: Path,
    raw_folders: Optional[Sequence[Dict[str, Any]]] = None,
    existing_root: Optional[Path] = None,
) -> Dict[str, int]:
    output_root.mkdir(parents=True, exist_ok=True)
    ensure_search_root(output_root, existing_root)
    ensure_rubbish_root(output_root, existing_root)
    note_paths = render_primary_notes(output_root, records)
    folder_catalog = folder_catalog_from_payload(raw_folders, records)
    render_author_indexes(output_root, records, note_paths)
    render_folder_indexes(output_root, records, note_paths, folder_catalog)
    render_coarse_domain_indexes(output_root, records, note_paths, existing_root)
    render_domain_indexes(output_root, records, note_paths, taxonomy_path)
    render_dashboard(output_root, records, new_record_ids, folder_catalog)
    return {
        "record_count": len(records),
        "folder_count": len(folder_catalog),
    }


def validate_output(root_dir: Path, expected_notes: int) -> Tuple[int, int]:
    required = [
        root_dir / DATE_DIRNAME,
        root_dir / AUTHOR_DIRNAME,
        root_dir / FOLDER_DIRNAME,
        root_dir / DOMAIN_DIRNAME,
        root_dir / COARSE_DOMAIN_DIRNAME,
        root_dir / SEARCH_DIRNAME,
        root_dir / RUBBISH_DIRNAME,
        root_dir / "Dashboard.md",
    ]
    for path in required:
        if not path.exists():
            raise AssertionError(f"missing output path: {path}")

    total_md_count = 0
    note_count = 0
    for note in root_dir.rglob("*.md"):
        total_md_count += 1
    for note in (root_dir / DATE_DIRNAME).rglob("*.md"):
        frontmatter, _body = parse_frontmatter(note)
        if clean_text(frontmatter.get("record_id")):
            note_count += 1
    if note_count != expected_notes:
        raise AssertionError(f"primary note count mismatch: {note_count} != {expected_notes}")
    return total_md_count, note_count


def strip_duplicate_suffix(name: str) -> str:
    name = name.strip()
    match = re.match(r"^(.*?)(?:\s+\d+|\s+\(\d+\))(\.[^.]+)?$", name)
    if not match:
        return name
    suffix = match.group(2) or ""
    return match.group(1).rstrip() + suffix


LEGACY_ROOT_RENAMES = {
    "01 Date": DATE_DIRNAME,
    "02 Author": AUTHOR_DIRNAME,
    "04 Domain": DOMAIN_DIRNAME,
    "06 Search": SEARCH_DIRNAME,
    "05 Search": SEARCH_DIRNAME,
    "07 Rubbish": RUBBISH_DIRNAME,
    "06 Rubbish": RUBBISH_DIRNAME,
}


def merge_path_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)
        return
    if source.read_text(encoding="utf-8", errors="ignore") == target.read_text(encoding="utf-8", errors="ignore"):
        return
    stem = target.stem
    suffix = target.suffix
    counter = 2
    while True:
        candidate = target.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            shutil.copy2(source, candidate)
            return
        counter += 1


def merge_dir_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in sorted(source.iterdir()):
        dest = target / item.name
        if item.is_dir():
            merge_dir_tree(item, dest)
        else:
            merge_path_file(item, dest)


def normalize_output_tree(root_dir: Path) -> None:
    if not root_dir.exists():
        return

    entries = sorted(root_dir.iterdir(), key=lambda path: (path.is_file(), path.name))
    for entry in entries:
        canonical_name = strip_duplicate_suffix(entry.name)
        canonical_name = LEGACY_ROOT_RENAMES.get(canonical_name, canonical_name)
        if canonical_name == entry.name:
            continue
        canonical = entry.with_name(canonical_name)
        if canonical.exists():
            if entry.is_dir():
                merge_dir_tree(entry, canonical)
                shutil.rmtree(entry)
            else:
                if entry.parent == root_dir:
                    entry.unlink()
                else:
                    merge_path_file(entry, canonical)
                    entry.unlink()
            continue
        entry.rename(canonical)


def run_delayed_duplicate_audit(
    root_dir: Path,
    delay_seconds: int = 60,
    expected_notes: Optional[int] = None,
) -> Optional[Tuple[int, int]]:
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    normalize_output_tree(root_dir)
    if expected_notes is not None and root_dir.exists():
        return validate_output(root_dir, expected_notes)
    return None


def codex_home_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()


def managed_state_root() -> Path:
    return codex_home_path() / "state" / "bilibili-favorites-to-obsidian"


def is_icloud_target_root(target_root: Path) -> bool:
    resolved = target_root.expanduser().resolve()
    mobile_documents_root = (Path.home() / "Library" / "Mobile Documents").expanduser().resolve()
    try:
        resolved.relative_to(mobile_documents_root)
        return True
    except ValueError:
        return False


def local_build_root_for_target(target_root: Path, container_name: str) -> Optional[Path]:
    if not is_icloud_target_root(target_root):
        return None
    target_hash = hashlib.sha1(str(target_root.expanduser().resolve()).encode("utf-8")).hexdigest()[:16]
    return managed_state_root() / target_hash / sanitize_filename(container_name)


def replace_target(root_dir: Path, stage_root: Path) -> None:
    root_dir.parent.mkdir(parents=True, exist_ok=True)
    if root_dir.exists():
        shutil.rmtree(root_dir)
    shutil.copytree(stage_root, root_dir)


def read_json_file(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_helper_script() -> Path:
    return Path(__file__).resolve().with_name("fetch_bilibili_favorites.mjs")


def fetch_payload(input_json: Optional[Path], helper_script: Path) -> Dict[str, Any]:
    if input_json is not None:
        resolved = input_json.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"input JSON not found: {resolved}")
        return read_json_file(resolved)

    node_bin = shutil.which("node") or "node"
    with tempfile.NamedTemporaryFile(prefix="bilibili-favorites-", suffix=".json", delete=False) as handle:
        output_json = Path(handle.name)
    command = [
        node_bin,
        str(helper_script),
        "--output-json",
        str(output_json),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    stdout = completed.stdout.strip()
    candidate_path = Path(stdout.splitlines()[-1]).expanduser().resolve() if stdout else output_json
    if not candidate_path.exists():
        candidate_path = output_json
    return read_json_file(candidate_path)


def main() -> int:
    args = parse_args()
    set_active_language(args.title_language)

    target_root = Path(args.target_root).expanduser().resolve()
    output_root = target_root / args.container_name
    normalize_output_tree(output_root)
    taxonomy_path = resolve_taxonomy_path(output_root, args.classification, args.manual_rules)
    payload = fetch_payload(
        Path(args.input_json).expanduser().resolve() if args.input_json else None,
        Path(args.helper_script).expanduser().resolve() if args.helper_script else default_helper_script(),
    )

    incoming = normalize_payload(payload, taxonomy_path)
    existing: Dict[str, FavoriteRecord] = {}
    if args.mode == "merge":
        existing_date_root = resolve_existing_stable_root(output_root, LEGACY_DATE_DIRNAMES) or (output_root / DATE_DIRNAME)
        existing = parse_existing_records(existing_date_root)
        merged, new_ids, sync_removed_ids = sync_records_authoritative(existing, incoming)
    else:
        merged = incoming
        new_ids = set(merged)
        sync_removed_ids = set()
    merged, removed_ids = prune_unwanted_records(merged)
    new_ids -= removed_ids
    removed_ids |= sync_removed_ids

    local_build_root = local_build_root_for_target(target_root, args.container_name)
    if local_build_root is not None:
        stage_root = local_build_root
        if stage_root.exists():
            shutil.rmtree(stage_root)
        stage_root.mkdir(parents=True, exist_ok=True)
    else:
        temp_parent = Path(tempfile.mkdtemp(prefix="bilibili-favorites-sync-"))
        stage_root = temp_parent / args.container_name
        stage_root.mkdir(parents=True, exist_ok=True)

    try:
        result = render_structure(stage_root, merged, new_ids, taxonomy_path, payload.get("folders"), output_root)
        replace_target(output_root, stage_root)
        normalize_output_tree(output_root)
        total_md_count, note_count = validate_output(output_root, len(merged))
        delayed_validation = run_delayed_duplicate_audit(output_root, delay_seconds=90, expected_notes=len(merged))
        if delayed_validation is not None:
            total_md_count, note_count = delayed_validation
    finally:
        if local_build_root is None and stage_root.parent.exists():
            shutil.rmtree(stage_root.parent, ignore_errors=True)

    summary = {
        "output_root": str(output_root),
        "record_count": result["record_count"],
        "folder_count": result["folder_count"],
        "new_count": len(new_ids),
        "removed_count": len(removed_ids),
        "primary_note_count": note_count,
        "total_md_count": total_md_count,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
