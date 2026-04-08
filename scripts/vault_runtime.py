#!/usr/bin/env python3
from __future__ import annotations

import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, Optional, Set
from urllib.parse import urlparse


RESOURCE_ROOT_CANDIDATES = ("04-Resources", "04Resources")
GLOBAL_SEARCH_DIRNAME = "搜索"
GLOBAL_RUBBISH_DIRNAME = "废弃"

SOURCE_ROOTS = {
    "书签": {
        "legacy_names": ("书签库",),
        "search_dirs": ("搜索",),
        "rubbish_dirs": ("废弃",),
        "note_roots": (),
    },
    "小红书": {
        "legacy_names": (),
        "search_dirs": ("06 搜索", "06 Search", "05 Search", "04 Search"),
        "rubbish_dirs": ("07 废弃", "07 Rubbish", "06 Rubbish", "05 Rubbish"),
        "note_roots": ("01 日期",),
    },
    "B站": {
        "legacy_names": (),
        "search_dirs": ("06 搜索", "06 Search", "05 Search", "04 Search"),
        "rubbish_dirs": ("07 废弃", "07 Rubbish", "06 Rubbish", "05 Rubbish"),
        "note_roots": ("01 日期",),
    },
    "X": {
        "legacy_names": ("X Likes",),
        "search_dirs": ("04 Search", "搜索"),
        "rubbish_dirs": ("05 Rubbish", "废弃"),
        "note_roots": ("01 Date",),
    },
}

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
URL_RE = re.compile(r"https?://[^\s)>\"']+")
X_STATUS_RE = re.compile(r"https?://(?:twitter\.com|x\.com)/[^)\s\"']+/status/(\d+)")
XHS_NOTE_RE = re.compile(r"https?://(?:www\.)?xiaohongshu\.com/explore/([A-Za-z0-9_-]+)")
BILIBILI_BVID_RE = re.compile(r"https?://(?:www\.)?bilibili\.com/video/(BV[0-9A-Za-z]+)")


def empty_signal_map() -> Dict[str, Dict[str, Set[str]]]:
    return {
        source_name: {"ids": set(), "urls": set()}
        for source_name in ("书签", "小红书", "B站", "X")
    }


def parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    block = text[4:end]
    body = text[end + 5 :]
    values: Dict[str, str] = {}
    for raw_line in block.splitlines():
        if ":" not in raw_line:
            continue
        key, raw_value = raw_line.split(":", 1)
        values[key.strip()] = raw_value.strip().strip('"').strip("'")
    return values, body


def resolve_resources_root(vault_root: Path, explicit_root: Optional[Path] = None) -> Path:
    if explicit_root is not None:
        return explicit_root.expanduser().resolve()

    resolved_vault = vault_root.expanduser().resolve()
    for name in RESOURCE_ROOT_CANDIDATES:
        candidate = resolved_vault / name
        if candidate.exists():
            return candidate.resolve()
    return (resolved_vault / RESOURCE_ROOT_CANDIDATES[0]).resolve()


def global_search_root(resources_root: Path) -> Path:
    return resources_root / GLOBAL_SEARCH_DIRNAME


def global_rubbish_root(resources_root: Path) -> Path:
    return resources_root / GLOBAL_RUBBISH_DIRNAME


def ensure_global_roots(resources_root: Path) -> None:
    global_search_root(resources_root).mkdir(parents=True, exist_ok=True)
    global_rubbish_root(resources_root).mkdir(parents=True, exist_ok=True)


def canonical_source_name(name: str) -> str:
    clean_name = name.strip()
    for canonical_name, config in SOURCE_ROOTS.items():
        if clean_name == canonical_name or clean_name in config["legacy_names"]:
            return canonical_name
    return clean_name


def unique_flat_file_path(target_root: Path, preferred_name: str, source_name: str, stable_id: Optional[str] = None) -> Path:
    target_root.mkdir(parents=True, exist_ok=True)
    candidate = target_root / preferred_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    extra = f"__{source_name}"
    if stable_id:
        extra += f"__{stable_id}"
    return target_root / f"{stem}{extra}{suffix}"


