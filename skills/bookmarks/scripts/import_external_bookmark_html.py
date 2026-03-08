#!/usr/bin/env python3
"""
Import an external bookmark HTML file into an existing Markdown bookmark archive.

Rules:
- Existing URLs are the canonical source of truth and must not be modified.
- Only new URLs from the external HTML are imported.
- New URLs are classified into the existing archive taxonomy by learning
  category-path mappings from duplicate URLs already present in the archive.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Sequence, Tuple

import autofill_annotations as autofill
import sync_bookmark_html as sync


PathKey = Tuple[str, ...]
Record = Dict[str, object]

# Optional override hooks for installations that want a small number of
# deterministic mappings before falling back to the generic import bucket.
MANUAL_URL_PREFIX_OVERRIDES: List[Tuple[str, List[str]]] = []
MANUAL_HOST_FAMILY_OVERRIDES: Dict[str, List[str]] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import external bookmark HTML into an existing archive.")
    parser.add_argument("--input-html", required=True, help="Path to external bookmark HTML export")
    parser.add_argument(
        "--target-root",
        required=True,
        help="Root path where the archive folder should live; accepts absolute or relative paths",
    )
    parser.add_argument("--container-name", default="Bookmarks", help="Folder name created under target root")
    parser.add_argument(
        "--state-root",
        help="Optional state directory; defaults like sync_bookmark_html.py",
    )
    parser.add_argument(
        "--title-language",
        choices=["zh", "en"],
        default="zh",
        help="Language for generated headings and placeholder text",
    )
    parser.add_argument(
        "--fallback-category",
        default="Imported/Needs Review",
        help="Slash-separated existing category path for URLs that cannot be mapped",
    )
    parser.add_argument("--summary-path", help="Optional path for copying the machine-readable summary JSON")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without writing to the archive")
    return parser.parse_args()


def category_paths_for_record(record: Record) -> List[List[str]]:
    raw_paths = record.get("category_paths", [[]])
    paths: List[List[str]] = []
    if isinstance(raw_paths, list):
        for raw_path in raw_paths:
            if not isinstance(raw_path, list):
                continue
            parts = [sync.clean_text(str(part)) for part in raw_path if sync.clean_text(str(part))]
            if parts:
                paths.append(parts)
    return sync.dedupe_paths(paths) if paths else [[]]


def record_host(record: Record) -> str:
    return sync.clean_text(str(record.get("host", ""))).lower()


def host_family(host: str) -> str:
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    second_level_suffixes = {"com", "net", "org", "gov", "edu", "ac"}
    if len(parts[-1]) == 2 and parts[-2] in second_level_suffixes and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def rank_path_counts(counter: Counter[PathKey]) -> List[Tuple[PathKey, int]]:
    return sorted(
        counter.items(),
        key=lambda item: (-item[1], len(item[0]), [part.lower() for part in item[0]]),
    )


def best_path(counter: Counter[PathKey]) -> PathKey | None:
    ranked = rank_path_counts(counter)
    return ranked[0][0] if ranked else None


def manual_override_for_record(record: Record) -> List[str] | None:
    url = sync.clean_text(str(record.get("url", "")))
    for prefix, path in MANUAL_URL_PREFIX_OVERRIDES:
        if url.startswith(prefix):
            return list(path)
    host = record_host(record)
    family = host_family(host) if host else ""
    if family in MANUAL_HOST_FAMILY_OVERRIDES:
        return list(MANUAL_HOST_FAMILY_OVERRIDES[family])
    return None


def build_mapping_models(
    external_records: Dict[str, Record],
    existing_active: Dict[str, Record],
) -> Tuple[
    DefaultDict[PathKey, Counter[PathKey]],
    DefaultDict[PathKey, Counter[PathKey]],
    DefaultDict[str, Counter[PathKey]],
    DefaultDict[str, Counter[PathKey]],
    DefaultDict[str, Counter[PathKey]],
]:
    exact_counts: DefaultDict[PathKey, Counter[PathKey]] = defaultdict(Counter)
    prefix_counts: DefaultDict[PathKey, Counter[PathKey]] = defaultdict(Counter)
    host_counts: DefaultDict[str, Counter[PathKey]] = defaultdict(Counter)
    host_family_counts: DefaultDict[str, Counter[PathKey]] = defaultdict(Counter)
    leaf_counts: DefaultDict[str, Counter[PathKey]] = defaultdict(Counter)

    for url, external_record in external_records.items():
        existing_record = existing_active.get(url)
        if not existing_record:
            continue
        existing_paths = [tuple(path) for path in category_paths_for_record(existing_record) if path]
        if not existing_paths:
            continue
        host = record_host(external_record) or record_host(existing_record)
        for external_path in category_paths_for_record(external_record):
            if not external_path:
                continue
            ext_key = tuple(external_path)
            for existing_key in existing_paths:
                exact_counts[ext_key][existing_key] += 1
                for depth in range(1, len(ext_key) + 1):
                    prefix_counts[ext_key[:depth]][existing_key] += 1
                if host:
                    host_counts[host][existing_key] += 1
                    host_family_counts[host_family(host)][existing_key] += 1
                leaf_counts[external_path[-1].strip().lower()][existing_key] += 1
    return exact_counts, prefix_counts, host_counts, host_family_counts, leaf_counts


def choose_mapped_path(
    external_path: Sequence[str],
    host: str,
    exact_counts: DefaultDict[PathKey, Counter[PathKey]],
    prefix_counts: DefaultDict[PathKey, Counter[PathKey]],
    host_counts: DefaultDict[str, Counter[PathKey]],
    host_family_counts: DefaultDict[str, Counter[PathKey]],
    leaf_counts: DefaultDict[str, Counter[PathKey]],
) -> Tuple[List[str] | None, str]:
    ext_key = tuple(external_path)
    exact = best_path(exact_counts.get(ext_key, Counter()))
    if exact:
        return list(exact), "exact"
    for depth in range(len(ext_key) - 1, 0, -1):
        prefix = best_path(prefix_counts.get(ext_key[:depth], Counter()))
        if prefix:
            return list(prefix), "prefix"
    if host:
        host_match = best_path(host_counts.get(host, Counter()))
        if host_match:
            return list(host_match), "host"
        family_match = best_path(host_family_counts.get(host_family(host), Counter()))
        if family_match:
            return list(family_match), "domain"
    if external_path:
        leaf = external_path[-1].strip().lower()
        leaf_match = best_path(leaf_counts.get(leaf, Counter()))
        if leaf_match:
            return list(leaf_match), "leaf"
    return None, "fallback"


def import_record(
    source_record: Record,
    mapped_paths: List[List[str]],
    source_html: Path,
    timestamp: str,
) -> Record:
    record = dict(source_record)
    record["category_paths"] = sync.dedupe_paths(mapped_paths)
    annotation_item = {
        "url": record.get("url", ""),
        "title": record.get("title", ""),
        "host": record.get("host", ""),
        "category_paths": record["category_paths"],
    }
    record["description"] = autofill.infer_description(annotation_item)
    record["note"] = ""
    record["tags"] = autofill.infer_tags(annotation_item)
    record["status"] = "active"
    record["first_seen_at"] = timestamp
    record["last_seen_at"] = timestamp
    record["removed_at"] = ""
    record["source_html"] = str(source_html)
    record["source_signature"] = sync.source_fingerprint(record)
    return record


def summarize_mapping(counter: Counter[str]) -> Dict[str, int]:
    return {key: int(counter[key]) for key in sorted(counter)}


def main() -> None:
    args = parse_args()
    sync.set_active_language(args.title_language)

    source_html = Path(args.input_html).expanduser().resolve()
    target_root = Path(args.target_root).expanduser().resolve() / args.container_name
    if args.state_root:
        state_root = Path(args.state_root).expanduser().resolve()
    else:
        state_root = sync.default_external_state_root(target_root)
    fallback_category = [part for part in args.fallback_category.split("/") if sync.clean_text(part)]
    if not fallback_category:
        raise ValueError("fallback category must contain at least one non-empty segment")
    if not source_html.exists():
        raise FileNotFoundError(f"input HTML not found: {source_html}")

    state_path = state_root / sync.STATE_FILE
    if not state_path.exists():
        raise FileNotFoundError(f"existing archive state not found: {state_path}")

    existing_state = sync.load_state(state_path)
    existing_active = sync.active_records(existing_state)

    entries = sync.parse_bookmark_html(source_html)
    clean_entries, excluded_entries = sync.split_noise_entries(entries)
    external_records = sync.aggregate_entries(clean_entries)
    excluded_records = sync.aggregate_excluded_entries(excluded_entries)

    exact_counts, prefix_counts, host_counts, host_family_counts, leaf_counts = build_mapping_models(
        external_records,
        existing_active,
    )

    timestamp = sync.now_iso()
    merged_records = dict(existing_state.get("records", {})) if isinstance(existing_state.get("records", {}), dict) else {}
    new_urls: List[str] = []
    duplicate_urls: List[str] = []
    strategy_counts: Counter[str] = Counter()
    unmapped_urls: List[str] = []

    for url, record in external_records.items():
        if url in existing_active:
            duplicate_urls.append(url)
            continue

        host = record_host(record)
        mapped_paths: List[List[str]] = []
        record_strategies: List[str] = []
        for external_path in category_paths_for_record(record):
            if not external_path:
                continue
            mapped_path, strategy = choose_mapped_path(
                external_path,
                host,
                exact_counts,
                prefix_counts,
                host_counts,
                host_family_counts,
                leaf_counts,
            )
            if mapped_path:
                mapped_paths.append(mapped_path)
            record_strategies.append(strategy)

        if not mapped_paths:
            manual_path = manual_override_for_record(record)
            if manual_path:
                mapped_paths = [manual_path]
                strategy_counts["manual"] += 1
            else:
                mapped_paths = [fallback_category]
                unmapped_urls.append(url)
                strategy_counts["fallback"] += 1
        else:
            for strategy in record_strategies:
                if strategy != "fallback":
                    strategy_counts[strategy] += 1
            if all(strategy == "fallback" for strategy in record_strategies):
                strategy_counts["fallback"] += 1

        merged_records[url] = import_record(record, mapped_paths, source_html, timestamp)
        new_urls.append(url)

    new_urls.sort()
    duplicate_urls.sort()
    unmapped_urls.sort()

    next_state = {
        "version": int(existing_state.get("version", sync.STATE_VERSION)),
        "last_sync_at": timestamp,
        "source_html": str(source_html),
        "records": merged_records,
    }
    changes = {
        "new": new_urls,
        "changed": [],
        "removed": [],
        "unchanged": duplicate_urls,
        "reactivated": [],
    }
    pending_annotations = sync.build_pending_annotations(next_state["records"])

    import_summary = {
        "container_root": str(target_root),
        "source_html": str(source_html),
        "input_bookmark_entries": len(entries),
        "input_unique_urls": len(external_records),
        "existing_active_urls_before_import": len(existing_active),
        "duplicate_urls_skipped": len(duplicate_urls),
        "new_urls_imported": len(new_urls),
        "excluded_noise_urls": len(excluded_records),
        "unmapped_new_urls": len(unmapped_urls),
        "mapping_strategies": summarize_mapping(strategy_counts),
        "duplicate_sample": duplicate_urls[:20],
        "new_url_sample": new_urls[:20],
        "unmapped_sample": unmapped_urls[:20],
        "state_root": str(state_root),
        "fallback_category": fallback_category,
    }

    if args.dry_run:
        if args.summary_path:
            sync.save_json(Path(args.summary_path).expanduser().resolve(), import_summary)
        print(json.dumps(import_summary, ensure_ascii=False, indent=2))
        return

    summary = sync.render_archive(
        target_root=target_root,
        state_root=state_root,
        raw_entries=entries,
        current_records=external_records,
        excluded_records=excluded_records,
        state=next_state,
        changes=changes,
        pending_annotations=pending_annotations,
        source_html=source_html,
        layout="compact",
    )
    summary["import"] = import_summary
    sync.save_json(state_root / sync.STATE_FILE, next_state)
    sync.save_json(state_root / sync.PENDING_ANNOTATIONS_FILE, pending_annotations)
    sync.save_json(state_root / sync.EXCLUDED_LINKS_JSON, excluded_records)
    sync.save_json(state_root / sync.LATEST_SUMMARY_FILE, summary)
    if args.summary_path:
        sync.save_json(Path(args.summary_path).expanduser().resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
