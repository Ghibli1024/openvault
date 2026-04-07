#!/usr/bin/env python3
"""
Reclassify an existing categories-only bookmark archive from its saved state.
"""

from __future__ import annotations

import argparse
import copy
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import sync_bookmark_html as sync


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reclassify an existing categories-only bookmark archive from state.json.")
    parser.add_argument("--archive-root", required=True, help="Existing archive root to rewrite in place")
    parser.add_argument("--taxonomy-reference-md", required=True, help="Target taxonomy markdown file")
    parser.add_argument(
        "--backup-root",
        help="Optional backup destination; defaults to a sibling archive backup directory with a timestamp suffix",
    )
    parser.add_argument(
        "--display-category-source",
        choices=["reference", "dual", "original"],
        default="reference",
        help="Which category path source should be rendered in the archive",
    )
    return parser.parse_args()


def timestamp_suffix() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def validate_archive_root(archive_root: Path) -> Tuple[Path, Path, Path]:
    taxonomy_path = archive_root / sync.ROOT_TAXONOMY_FILENAME
    state_path = archive_root / "_state" / sync.STATE_FILE
    index_path = archive_root / sync.INDEX_FILE
    missing = [str(path) for path in (taxonomy_path, state_path, index_path) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"archive root is missing required files: {', '.join(missing)}")
    return taxonomy_path, state_path, index_path


def default_backup_root(archive_root: Path) -> Path:
    return archive_root.parent / f"{archive_root.name}.backup-{timestamp_suffix()}"


def backup_archive(archive_root: Path, backup_root: Path) -> Path:
    if backup_root.exists():
        raise FileExistsError(f"backup destination already exists: {backup_root}")
    shutil.copytree(archive_root, backup_root)
    return backup_root


def load_state_payload(state_path: Path) -> Dict[str, object]:
    payload = sync.load_json(state_path)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid state payload: {state_path}")
    records = payload.get("records", {})
    if not isinstance(records, dict):
        raise ValueError(f"invalid records block in state payload: {state_path}")
    return payload


def normalize_url_list(urls: Sequence[str]) -> List[str]:
    return sync.dedupe_strings(sync.normalize_url(url) for url in urls if sync.clean_text(url))


def build_new_manual_records(
    state: Dict[str, object],
    manual_urls: Sequence[str],
    reference: sync.TaxonomyReference,
    display_source: str,
) -> Tuple[Dict[str, Dict[str, object]], Dict[str, Dict[str, object]]]:
    records = state.get("records", {})
    existing_records = records if isinstance(records, dict) else {}
    existing_urls = {sync.normalize_url(url) for url in existing_records}
    new_manual_urls = [url for url in manual_urls if sync.normalize_url(url) not in existing_urls]
    if not new_manual_urls:
        return {}, {}

    manual_entries = sync.build_manual_entries(new_manual_urls, sync.active_records(state))
    clean_entries, excluded_entries = sync.split_noise_entries(manual_entries)
    manual_records = sync.aggregate_entries(clean_entries)
    if reference is not None:
        manual_records, _ = sync.apply_reference_taxonomy(
            manual_records,
            reference,
            "full",
            "nearest",
            display_source,
        )
    excluded_records = sync.aggregate_excluded_entries(excluded_entries)
    return manual_records, excluded_records


def merge_manual_records(
    state: Dict[str, object],
    manual_records: Dict[str, Dict[str, object]],
) -> List[str]:
    raw_records = state.setdefault("records", {})
    if not isinstance(raw_records, dict):
        raise ValueError("state.records must be a dict")

    added_urls: List[str] = []
    timestamp = sync.now_iso()
    source_html = str(state.get("source_html", ""))
    for url, record in manual_records.items():
        normalized = sync.normalize_url(url)
        if normalized in raw_records:
            continue
        next_record = dict(record)
        next_record.setdefault("titles", [str(next_record.get("title", ""))])
        next_record.setdefault("bookmark_count", 1)
        next_record.setdefault("bookmark_add_dates", [])
        next_record.setdefault("bookmark_last_modified_dates", [])
        next_record["description"] = sync.clean_text(str(next_record.get("description", "")))
        next_record["note"] = sync.clean_text(str(next_record.get("note", "")))
        next_record["tags"] = sync.dedupe_strings(str(tag) for tag in next_record.get("tags", []) if sync.clean_text(str(tag)))
        next_record["status"] = "active"
        next_record["first_seen_at"] = timestamp
        next_record["last_seen_at"] = timestamp
        next_record["removed_at"] = ""
        next_record["source_html"] = source_html
        next_record["source_signature"] = sync.source_fingerprint(next_record)
        raw_records[normalized] = next_record
        added_urls.append(normalized)
    return sorted(added_urls)


def category_paths_for_active_record(record: Dict[str, object]) -> List[List[str]]:
    raw_paths = record.get("category_paths", [[]])
    if not isinstance(raw_paths, list) or not raw_paths:
        raw_paths = [[]]
    return sync.dedupe_paths(raw_paths)


def compute_changes(
    before_state: Dict[str, object],
    after_state: Dict[str, object],
    manual_new_urls: Sequence[str],
) -> Dict[str, List[str]]:
    before_active = sync.active_records(before_state)
    after_active = sync.active_records(after_state)
    manual_new_set = set(normalize_url_list(manual_new_urls))

    changes: Dict[str, List[str]] = {
        "new": [],
        "changed": [],
        "removed": [],
        "unchanged": [],
        "reactivated": [],
    }

    for url in sorted(after_active):
        if url in manual_new_set:
            changes["new"].append(url)
            continue
        before_record = before_active.get(url)
        if before_record is None:
            changes["new"].append(url)
            continue
        before_paths = category_paths_for_active_record(before_record)
        after_paths = category_paths_for_active_record(after_active[url])
        if before_paths != after_paths:
            changes["changed"].append(url)
        else:
            changes["unchanged"].append(url)

    return changes