def merge_dir_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(source.iterdir(), key=lambda path: path.name):
        destination = target / entry.name
        if entry.is_dir():
            merge_dir_tree(entry, destination)
            shutil.rmtree(entry)
            continue
        if destination.exists():
            destination = unique_flat_file_path(target, entry.name, source.parent.name, None)
        shutil.move(str(entry), str(destination))


def _lift_managed_folder(resources_root: Path, source_root: Path, folder_name: str, target_root: Path) -> None:
    folder = source_root / folder_name
    if not folder.exists():
        return
    merge_dir_tree(folder, target_root)
    shutil.rmtree(folder, ignore_errors=True)


def _rename_or_merge(source_root: Path, target_root: Path) -> None:
    if not source_root.exists():
        return
    if not target_root.exists():
        source_root.rename(target_root)
        return
    merge_dir_tree(source_root, target_root)
    shutil.rmtree(source_root, ignore_errors=True)


def migrate_resources_layout(resources_root: Path) -> None:
    resources_root = resources_root.expanduser().resolve()
    ensure_global_roots(resources_root)

    for canonical_name, config in SOURCE_ROOTS.items():
        canonical_root = resources_root / canonical_name
        for legacy_name in config["legacy_names"]:
            _rename_or_merge(resources_root / legacy_name, canonical_root)

    for canonical_name, config in SOURCE_ROOTS.items():
        source_root = resources_root / canonical_name
        if not source_root.exists():
            continue
        for folder_name in config["search_dirs"]:
            _lift_managed_folder(resources_root, source_root, folder_name, global_search_root(resources_root))
        for folder_name in config["rubbish_dirs"]:
            _lift_managed_folder(resources_root, source_root, folder_name, global_rubbish_root(resources_root))


def detect_source_from_url(url: str) -> str:
    if X_STATUS_RE.search(url):
        return "X"
    if XHS_NOTE_RE.search(url):
        return "小红书"
    if BILIBILI_BVID_RE.search(url):
        return "B站"
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return "书签"
    return ""


def detect_note_source(frontmatter: Dict[str, str], note_path: Path) -> str:
    platform_name = frontmatter.get("platform", "").strip().lower()
    if platform_name == "xiaohongshu":
        return "小红书"
    if frontmatter.get("tweet_id"):
        return "X"
    if frontmatter.get("bvid") or frontmatter.get("video_url"):
        return "B站"
    if frontmatter.get("url"):
        return "书签"
    if note_path.parts:
        for part in note_path.parts:
            canonical = canonical_source_name(part)
            if canonical in SOURCE_ROOTS:
                return canonical
    return ""


def _signal_id_from_url(url: str) -> tuple[str, str]:
    x_match = X_STATUS_RE.search(url)
    if x_match:
        return "X", x_match.group(1)
    xhs_match = XHS_NOTE_RE.search(url)
    if xhs_match:
        return "小红书", xhs_match.group(1)
    bili_match = BILIBILI_BVID_RE.search(url)
    if bili_match:
        return "B站", bili_match.group(1)
    return "", ""


def _collect_signal_from_note(resources_root: Path, note_path: Path, signals: Dict[str, Dict[str, Set[str]]]) -> None:
    text = note_path.read_text(encoding="utf-8", errors="ignore")
    frontmatter, body = parse_frontmatter(text)
    note_source = detect_note_source(frontmatter, note_path.relative_to(resources_root))

    if note_source == "X":
        for field in ("tweet_id",):
            value = frontmatter.get(field, "").strip()
            if value:
                signals["X"]["ids"].add(value)
    elif note_source == "小红书":
        for field in ("note_id",):
            value = frontmatter.get(field, "").strip()
            if value:
                signals["小红书"]["ids"].add(value)
    elif note_source == "B站":
        for field in ("bvid",):
            value = frontmatter.get(field, "").strip()
            if value:
                signals["B站"]["ids"].add(value)

    for url in URL_RE.findall(text):
        source_name, stable_id = _signal_id_from_url(url)
        if source_name and stable_id:
            signals[source_name]["ids"].add(stable_id)
            continue
        detected = detect_source_from_url(url)
        if detected == "书签":
            signals["书签"]["urls"].add(url)

    for target in WIKILINK_RE.findall(body):
        link_path = (resources_root / target).with_suffix(".md")
        if not link_path.exists():
            continue
        linked_text = link_path.read_text(encoding="utf-8", errors="ignore")
        linked_frontmatter, _ = parse_frontmatter(linked_text)
        linked_source = detect_note_source(linked_frontmatter, link_path.relative_to(resources_root))
        if linked_source == "X" and linked_frontmatter.get("tweet_id"):
            signals["X"]["ids"].add(linked_frontmatter["tweet_id"].strip())
        elif linked_source == "小红书" and linked_frontmatter.get("note_id"):
            signals["小红书"]["ids"].add(linked_frontmatter["note_id"].strip())
        elif linked_source == "B站" and linked_frontmatter.get("bvid"):
            signals["B站"]["ids"].add(linked_frontmatter["bvid"].strip())


