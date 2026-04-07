from __future__ import annotations

import re
from typing import Any, Iterable


INVALID_TITLE_REASON = "invalid_placeholder_title"
INVALID_ATTR_REASON = "invalid_attr_flag"
INVALID_STATUS_REASON = "invalid_status_flag"

_INVALID_TITLE_MARKERS = {
    "已失效视频",
    "视频已失效",
    "该视频已失效",
    "稿件已失效",
    "该稿件已失效",
}
_INVALID_ATTR_MARKERS = {
    "1",
    "invalid",
    "expired",
    "unavailable",
    "deleted",
    "已失效",
    "视频已失效",
    "已失效视频",
    "稿件已失效",
    "已删除",
}
_INVALID_STATUS_KEYS = (
    "invalid",
    "is_invalid",
    "expired",
    "is_expired",
    "deleted",
    "is_deleted",
)
_INVALID_STATUS_MARKERS = {
    "invalid",
    "expired",
    "unavailable",
    "deleted",
    "已失效",
    "已删除",
}
_TITLE_WRAPPER_RE = re.compile(r"[\s\[\]【】()（）<>《》'\"“”‘’`]+")


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalized_title(value: Any) -> str:
    return _TITLE_WRAPPER_RE.sub("", _clean_text(value))


def _iter_candidate_dicts(media: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield media
    for key in ("media", "raw_media"):
        nested = media.get(key)
        if isinstance(nested, dict):
            yield nested


def _reason_from_title(candidate: dict[str, Any]) -> str | None:
    if _normalized_title(candidate.get("title")) in _INVALID_TITLE_MARKERS:
        return INVALID_TITLE_REASON
    return None


def _reason_from_attr(candidate: dict[str, Any]) -> str | None:
    attr = candidate.get("attr")
    if isinstance(attr, bool):
        return INVALID_ATTR_REASON if attr else None
    if isinstance(attr, int):
        return INVALID_ATTR_REASON if attr == 1 else None
    if _clean_text(attr).casefold() in _INVALID_ATTR_MARKERS:
        return INVALID_ATTR_REASON
    return None


def _reason_from_status(candidate: dict[str, Any]) -> str | None:
    for key in _INVALID_STATUS_KEYS:
        value = candidate.get(key)
        if isinstance(value, bool) and value:
            return INVALID_STATUS_REASON
        if _clean_text(value).casefold() in _INVALID_STATUS_MARKERS:
            return INVALID_STATUS_REASON
    return None


def invalid_bilibili_media_reason(media: dict[str, Any]) -> str | None:
    for candidate in _iter_candidate_dicts(media):
        for detector in (_reason_from_title, _reason_from_attr, _reason_from_status):
            reason = detector(candidate)
            if reason:
                return reason
    return None


def is_invalid_bilibili_media(media: dict[str, Any]) -> bool:
    return invalid_bilibili_media_reason(media) is not None


def filter_valid_media(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid_items: list[dict[str, Any]] = []
    invalid_items: list[dict[str, Any]] = []
    for item in items:
        if is_invalid_bilibili_media(item):
            invalid_items.append(item)
        else:
            valid_items.append(item)
    return valid_items, invalid_items
