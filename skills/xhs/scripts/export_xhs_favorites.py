#!/usr/bin/env python3
"""
Export Xiaohongshu favorites into a normalized JSON schema.

This script uses a small Node + Playwright helper at runtime so it can work
without Python Playwright installed. The browser automation is intentionally
best-effort: helpers are designed to be reusable even when the site changes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse
from zoneinfo import ZoneInfo


DEFAULT_OUTPUT_JSON = Path.cwd() / "xhs-favorites-export.json"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Xiaohongshu favorites to normalized JSON")
    parser.add_argument("--input-json", help="Existing normalized export JSON to resume or enrich from")
    parser.add_argument("--favorites-html", help="Favorites HTML exported from an external Xiaohongshu plugin")
    parser.add_argument("--liked-html", help="Liked posts HTML exported from an external Xiaohongshu plugin")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON), help="Where to write the normalized JSON")
    parser.add_argument("--user-data-dir", help="Persistent browser state directory used by Playwright")
    parser.add_argument("--profile-dir", default="Default", help="Chrome profile directory name")
    parser.add_argument("--use-current-chrome", action="store_true", help="Read from the currently active Xiaohongshu favorites tab in Google Chrome")
    parser.add_argument("--favorites-url", help="Optional Xiaohongshu favorites URL to open in Google Chrome before crawling")
    parser.add_argument("--headless", action="store_true", help="Run browser headless after login state is ready")
    parser.add_argument("--max-empty-rounds", type=int, default=4, help="How many no-growth scroll rounds end a collection crawl")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for current Chrome enrichment")
    parser.add_argument("--skip-enrich", action="store_true", help="Skip opencli note enrichment")
    return parser.parse_args()


def global_node_modules_root() -> str:
    completed = subprocess.run(
        ["npm", "root", "-g"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def extract_note_id(url: str) -> str:
    match = re.search(r"/(?:explore|note|search_result|discovery/item)/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else ""


def normalize_note_url(url: str) -> Dict[str, str]:
    parsed = urlparse(url)
    note_id = extract_note_id(url)
    kept_query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key == "xsec_token"]
    canonical_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.scheme and parsed.netloc else url
    note_url = canonical_url
    if kept_query:
        note_url = f"{canonical_url}?{urlencode(kept_query)}"
    return {
        "note_id": note_id,
        "canonical_url": canonical_url,
        "note_url": note_url,
    }


def normalize_xhs_edited_date(value: object) -> str:
    if value in (None, ""):
        return ""

    if isinstance(value, (int, float)):
        raw = int(value)
    else:
        text = str(value).strip()
        if not text:
            return ""
        if not re.search(r"编辑于|最后编辑于|最近编辑于|last update|last edited|updated at|edited at", text, re.I):
            if re.fullmatch(r"\d{10,13}", text):
                raw = int(text)
            else:
                return ""
        else:
            match = re.search(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})", text)
            if not match:
                return ""
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"

    if raw <= 0:
        return ""
    if raw >= 10**12:
        raw //= 1000
    try:
        dt = datetime.fromtimestamp(raw, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return ""
    return dt.strftime("%Y-%m-%d")


def note_time_from_note_id(note_id: object) -> str:
    raw = str(note_id or "").strip()
    if len(raw) < 8 or not re.fullmatch(r"[0-9a-fA-F_-]+", raw):
        return ""
    try:
        ts = int(raw[:8], 16)
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d")
    except (ValueError, OverflowError, OSError):
        return ""


def parse_like_count(text: object) -> int:
    raw = str(text or "").strip()
    if not raw:
        return 0
    match = re.search(r"([\d.]+)\s*万", raw)
    if match:
        return int(float(match.group(1)) * 10000)
    match = re.search(r"\d+", raw.replace(",", ""))
    return int(match.group(0)) if match else 0


class XhsTableExportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_thead = False
        self.in_tbody = False
        self.current_row: Optional[List[dict]] = None
        self.current_cell: Optional[dict] = None
        self.header_rows: List[List[dict]] = []
        self.body_rows: List[List[dict]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attr_map = dict(attrs)
        if tag == "thead":
            self.in_thead = True
            return
        if tag == "tbody":
            self.in_tbody = True
            return
        if tag == "tr" and (self.in_thead or self.in_tbody):
            self.current_row = []
            return
        if tag in {"th", "td"} and self.current_row is not None:
            self.current_cell = {"text_parts": [], "hrefs": [], "images": []}
            return
        if tag == "a" and self.current_cell is not None:
            href = attr_map.get("href")
            if href:
                self.current_cell["hrefs"].append(href)
            return
        if tag == "img" and self.current_cell is not None:
            src = attr_map.get("src")
            if src:
                self.current_cell["images"].append(src)

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None:
            self.current_cell["text_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self.current_cell is not None and self.current_row is not None:
            text = re.sub(r"\s+", " ", "".join(self.current_cell["text_parts"])).strip()
            self.current_row.append(
                {
                    "text": text,
                    "hrefs": list(self.current_cell["hrefs"]),
                    "images": list(self.current_cell["images"]),
                }
            )
            self.current_cell = None
            return
        if tag == "tr" and self.current_row is not None:
            if self.in_tbody:
                self.body_rows.append(self.current_row)
            elif self.in_thead:
                self.header_rows.append(self.current_row)
            self.current_row = None
            return
        if tag == "thead":
            self.in_thead = False
            return
        if tag == "tbody":
            self.in_tbody = False


def parse_xhs_html_export(path: Path, source_name: str, source_id: str) -> List[dict]:
    parser = XhsTableExportParser()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    rows: List[dict] = []
    for raw_row in parser.body_rows:
        if len(raw_row) < 6:
            continue
        cover_cell, title_cell, content_cell, author_cell, type_cell, likes_cell = raw_row[:6]
        note_url = str(title_cell["hrefs"][0]).strip() if title_cell["hrefs"] else ""
        normalized = normalize_note_url(note_url)
        if not normalized["note_id"]:
            continue
        profile_url = str(author_cell["hrefs"][0]).strip() if author_cell["hrefs"] else ""
        author_id = ""
        author_match = re.search(r"/user/profile/([^/?#]+)", profile_url)
        if author_match:
            author_id = author_match.group(1)
        cover_url = str(cover_cell["images"][0]).strip() if cover_cell["images"] else ""
        rows.append(
            {
                "note_id": normalized["note_id"],
                "note_url": normalized["note_url"] or normalized["canonical_url"],
                "canonical_url": normalized["canonical_url"],
                "title": title_cell["text"],
                "title_preview": title_cell["text"],
                "author_name": author_cell["text"],
                "author_id": author_id,
                "profile_url": profile_url,
                "content": content_cell["text"],
                "note_type": type_cell["text"] or "普通",
                "likes": parse_like_count(likes_cell["text"]),
                "collects": 0,
                "comments": 0,
                "cover_url": cover_url,
                "media_urls": [cover_url] if cover_url else [],
                "fetch_status": "partial",
                "note_time": note_time_from_note_id(normalized["note_id"]),
                "note_time_source": "note_id" if note_time_from_note_id(normalized["note_id"]) else "",
                "source_actions": [source_name],
                "source_refs": [{"id": source_id, "name": source_name, "order": 1}],
            }
        )
    return rows


def merge_note_sources(rows: List[dict]) -> List[dict]:
    merged: Dict[str, dict] = {}
    for row in rows:
        normalized = normalize_note_url(str(row.get("note_url", "")))
        note_id = str(row.get("note_id") or normalized["note_id"]).strip()
        if not note_id:
            continue
        existing = merged.get(note_id)
        source_actions = [str(value).strip() for value in row.get("source_actions", []) if str(value).strip()]
        source_refs = []
        for value in row.get("source_refs", []) or []:
            if not isinstance(value, dict):
                continue
            source_refs.append(
                {
                    "id": str(value.get("id", "")).strip(),
                    "name": str(value.get("name", "")).strip(),
                    "order": int(value.get("order", 0) or 0),
                }
            )
        if existing is None:
            merged[note_id] = {
                "note_id": note_id,
                "note_url": normalized["note_url"],
                "canonical_url": normalized["canonical_url"],
                "title": str(row.get("title", "")).strip(),
                "title_preview": str(row.get("title_preview", "")).strip(),
                "author_name": str(row.get("author_name", "")).strip(),
                "author_id": str(row.get("author_id", "")).strip(),
                "profile_url": str(row.get("profile_url", "")).strip(),
                "content": str(row.get("content", "")).strip(),
                "note_type": str(row.get("note_type", "")).strip(),
                "likes": int(row.get("likes", 0) or 0),
                "collects": int(row.get("collects", 0) or 0),
                "comments": int(row.get("comments", 0) or 0),
                "cover_url": str(row.get("cover_url", "")).strip(),
                "media_urls": [str(value).strip() for value in row.get("media_urls", []) if str(value).strip()],
                "fetch_status": str(row.get("fetch_status", "partial") or "partial"),
                "note_time": str(row.get("note_time", "")).strip() or note_time_from_note_id(note_id),
                "note_time_source": str(row.get("note_time_source", "")).strip() or ("note_id" if note_time_from_note_id(note_id) else ""),
                "source_actions": source_actions,
                "source_refs": source_refs,
            }
            continue

        if normalized["note_url"]:
            existing["note_url"] = normalized["note_url"]
        if normalized["canonical_url"]:
            existing["canonical_url"] = normalized["canonical_url"]
        for field in ("title", "title_preview", "author_name", "author_id", "profile_url", "content", "note_type", "cover_url", "note_time", "note_time_source"):
            if row.get(field) and not existing.get(field):
                existing[field] = str(row.get(field)).strip()
        existing["likes"] = max(int(existing.get("likes", 0) or 0), int(row.get("likes", 0) or 0))
        existing["collects"] = max(int(existing.get("collects", 0) or 0), int(row.get("collects", 0) or 0))
        existing["comments"] = max(int(existing.get("comments", 0) or 0), int(row.get("comments", 0) or 0))
        if not existing.get("media_urls") and row.get("media_urls"):
            existing["media_urls"] = [str(value).strip() for value in row.get("media_urls", []) if str(value).strip()]
        if existing.get("fetch_status") != "full":
            existing["fetch_status"] = str(row.get("fetch_status", existing.get("fetch_status", "partial")) or "partial")
        for action in source_actions:
            if action and action not in existing["source_actions"]:
                existing["source_actions"].append(action)
        known_refs = {(item["id"], item["name"]) for item in existing.get("source_refs", [])}
        for ref in source_refs:
            key = (ref["id"], ref["name"])
            if ref["name"] and key not in known_refs:
                existing["source_refs"].append(ref)
                known_refs.add(key)

    for note in merged.values():
        note["source_actions"] = sorted(set(note.get("source_actions", [])))
        source_rank = {"收藏": 0, "喜欢": 1}
        note["source_refs"] = sorted(
            note.get("source_refs", []),
            key=lambda item: (item["order"], source_rank.get(item["name"], 99), item["name"].lower()),
        )
    return sorted(merged.values(), key=lambda item: item["note_id"])


def merge_note_memberships(rows: List[dict]) -> List[dict]:
    return merge_note_sources(rows)


def enrich_note(note: dict) -> dict:
    note_url = str(note.get("note_url", "")).strip()
    if not note_url:
        enriched = dict(note)
        enriched["fetch_status"] = "partial"
        return enriched

    try:
        completed = subprocess.run(
            ["opencli", "xiaohongshu", "note", note_url, "-f", "json"],
            check=True,
            capture_output=True,
            text=True,
        )
        rows = json.loads(completed.stdout)
    except Exception:
        enriched = dict(note)
        enriched.setdefault("content", "")
        enriched.setdefault("likes", 0)
        enriched.setdefault("collects", 0)
        enriched.setdefault("comments", 0)
        enriched.setdefault("media_urls", [])
        enriched["fetch_status"] = "partial"
        return enriched

    detail = {str(row.get("field", "")).strip(): row.get("value", "") for row in rows if isinstance(row, dict)}
    enriched = dict(note)
    enriched["title"] = str(detail.get("title", note.get("title_preview", ""))).strip()
    enriched["content"] = str(detail.get("content", "")).strip()
    enriched["likes"] = int(detail.get("likes", 0) or 0)
    enriched["collects"] = int(detail.get("collects", 0) or 0)
    enriched["comments"] = int(detail.get("comments", 0) or 0)
    enriched.setdefault("media_urls", [note.get("cover_url")] if note.get("cover_url") else [])
    enriched["fetch_status"] = "full"
    return enriched


def build_payload(collections: List[dict], notes: List[dict], note_count_raw: int) -> dict:
    return {
        "sources": collections,
        "collections": collections,
        "notes": notes,
        "run_meta": {
            "crawled_at": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], check=True, capture_output=True, text=True).stdout.strip(),
            "collection_count": len(collections),
            "note_count_raw": note_count_raw,
            "note_count_unique": len(notes),
        },
    }


def run_osascript(script: str, timeout: int = 30) -> str:
    completed = subprocess.run(
        ["osascript"],
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(stderr or "osascript failed")
    return completed.stdout.strip()


def applescript_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def chrome_exec_js(js: str, timeout_seconds: int = 20) -> str:
    script = f'''
with timeout of {timeout_seconds} seconds
tell application "Google Chrome"
  return execute active tab of window 1 javascript "{applescript_escape(js)}"
end tell
end timeout
'''
    return run_osascript(script, timeout=timeout_seconds + 5)


def ensure_current_chrome_tab(favorites_url: Optional[str]) -> None:
    if favorites_url:
        script = f'''
tell application "Google Chrome"
  if (count of windows) = 0 then make new window
  tell window 1
    set newTab to make new tab at end of tabs with properties {{URL:"{applescript_escape(favorites_url)}"}}
    set active tab index to (count of tabs)
  end tell
  activate
end tell
'''
        run_osascript(script, timeout=10)
        time.sleep(3)
        return

    current_url = run_osascript('tell application "Google Chrome" to get URL of active tab of front window', timeout=10)
    if "xiaohongshu.com" not in current_url or "tab=fav" not in current_url or "subTab=note" not in current_url:
        raise RuntimeError("Active Google Chrome tab is not a Xiaohongshu favorites note page. Open that page first or pass --favorites-url.")


def crawl_from_current_chrome(max_empty_rounds: int, favorites_url: Optional[str]) -> dict:
    ensure_current_chrome_tab(favorites_url)

    extract_js = r"""