def collect_global_rubbish_signals(resources_root: Path) -> Dict[str, Dict[str, Set[str]]]:
    resources_root = resources_root.expanduser().resolve()
    signals = empty_signal_map()
    rubbish_root = global_rubbish_root(resources_root)
    if not rubbish_root.exists():
        return signals

    for note_path in rubbish_root.rglob("*.md"):
        _collect_signal_from_note(resources_root, note_path, signals)
    return signals


def send_paths_to_trash(paths: Iterable[Path]) -> None:
    existing_paths = [path.expanduser().resolve() for path in paths if path.exists()]
    if not existing_paths:
        return

    if platform.system() == "Darwin":
        file_list = ", ".join(f'POSIX file "{str(path).replace("\"", "\\\"")}"' for path in existing_paths)
        script = f'tell application "Finder" to delete {{{file_list}}}'
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
        return

    raise RuntimeError("send_paths_to_trash is currently implemented only for macOS")


def trash_markdown_notes_by_frontmatter_field(root: Path, field: str, ids: Set[str]) -> list[Path]:
    if not ids or not root.exists():
        return []
    pattern = re.compile(rf'^{re.escape(field)}:\s*"?([^"\n]+)"?\s*$', re.MULTILINE)
    matched: list[Path] = []
    for note_path in root.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8", errors="ignore")
        hit = pattern.search(text)
        if not hit:
            continue
        if hit.group(1).strip() not in ids:
            continue
        matched.append(note_path)
    if matched:
        send_paths_to_trash(matched)
    return matched


def searchable_note_roots(resources_root: Path, source_name: str) -> tuple[Path, ...]:
    source_root = resources_root / source_name
    config = SOURCE_ROOTS.get(source_name, {})
    note_roots = tuple(config.get("note_roots", ()))
    if source_name == "书签":
        return (source_root,)
    return tuple(source_root / name for name in note_roots)


def iter_searchable_notes(resources_root: Path, source_name: str) -> Iterable[Path]:
    for note_root in searchable_note_roots(resources_root, source_name):
        if not note_root.exists():
            continue
        for note_path in note_root.rglob("*.md"):
            if note_path.name == "ROOT分类目录.md":
                continue
            if "_state" in note_path.parts:
                continue
            if source_name != "书签" and note_path.name == "Index.md":
                continue
            yield note_path


def note_candidate_sources(resources_root: Path, note_path: Path) -> Set[str]:
    text = note_path.read_text(encoding="utf-8", errors="ignore")
    frontmatter, body = parse_frontmatter(text)
    detected = detect_note_source(frontmatter, note_path.relative_to(resources_root))
    sources: Set[str] = {detected} if detected else set()
    for url in URL_RE.findall(text):
        url_source = detect_source_from_url(url)
        if url_source:
            sources.add(url_source)
    for target in WIKILINK_RE.findall(body):
        link_path = (resources_root / target).with_suffix(".md")
        if not link_path.exists():
            continue
        linked_text = link_path.read_text(encoding="utf-8", errors="ignore")
        linked_frontmatter, _ = parse_frontmatter(linked_text)
        linked_source = detect_note_source(linked_frontmatter, link_path.relative_to(resources_root))
        if linked_source:
            sources.add(linked_source)
    return sources
