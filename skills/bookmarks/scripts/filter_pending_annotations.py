#!/usr/bin/env python3
"""
Filter a pending-annotations JSON file down to a specific category branch.

This is intended for gradual annotation workflows on large bookmark archives.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter pending bookmark annotations by category prefix.")
    parser.add_argument("--pending-json", required=True, help="Path to pending_annotations.json")
    parser.add_argument(
        "--category-prefix",
        required=True,
        help="Slash-separated category prefix, e.g. Research/AI Tools",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional maximum number of items to export")
    parser.add_argument("--output", required=True, help="Where to write the filtered JSON list")
    return parser.parse_args()


def parse_prefix(raw: str) -> List[str]:
    return [part.strip() for part in raw.split("/") if part.strip()]


def matches_prefix(item: dict, prefix: List[str]) -> bool:
    for path in item.get("category_paths", []):
        if path[: len(prefix)] == prefix:
            return True
    return False


def main() -> None:
    args = parse_args()
    pending_path = Path(args.pending_json).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    prefix = parse_prefix(args.category_prefix)

    items = json.loads(pending_path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError("pending JSON must be a list")

    filtered = [item for item in items if isinstance(item, dict) and matches_prefix(item, prefix)]
    filtered.sort(key=lambda item: (str(item.get("title", "")).lower(), str(item.get("url", "")).lower()))
    if args.limit > 0:
        filtered = filtered[: args.limit]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(filtered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "pending_json": str(pending_path),
                "category_prefix": prefix,
                "output": str(output_path),
                "count": len(filtered),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
