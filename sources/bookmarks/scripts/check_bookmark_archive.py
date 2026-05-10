#!/usr/bin/env python3
"""
Check the structural health of a generated bookmark archive.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sync_bookmark_html as sync


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check bookmark archive structure.")
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
        "--archive-profile",
        choices=["full", "categories-only"],
        default="full",
        help="Archive profile to validate",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_root = Path(args.target_root).expanduser().resolve() / args.container_name
    if args.state_root:
        state_root = Path(args.state_root).expanduser().resolve()
    else:
        state_root = sync.default_external_state_root(target_root)
    report = sync.archive_structure_report(target_root, state_root, archive_profile=args.archive_profile)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
