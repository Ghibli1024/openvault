#!/usr/bin/env python3
"""Detect which Obsidian archive workflow matches the current request."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SOURCE_KEYS = ("bookmarks", "xhs", "bilibili", "x-likes")


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().replace("_", " ").replace("-", " ").split())


def _score_bookmarks(text: str, path_text: str) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if "书签" in text or "bookmark" in text or "bookmarks" in text:
        score += 3
        reasons.append("text mentions bookmarks")
    if "bookmarks.html" in path_text or "bookmark.html" in path_text:
        score += 4
        reasons.append("filename matches bookmark export")
    if path_text.endswith(".html") and ("bookmark" in path_text or "书签" in path_text):
        score += 2
        reasons.append("html path includes bookmark keywords")
    return score, reasons


def _score_xhs(text: str, path_text: str) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if "小红书" in text or "xiaohongshu" in text or "xhs" in text:
        score += 4
        reasons.append("text mentions Xiaohongshu")
    if "小红书" in path_text or "xiaohongshu" in path_text or "xhs" in path_text:
        score += 4
        reasons.append("path mentions Xiaohongshu")
    if path_text.endswith(".html") and (
        path_text.endswith("/收藏.html")
        or path_text.endswith("/喜欢.html")
        or path_text.endswith("\\收藏.html")
        or path_text.endswith("\\喜欢.html")
    ):
        score += 3
        reasons.append("html filename matches Xiaohongshu export")
    return score, reasons


def _score_bilibili(text: str, path_text: str) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if "b站" in text or "b 站" in text or "bilibili" in text:
        score += 4
        reasons.append("text mentions Bilibili")
    if "b站" in path_text or "b 站" in path_text or "bilibili" in path_text:
        score += 4
        reasons.append("path mentions Bilibili")
    if "收藏夹" in text:
        score += 2
        reasons.append("text mentions favorite folders")
    if "up主" in text:
        score += 1
        reasons.append("text mentions UP 主")
    return score, reasons


def _score_x_likes(text: str, path_text: str) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if "x likes" in text or "twitter likes" in text or "x 喜欢" in text or "twitter 喜欢" in text:
        score += 4
        reasons.append("text mentions X likes")
    if "x likes" in path_text or "twitter likes" in path_text:
        score += 4
        reasons.append("path mentions X likes")
    if path_text.endswith(".json") and (
        "x likes" in path_text
        or "xlikes" in path_text
        or "twitter likes" in path_text
        or "tweet" in path_text
    ):
        score += 3
        reasons.append("json filename looks like X export")
    if path_text.endswith(".json") and "likes" in path_text and "x " in path_text:
        score += 2
        reasons.append("json filename includes x + likes")
    return score, reasons


def detect_source(text: str = "", path: str = "") -> dict[str, object]:
    normalized_text = _normalize(text)
    normalized_path = _normalize(path)
    path_text = normalized_path
    scores: dict[str, int] = {}
    reasons: dict[str, list[str]] = {}

    for source, scorer in (
        ("bookmarks", _score_bookmarks),
        ("xhs", _score_xhs),
        ("bilibili", _score_bilibili),
        ("x-likes", _score_x_likes),
    ):
        source_score, source_reasons = scorer(normalized_text, path_text)
        scores[source] = source_score
        reasons[source] = source_reasons

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_source, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0

    if top_score == 0 or top_score == second_score:
        return {
            "source": "ambiguous",
            "ambiguous": True,
            "reason": "no unique source signal",
            "scores": scores,
            "reasons": reasons,
        }

    return {
        "source": top_source,
        "ambiguous": False,
        "reason": "; ".join(reasons[top_source]) or "highest score",
        "scores": scores,
        "reasons": reasons,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect which Obsidian archive workflow to route to.")
    parser.add_argument("--text", default="", help="User request text")
    parser.add_argument("--path", default="", help="Candidate file path or filename")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = detect_source(args.text, args.path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
