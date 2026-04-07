#!/usr/bin/env python3
"""
Autofill bookmark annotation descriptions from URL, title, and category context.

This is intended for large archives where manual annotation of every pending URL
is impractical. Output is a JSON list compatible with sync_bookmark_html.py
--annotations-file.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autofill pending bookmark annotations.")
    parser.add_argument("--pending-json", required=True, help="Path to pending_annotations.json")
    parser.add_argument("--output", required=True, help="Where to write the autofilled annotations JSON")
    return parser.parse_args()


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_label(text: str) -> str:
    value = clean(text)
    value = re.sub(r"^[^\w\u4e00-\u9fffA-Za-z]+", "", value)
    return clean(value)


def last_category(item: dict) -> str:
    paths = item.get("category_paths", [])
    if not paths:
        return ""
    for path in paths:
        if path:
            return path[-1]
    return ""


def joined_category(item: dict) -> str:
    paths = item.get("category_paths", [])
    if not paths:
        return ""
    for path in paths:
        if path:
            return " / ".join(path)
    return ""


def normalize_host(host: str) -> str:
    host = clean(host).lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def generic_tool_desc(title: str, leaf: str) -> str:
    normalized_leaf = normalize_label(leaf)
    generic_labels = {"", "其他", "一般", "综合", "工具箱", "网站", "项目", "推荐"}
    if normalized_leaf and normalized_leaf not in generic_labels:
        return f"一个与“{normalized_leaf}”相关的工具或资源页面，用来查看、使用或获取对应功能。"
    return f"一个与“{title}”相关的工具或资源页面，用来查看、使用或获取对应内容。"


def infer_description(item: dict) -> str:
    title = clean(str(item.get("title", "")))
    url = clean(str(item.get("url", "")))
    host = normalize_host(str(item.get("host", "")))
    leaf = clean(last_category(item))
    normalized_leaf = normalize_label(leaf)
    full_category = joined_category(item)
    parsed = urlparse(url)

    title_l = title.lower()
    path_l = parsed.path.lower()

    if host == "github.com":
        return f"一个 GitHub 仓库页，用来查看项目源码、安装说明、文档和更新记录。"
    if host in {"gitlab.com", "gitee.com", "codeberg.org", "sourceforge.net"}:
        return f"一个代码托管平台上的项目页面，用来查看源码、版本信息和使用说明。"
    if host == "gist.github.com":
        return "一个 GitHub Gist 页面，用来查看和分享代码片段或配置脚本。"
    if host == "apps.apple.com":
        return "一个 App Store 应用页面，用来查看应用介绍、系统要求和下载入口。"
    if host == "play.google.com":
        return "一个 Google Play 应用页面，用来查看应用介绍、评价和安装入口。"
    if host in {"chromewebstore.google.com", "chrome.google.com"}:
        return "一个 Chrome 扩展商店页面，用来查看插件介绍、权限说明和安装入口。"
    if host == "greasyfork.org":
        return "一个 Greasy Fork 脚本页面，用来查看脚本介绍、安装方式和更新记录。"
    if host == "t.me":
        return "一个 Telegram 频道、群组或机器人入口，用来加入对应的信息流或资源分发渠道。"
    if host.endswith("bilibili.com"):
        return f"一条与“{leaf or title}”相关的视频页面，用来演示、介绍或讲解对应内容。"
    if host.endswith("youtube.com"):
        return f"一个 YouTube 视频或频道页面，用来观看与“{leaf or title}”相关的内容。"
    if host.endswith("feishu.cn") or host.endswith("larksuite.com"):
        return "一个飞书文档、表格或多维表页面，用来协作整理、记录或查询对应信息。"
    if host.endswith("qq.com") and ("wiki" in path_l or "doc" in path_l):
        return "一个腾讯文档或知识页入口，用来查看、整理或检索对应内容。"
    if host.endswith("notion.so") or host.endswith("notion.site"):
        return "一个 Notion 页面，用来整理、展示或协作对应主题内容。"
    if host.endswith("yuque.com"):
        return "一个语雀页面，用来记录、整理或分享对应主题内容。"
    if host.endswith("kdocs.cn") or host.endswith("docs.qq.com"):
        return "一个在线文档页面，用来记录、协作或分享对应资料。"
    if host.endswith("reddit.com"):
        return "一个 Reddit 帖子或社区页面，用来查看讨论、经验分享或资源线索。"
    if host.endswith("huggingface.co"):
        return "一个 Hugging Face 项目、模型或数据集页面，用来查看说明并获取相关资源。"
    if host.endswith("archive.org"):
        return "一个 Internet Archive 页面，用来浏览、借阅或检索归档资源。"
    if "app store" in title_l or "mac app store" in title_l:
        return "一个应用商店页面，用来查看应用介绍、评价和下载入口。"
    if "documentation" in title_l or "docs" in title_l or "/docs" in path_l:
        return f"一个与“{leaf or title}”相关的文档页面，用来查看使用说明、API 或配置方法。"
    if "官网" in title or "official" in title_l:
        return f"一个与“{leaf or title}”相关的官网页面，用来查看官方介绍和入口。"
    if "插件" in title or "extension" in title_l or "addon" in title_l:
        return f"一个与“{leaf or title}”相关的插件页面，用来查看功能介绍、安装方式或使用说明。"
    if "教程" in title or "guide" in title_l or "how to" in title_l:
        return f"一个与“{leaf or title}”相关的教程页面，用来学习具体用法或操作流程。"
    if "blog" in host or "博客" in title:
        return f"一个与“{leaf or title}”相关的博客或文章页面，用来阅读经验分享、介绍或教程内容。"
    if "wiki" in title_l or "wiki" in host:
        return f"一个与“{leaf or title}”相关的 Wiki 页面，用来查阅整理过的背景资料或条目。"
    if "store" in path_l or "shop" in path_l or "store" in title_l:
        return f"一个与“{leaf or title}”相关的商店或商品页面，用来查看、购买或获取对应资源。"
    if "video" in path_l or "watch" in path_l:
        return f"一个与“{leaf or title}”相关的视频页面，用来观看介绍、演示或教程内容。"
    if host:
        return generic_tool_desc(title or host, normalized_leaf or full_category)
    return f"一个与“{title or full_category or url}”相关的页面，用来查看或获取对应内容。"


def infer_tags(item: dict) -> list[str]:
    tags = []
    host = normalize_host(str(item.get("host", "")))
    leaf = clean(last_category(item))
    if leaf:
        tags.append(normalize_label(leaf))
    if host:
        tags.append(host)
    if host == "github.com":
        tags.append("代码仓库")
    elif host == "apps.apple.com":
        tags.append("App Store")
    elif host == "play.google.com":
        tags.append("Google Play")
    elif host == "greasyfork.org":
        tags.append("脚本")
    elif host == "t.me":
        tags.append("Telegram")
    out = []
    seen = set()
    for tag in tags:
        if tag and tag not in seen:
            out.append(tag)
            seen.add(tag)
    return out[:4]


def main() -> None:
    args = parse_args()
    pending_path = Path(args.pending_json).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    items = json.loads(pending_path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError("pending JSON must be a list")

    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        output.append(
            {
                "url": item.get("url", ""),
                "description": infer_description(item),
                "note": "",
                "tags": infer_tags(item),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "pending_json": str(pending_path),
                "output": str(output_path),
                "count": len(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