def enrich_state_and_summary(
    state: Dict[str, object],
    summary: Dict[str, object],
    source_state_path: Path,
    taxonomy_reference_md: Path,
    manual_urls_processed: Sequence[str],
) -> None:
    state["last_sync_at"] = sync.now_iso()
    state["source_mode"] = "state-reclassify"
    state["source_state_path"] = str(source_state_path)
    state["last_taxonomy_reference_md"] = str(taxonomy_reference_md)
    state["manual_urls_processed"] = len(manual_urls_processed)

    summary["source_mode"] = "state-reclassify"
    summary["source_state_path"] = str(source_state_path)
    summary["last_taxonomy_reference_md"] = str(taxonomy_reference_md)
    summary["manual_urls_processed"] = len(manual_urls_processed)
    summary["manual_url_sample"] = list(manual_urls_processed)[:20]


def copy_taxonomy_into_archive(archive_root: Path, taxonomy_reference_md: Path) -> Path:
    destination = archive_root / sync.ROOT_TAXONOMY_FILENAME
    shutil.copy2(taxonomy_reference_md, destination)
    return destination


def cleanup_duplicate_root_taxonomy_copies(archive_root: Path) -> None:
    canonical = archive_root / sync.ROOT_TAXONOMY_FILENAME
    for path in archive_root.glob("ROOT分类目录 *.md"):
        if path.resolve() == canonical.resolve():
            continue
        if path.is_file():
            path.unlink()


def reclassify_existing_archive(
    archive_root: Path,
    taxonomy_reference_md: Path,
    backup_root: Optional[Path] = None,
    display_category_source: str = "reference",
) -> Dict[str, object]:
    archive_root = archive_root.expanduser().resolve()
    taxonomy_reference_md = taxonomy_reference_md.expanduser().resolve()
    if not archive_root.exists():
        raise FileNotFoundError(f"archive root not found: {archive_root}")
    if not taxonomy_reference_md.exists():
        raise FileNotFoundError(f"taxonomy reference not found: {taxonomy_reference_md}")

    current_taxonomy_path, state_path, index_path = validate_archive_root(archive_root)
    previous_payload = load_state_payload(state_path)
    previous_state = copy.deepcopy(previous_payload)
    previous_reference = sync.parse_taxonomy_reference_markdown(current_taxonomy_path)
    previous_top_level_categories = sync.top_level_categories_from_records(
        sync.active_records(previous_state),
        previous_reference.root_label,
    )
    manual_urls = sync.parse_manual_urls(index_path)

    resolved_backup_root = backup_root.expanduser().resolve() if backup_root else default_backup_root(archive_root)
    backup_archive(archive_root, resolved_backup_root)

    reference = sync.parse_taxonomy_reference_markdown(taxonomy_reference_md)
    next_state, _ = sync.reclassify_state_records(copy.deepcopy(previous_payload), reference, display_category_source)
    manual_records, excluded_records = build_new_manual_records(next_state, manual_urls, reference, display_category_source)
    manual_new_urls = merge_manual_records(next_state, manual_records)
    changes = compute_changes(previous_state, next_state, manual_new_urls)

    active_records = sync.active_records(next_state)
    raw_entries = [None] * len(active_records)
    current_records = dict(active_records)

    summary = sync.render_archive(
        target_root=archive_root,
        state_root=archive_root / "_state",
        raw_entries=raw_entries,
        current_records=current_records,
        excluded_records=excluded_records,
        state=next_state,
        changes=changes,
        pending_annotations=[],
        source_html=state_path,
        layout="compact",
        archive_profile="categories-only",
        taxonomy_reference=reference,
        previous_top_level_categories=previous_top_level_categories,
        manual_urls_processed=manual_urls,
    )

    copy_taxonomy_into_archive(archive_root, taxonomy_reference_md)
    cleanup_duplicate_root_taxonomy_copies(archive_root)
    enrich_state_and_summary(next_state, summary, state_path, taxonomy_reference_md, manual_urls)
    sync.save_json(archive_root / "_state" / sync.STATE_FILE, next_state)
    sync.save_json(archive_root / "_state" / sync.LATEST_SUMMARY_FILE, summary)
    (archive_root / "_state" / sync.INDEX_FILE).write_text(sync.render_state_index(summary), encoding="utf-8")

    return {
        "archive_root": str(archive_root),
        "backup_root": str(resolved_backup_root),
        "taxonomy_path": str(archive_root / sync.ROOT_TAXONOMY_FILENAME),
        "state_path": str(archive_root / "_state" / sync.STATE_FILE),
        "summary_path": str(archive_root / "_state" / sync.LATEST_SUMMARY_FILE),
        "new_urls": len(changes["new"]),
        "changed_urls": len(changes["changed"]),
        "removed_urls": len(changes["removed"]),
        "manual_urls_processed": len(manual_urls),
        "top_level_categories": summary.get("top_level_categories", []),
    }


def main() -> None:
    args = parse_args()
    result = reclassify_existing_archive(
        archive_root=Path(args.archive_root),
        taxonomy_reference_md=Path(args.taxonomy_reference_md),
        backup_root=Path(args.backup_root) if args.backup_root else None,
        display_category_source=args.display_category_source,
    )
    print(sync.json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