JSON.stringify((() => {
  const clean = (value) => (value || '').replace(/\s+/g, ' ').trim();
  const noteLinkPattern = /\/user\/profile\/([^/]+)\/([A-Za-z0-9_-]+)\?[^#]*xsec_token=/;
  const profilePattern = /\/user\/profile\/([^/?#]+)(?:\?|$)/;
  const results = [];
  const seen = new Set();
  const anchors = Array.from(document.querySelectorAll('a[href*="xsec_source=pc_collect"], a[href*="xsec_token="]'));

  const resolveCardRoot = (node) => {
    let current = node;
    for (let i = 0; i < 8 && current; i += 1) {
      if (!(current instanceof HTMLElement)) break;
      const text = clean(current.innerText || '');
      const imageCount = current.querySelectorAll('img').length;
      if (imageCount > 0 && text) return current;
      current = current.parentElement;
    }
    return node instanceof HTMLElement ? node : null;
  };

  for (const anchor of anchors) {
    if (!(anchor instanceof HTMLAnchorElement)) continue;
    const href = anchor.getAttribute('href') || '';
    const absolute = new URL(href, location.origin).toString();
    const match = absolute.match(noteLinkPattern);
    if (!match) continue;
    const noteId = match[2];
    if (seen.has(noteId)) continue;
    seen.add(noteId);

    const card = resolveCardRoot(anchor);
    const img = (card && card.querySelector('img')) || anchor.querySelector('img');
    const coverUrl = clean((img && (img.currentSrc || img.src || img.getAttribute('src'))) || '');
    const lineTexts = card && card.innerText
      ? card.innerText.split(/\n+/).map(clean).filter(Boolean)
      : [];
    const textNodes = card ? Array.from(card.querySelectorAll('span, div, p, a')) : [];
    const texts = Array.from(new Set(textNodes.map((node) => clean(node.textContent || '')).filter(Boolean)));

    const authorAnchor = (card ? Array.from(card.querySelectorAll('a[href*="/user/profile/"]')) : []).find((node) => {
      const link = node.getAttribute('href') || '';
      return !noteLinkPattern.test(new URL(link, location.origin).toString()) && profilePattern.test(link);
    });
    const authorName = clean((authorAnchor && authorAnchor.textContent) || '') ||
      lineTexts.find((text) => text.length >= 2 && text.length <= 24) ||
      texts.find((text) => text.length >= 2 && text.length <= 24) || '';
    const authorHref = authorAnchor ? new URL(authorAnchor.getAttribute('href') || '', location.origin).toString() : '';
    const authorMatch = authorHref.match(profilePattern);
    const authorId = authorMatch ? authorMatch[1] : '';

    const titlePreview =
      lineTexts.find((text) => text && text !== authorName && !/^[\d.万wWkK]+$/.test(text) && text.length >= 4) ||
      clean((img && img.getAttribute('alt')) || '') ||
      texts.find((text) => text && text !== authorName && !/^[\d.万wWkK]+$/.test(text) && text.length >= 4) ||
      noteId;

    results.push({
      note_id: noteId,
      note_url: absolute,
      title_preview: titlePreview,
      author_name: authorName,
      author_id: authorId,
      profile_url: authorHref,
      cover_url: coverUrl,
      collection_id: 'notes',
      collection_name: '笔记',
      collection_order: 1
    });
  }

  const bodyText = document.body.innerText || '';
  const countMatch = bodyText.match(/笔记・(\d+)/);
  return {
    total_notes: countMatch ? Number(countMatch[1]) : 0,
    results,
    scroll_y: Math.round(window.scrollY),
    scroll_height: Math.round(document.documentElement.scrollHeight || document.body.scrollHeight || 0)
  };
})())
"""

    scroll_js = "window.scrollBy(0, Math.max(window.innerHeight * 0.9, 900)); 'ok'"

    merged: Dict[str, dict] = {}
    total_notes = 0
    stable_rounds = 0

    for _ in range(120):
        payload = json.loads(chrome_exec_js(extract_js, timeout_seconds=20))
        total_notes = max(total_notes, int(payload.get("total_notes", 0) or 0))
        before = len(merged)
        for row in payload.get("results", []):
            note_id = str(row.get("note_id", "")).strip()
            if not note_id:
                continue
            merged.setdefault(note_id, row)

        if len(merged) == before:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if total_notes and len(merged) >= total_notes:
            break
        if stable_rounds >= max_empty_rounds:
            break

        chrome_exec_js(scroll_js, timeout_seconds=10)
        time.sleep(1.2)

    collections = [
        {
            "id": "notes",
            "name": "笔记",
            "note_count_estimate": total_notes or len(merged),
        }
    ]
    return {
        "collections": collections,
        "noteRows": list(merged.values()),
    }


def load_existing_export(input_json: Path) -> dict:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    payload.setdefault("sources", payload.get("collections", []))
    payload.setdefault("collections", [])
    payload.setdefault("notes", [])
    payload.setdefault("run_meta", {})
    return payload


def enrich_notes_via_current_chrome(
    notes: List[dict],
    batch_size: int = 10,
) -> List[dict]:
    if not notes:
        return notes

    def parse_count(text: object) -> int:
        raw = str(text or "").strip()
        if not raw:
            return 0
        match = re.search(r"([\d.]+)\s*万", raw)
        if match:
            return int(float(match.group(1)) * 10000)
        match = re.search(r"\d+", raw.replace(",", ""))
        return int(match.group(0)) if match else 0

    pending_notes = [
        note
        for note in notes
        if str(note.get("note_url", "")).strip() and not str(note.get("edited_at", "")).strip()
    ]
    if not pending_notes:
        return notes

    urls = [str(note.get("note_url", "")).strip() for note in pending_notes]
    details_by_url: Dict[str, dict] = {}
    open_windows_output = run_osascript(
        '''
tell application "Google Chrome"
  if (count of windows) = 0 then error "Google Chrome is not open."
  return count of windows as text
end tell
''',
        timeout=10,
    )
    if not open_windows_output:
        return notes

    for index, url in enumerate(urls, start=1):
        js = r"""
JSON.stringify((() => {
  const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
  const bodyText = clean(document.body?.innerText || '');
  const title = clean(document.querySelector('#detail-title, .title')?.textContent || '');
  const content = clean(document.querySelector('#detail-desc, .desc, .note-text')?.textContent || '');
  const author = clean(document.querySelector('.username, .author-wrapper .name')?.textContent || '');
  const likes = clean(document.querySelector('.like-wrapper .count')?.textContent || '');
  const collects = clean(document.querySelector('.collect-wrapper .count')?.textContent || '');
  const comments = clean(document.querySelector('.chat-wrapper .count')?.textContent || '');
  const selectorDateText = clean(
    document.querySelector('.date, time, .publish-time, .note-time, .bottom-container .date, .create-time')?.textContent || ''
  );
  const bodyEditMatch = bodyText.match(/(?:编辑于|最后编辑于|最近编辑于)\s*(20\d{2}[-./年]\d{1,2}[-./月]\d{1,2})/);
  const dateText = bodyEditMatch ? bodyEditMatch[0] : selectorDateText;
  const tags = Array.from(document.querySelectorAll('#detail-desc a.tag, #detail-desc a[href*="search_result"]'))
    .map((node) => clean(node.textContent || ''))
    .filter(Boolean);
  const mediaUrls = Array.from(document.querySelectorAll('img[src*="xhscdn"], img[src*="xiaohongshu"]'))
    .map((node) => (node.currentSrc || node.src || node.getAttribute('src') || '').split('?')[0])
    .filter(Boolean)
    .filter((value, idx, arr) => arr.indexOf(value) === idx)
    .slice(0, 20);
  return {
    url: location.href,
    title,
    content,
    author,
    likes,
    collects,
    comments,
    edited_at: dateText,
    body_text: bodyText,
    tags,
    media_urls: mediaUrls,
    fetch_status: title ? 'full' : 'partial'
  };
})())
"""
        fetch_script = f'''
with timeout of 90 seconds
tell application "Google Chrome"
  tell window 1
    set tabRef to make new tab at end of tabs with properties {{URL:"{applescript_escape(url)}"}}
    set active tab index to (count of tabs)
  end tell
  activate
  delay {8 if index == 1 else 6}
  set payload to execute tabRef javascript "{applescript_escape(js)}"
  tell window 1 to close tabRef
  return payload
end tell
end timeout
'''
        payload = run_osascript(fetch_script, timeout=95)
        row = json.loads(payload)
        if isinstance(row, dict) and row.get("url"):
            details_by_url[str(row["url"])] = row
        if index % max(batch_size, 1) == 0:
            time.sleep(2)

    enriched: List[dict] = []
    for note in notes:
        detail = details_by_url.get(str(note.get("note_url", "")).strip(), {})
        merged = dict(note)
        if detail:
            fetch_status = str(detail.get("fetch_status", "partial") or "partial")
            merged["fetch_status"] = fetch_status
            if fetch_status == "full":
                merged["title"] = str(detail.get("title", "")).strip() or merged.get("title", "") or merged.get("title_preview", "")
                merged["content"] = str(detail.get("content", "")).strip()
                merged["author_name"] = str(detail.get("author", "")).strip() or merged.get("author_name", "")
                edited_at = normalize_xhs_edited_date(detail.get("edited_at", ""))
                if edited_at:
                    merged["edited_at"] = edited_at
                merged["likes"] = parse_count(detail.get("likes"))
                merged["collects"] = parse_count(detail.get("collects"))
                merged["comments"] = parse_count(detail.get("comments"))
                media_urls = [str(value).strip() for value in detail.get("media_urls", []) if str(value).strip()]
                if media_urls:
                    merged["media_urls"] = media_urls
                elif note.get("cover_url"):
                    merged["media_urls"] = [str(note.get("cover_url"))]
                merged["tags"] = [str(value).strip() for value in detail.get("tags", []) if str(value).strip()]
            else:
                merged.setdefault("content", "")
        else:
            merged.setdefault("fetch_status", "partial")
        merged["note_time"] = str(merged.get("note_time", "")).strip() or note_time_from_note_id(merged.get("note_id"))
        merged["note_time_source"] = str(merged.get("note_time_source", "")).strip() or ("note_id" if merged.get("note_time") else "")
        merged.pop("created_at", None)
        merged.pop("edited_at", None)
        enriched.append(merged)
    return enriched


def crawl_with_node(user_data_dir: Optional[str], profile_dir: str, headless: bool, max_empty_rounds: int) -> dict:
    helper_js = f"""
const fs = require('fs');
const os = require('os');
const path = require('path');
const {{ chromium }} = require('playwright');

async function main() {{
  const userDataDir = {json.dumps(user_data_dir or '')} || path.join(os.homedir(), '.codex', 'state', 'xhs-favorites-browser');
  const context = await chromium.launchPersistentContext(userDataDir, {{
    channel: 'chrome',
    headless: {str(headless).lower()},
    viewport: null,
  }});
  const page = context.pages()[0] || await context.newPage();
  await page.goto('https://www.xiaohongshu.com', {{ waitUntil: 'domcontentloaded' }});

  const state = await page.evaluate(async (limit) => {{
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
    const excludedCollections = new Set(['笔记', '专辑', '文件', '全部', '最近', '收藏', '点赞']);
    const noteHrefPattern = /\\/(?:explore|note|search_result|discovery\\/item)\\//;

    const clickableNodes = () =>
      Array.from(document.querySelectorAll('button, a, [role="button"], div, span'))
        .filter((node) => node instanceof HTMLElement)
        .filter((node) => {{
          const text = clean(node.textContent || '');
          if (!text) return false;
          const rect = node.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        }});

    const clickByExactText = async (texts) => {{
      for (const target of texts) {{
        const node = clickableNodes().find((item) => clean(item.textContent || '') === target);
        if (node) {{
          node.click();
          await sleep(1200);
          return true;
        }}
      }}
      return false;
    }};

    const inferCollectionCandidates = () => {{
      const out = [];
      const seen = new Set();
      clickableNodes().forEach((node, index) => {{
        const text = clean(node.textContent || '');
        if (!text || text.length > 40) return;
        const match = text.match(/^(.+?)[·•]\\s*(\\d+)$/) || text.match(/^(.+?)\\s+(\\d+)$/);
        if (!match) return;
        const name = clean(match[1]);
        if (!name || excludedCollections.has(name)) return;
        const key = `${{name}}::${{match[2]}}`;
        if (seen.has(key)) return;
        seen.add(key);
        out.push({{ name, id: name, note_count_estimate: Number(match[2]) || 0, order: index }});
      }});
      return out;
    }};

    const resolveCardRoot = (anchor) => {{
      let node = anchor;
      for (let i = 0; i < 5 && node; i += 1) {{
        if (!(node instanceof HTMLElement)) break;
        const text = clean(node.textContent || '');
        const images = node.querySelectorAll('img').length;
        if (images > 0 && text.length > 0) return node;
        node = node.parentElement;
      }}
      return anchor instanceof HTMLElement ? anchor : null;
    }};

    const collectCards = (collection) => {{
      const results = [];
      const seen = new Set();
      const anchors = Array.from(document.querySelectorAll('a[href]'));
      for (const anchor of anchors) {{
        if (!(anchor instanceof HTMLAnchorElement)) continue;
        const href = anchor.href || '';
        if (!noteHrefPattern.test(href)) continue;
        const noteIdMatch = href.match(/\\/(?:explore|note|search_result|discovery\\/item)\\/([A-Za-z0-9_-]+)/);
        if (!noteIdMatch) continue;
        const noteId = noteIdMatch[1];
        if (seen.has(noteId)) continue;
        seen.add(noteId);
        const card = resolveCardRoot(anchor);
        const textCandidates = [];
        if (card) {{
          card.querySelectorAll('span, div, p, a').forEach((node) => {{
            const text = clean(node.textContent || '');
            if (text && text.length <= 80) textCandidates.push(text);
          }});
        }}
        const uniqueTexts = Array.from(new Set(textCandidates));
        const img = (card && card.querySelector('img')) || anchor.querySelector('img');
        const coverUrl = clean((img && (img.src || img.getAttribute('src'))) || '');
        const titlePreview =
          clean((img && img.getAttribute('alt')) || '') ||
          uniqueTexts.find((text) => text.length >= 4 && !/^[\\d.万wWkK]+$/.test(text)) ||
          noteId;
        const authorName =
          uniqueTexts.find((text) => text !== titlePreview && text.length >= 2 && text.length <= 24) || '';
        results.push({{
          note_id: noteId,
          note_url: href,
          title_preview: titlePreview,
          author_name: authorName,
          author_id: '',
          profile_url: '',
          cover_url: coverUrl,
          collection_id: collection.id,
          collection_name: collection.name,
          collection_order: collection.order,
        }});
      }}
      return results;
    }};

    const scrollUntilStable = async (collection) => {{
      let stableRounds = 0;
      let lastCount = -1;
      let notes = collectCards(collection);
      for (let round = 0; round < 40 && stableRounds < limit; round += 1) {{
        window.scrollTo(0, document.body.scrollHeight);
        await sleep(1200);
        const next = collectCards(collection);
        if (next.length <= lastCount) {{
          stableRounds += 1;
        }} else {{
          stableRounds = 0;
          lastCount = next.length;
          notes = next;
        }}
      }}
      window.scrollTo(0, 0);
      await sleep(300);
      return notes;
    }};

    await clickByExactText(['收藏']);

    let collections = inferCollectionCandidates();
    if (collections.length === 0) {{
      collections = [{{ id: 'default', name: '全部收藏', note_count_estimate: 0, order: 0 }}];
    }}

    const noteRows = [];
    for (const collection of collections) {{
      if (collection.id !== 'default') {{
        await clickByExactText([`${{collection.name}} · ${{collection.note_count_estimate}}`, `${{collection.name}} ${{collection.note_count_estimate}}`, collection.name]);
      }}
      const rows = await scrollUntilStable(collection);
      noteRows.push(...rows);
    }}

    return {{ collections, noteRows }};
  }}, {max_empty_rounds});
  await context.close();
  return state;
}}

main().then((result) => {{
  process.stdout.write(JSON.stringify(result));
}}).catch((error) => {{
  process.stderr.write(String(error && error.stack || error));
  process.exit(1);
}});
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(helper_js)
        helper_path = Path(handle.name)
    try:
        env = os.environ.copy()
        node_path_parts = [global_node_modules_root()]
        if env.get("NODE_PATH"):
            node_path_parts.append(env["NODE_PATH"])
        env["NODE_PATH"] = os.pathsep.join(part for part in node_path_parts if part)
        completed = subprocess.run(
            ["node", str(helper_path)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return json.loads(completed.stdout or "{}")
    finally:
        helper_path.unlink(missing_ok=True)


def export_favorites(
    output_json: Path,
    input_json: Optional[Path] = None,
    favorites_html: Optional[Path] = None,
    liked_html: Optional[Path] = None,
    user_data_dir: Optional[str] = None,
    profile_dir: str = "Default",
    use_current_chrome: bool = False,
    favorites_url: Optional[str] = None,
    headless: bool = False,
    max_empty_rounds: int = 4,
    batch_size: int = 10,
    enrich: bool = True,
) -> dict:
    if input_json is not None:
        existing = load_existing_export(input_json)
        collections = existing.get("sources") or existing.get("collections", [])
        merged_notes = existing.get("notes", [])
        note_count_raw = int(existing.get("run_meta", {}).get("note_count_raw", len(merged_notes)) or len(merged_notes))
    elif favorites_html is not None or liked_html is not None:
        collections = []
        rows: List[dict] = []
        if favorites_html is not None:
            collections.append({"id": "favorites", "name": "收藏", "note_count_estimate": 0})
            favorite_rows = parse_xhs_html_export(favorites_html, source_name="收藏", source_id="favorites")
            collections[-1]["note_count_estimate"] = len(favorite_rows)
            rows.extend(favorite_rows)
        if liked_html is not None:
            collections.append({"id": "liked", "name": "喜欢", "note_count_estimate": 0})
            liked_rows = parse_xhs_html_export(liked_html, source_name="喜欢", source_id="liked")
            collections[-1]["note_count_estimate"] = len(liked_rows)
            rows.extend(liked_rows)
        merged_notes = merge_note_sources(rows)
        note_count_raw = len(rows)
    else:
        raw = (
            crawl_from_current_chrome(max_empty_rounds=max_empty_rounds, favorites_url=favorites_url)
            if use_current_chrome
            else crawl_with_node(user_data_dir=user_data_dir, profile_dir=profile_dir, headless=headless, max_empty_rounds=max_empty_rounds)
        )
        collections = raw.get("collections", []) if isinstance(raw, dict) else []
        note_rows = raw.get("noteRows", []) if isinstance(raw, dict) else []
        merged_notes = merge_note_memberships(note_rows)
        note_count_raw = len(note_rows)

    if enrich:
        merged_notes = (
            enrich_notes_via_current_chrome(merged_notes, batch_size=batch_size)
            if use_current_chrome
            else [enrich_note(note) for note in merged_notes]
        )
    payload = build_payload(collections, merged_notes, note_count_raw)
    output_json = Path(output_json).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    args = parse_args()
    payload = export_favorites(
        input_json=Path(args.input_json).expanduser().resolve() if args.input_json else None,
        favorites_html=Path(args.favorites_html).expanduser().resolve() if args.favorites_html else None,
        liked_html=Path(args.liked_html).expanduser().resolve() if args.liked_html else None,
        output_json=Path(args.output_json),
        user_data_dir=args.user_data_dir,
        profile_dir=args.profile_dir,
        use_current_chrome=args.use_current_chrome,
        favorites_url=args.favorites_url,
        headless=args.headless,
        max_empty_rounds=args.max_empty_rounds,
        batch_size=args.batch_size,
        enrich=not args.skip_enrich,
    )
    print(json.dumps(payload["run_meta"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
