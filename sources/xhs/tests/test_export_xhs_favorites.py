import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = SKILL_ROOT / "scripts" / "export_xhs_favorites.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExportXhsFavoritesTest(unittest.TestCase):
    def setUp(self):
        self.export = load_module(EXPORT_PATH, "export_xhs_favorites_test")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="xhs-export-test-"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def write_html(self, path: Path, rows: list[dict]) -> None:
        trs = []
        for row in rows:
            trs.append(
                f"""
                <tr>
                  <td><img src="{row['cover_url']}"></td>
                  <td><a href="{row['note_url']}" target="_blank">{row['title']}</a></td>
                  <td>{row.get('content', '')}</td>
                  <td><a href="{row['profile_url']}" target="_blank">{row['author_name']}</a></td>
                  <td>{row.get('note_type', '普通')}</td>
                  <td>{row.get('likes', '0')}</td>
                </tr>
                """
            )
        path.write_text(
            f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>小红书收藏</title></head>
<body>
<div class="container">
  <table class="table">
    <thead>
      <tr>
        <th>封面图</th>
        <th>笔记标题</th>
        <th>笔记内容</th>
        <th>笔记作者</th>
        <th>笔记类型</th>
        <th>点赞数</th>
      </tr>
    </thead>
    <tbody>
      {''.join(trs)}
    </tbody>
  </table>
</div>
</body>
</html>
""",
            encoding="utf-8",
        )

    def test_normalize_note_url_prefers_search_result_token_and_canonical_url(self):
        normalized = self.export.normalize_note_url(
            "https://www.xiaohongshu.com/explore/abcd1234?xsec_token=abc&foo=1"
        )
        self.assertEqual(normalized["canonical_url"], "https://www.xiaohongshu.com/explore/abcd1234")
        self.assertEqual(normalized["note_url"], "https://www.xiaohongshu.com/explore/abcd1234?xsec_token=abc")
        self.assertEqual(normalized["note_id"], "abcd1234")

    def test_normalize_xhs_edited_date_extracts_edit_label_and_timestamps(self):
        self.assertEqual(self.export.normalize_xhs_edited_date("编辑于 2025-03-12"), "2025-03-12")
        self.assertEqual(self.export.normalize_xhs_edited_date("最后编辑于2025/3/2"), "2025-03-02")
        self.assertEqual(self.export.normalize_xhs_edited_date(1741737600000), "2025-03-12")
        self.assertEqual(self.export.normalize_xhs_edited_date("2025-03-12"), "")

    def test_note_time_from_note_id_extracts_date(self):
        self.assertEqual(
            self.export.note_time_from_note_id("61a06a9a000000002103c4c8"),
            "2021-11-26",
        )
        self.assertEqual(self.export.note_time_from_note_id("bad"), "")

    def test_parse_xhs_html_export_maps_table_rows_to_standard_notes(self):
        html_path = self.temp_dir / "收藏.html"
        self.write_html(
            html_path,
            rows=[
                {
                    "cover_url": "https://img.example.com/a.jpg",
                    "note_url": "https://www.xiaohongshu.com/explore/69d3d0d90000000023012fd2",
                    "title": "提取任何网站的DESIGN.md",
                    "content": "",
                    "profile_url": "https://www.xiaohongshu.com/user/profile/5a199a6edb2e60456682f7f4",
                    "author_name": "Charlex",
                    "note_type": "视频",
                    "likes": "1.2万",
                }
            ],
        )

        rows = self.export.parse_xhs_html_export(html_path, source_name="收藏", source_id="favorites")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["note_id"], "69d3d0d90000000023012fd2")
        self.assertEqual(row["canonical_url"], "https://www.xiaohongshu.com/explore/69d3d0d90000000023012fd2")
        self.assertEqual(row["title"], "提取任何网站的DESIGN.md")
        self.assertEqual(row["title_preview"], "提取任何网站的DESIGN.md")
        self.assertEqual(row["author_id"], "5a199a6edb2e60456682f7f4")
        self.assertEqual(row["author_name"], "Charlex")
        self.assertEqual(row["note_type"], "视频")
        self.assertEqual(row["likes"], 12000)
        self.assertEqual(row["note_time"], "2026-04-06")
        self.assertEqual(row["note_time_source"], "note_id")
        self.assertEqual(row["fetch_status"], "partial")
        self.assertEqual(row["source_actions"], ["收藏"])
        self.assertEqual(row["source_refs"], [{"id": "favorites", "name": "收藏", "order": 1}])

    def test_merge_note_sources_unions_same_note_from_favorites_and_liked(self):
        merged = self.export.merge_note_sources(
            [
                {
                    "note_id": "note-1",
                    "note_url": "https://www.xiaohongshu.com/explore/note-1",
                    "canonical_url": "https://www.xiaohongshu.com/explore/note-1",
                    "title": "第一篇",
                    "title_preview": "第一篇",
                    "author_name": "作者甲",
                    "author_id": "user-a",
                    "profile_url": "https://www.xiaohongshu.com/user/profile/user-a",
                    "content": "",
                    "note_type": "普通",
                    "likes": 12,
                    "cover_url": "https://img.example.com/1.jpg",
                    "media_urls": ["https://img.example.com/1.jpg"],
                    "fetch_status": "partial",
                    "note_time": "2025-04-07",
                    "note_time_source": "note_id",
                    "source_actions": ["收藏"],
                    "source_refs": [{"id": "favorites", "name": "收藏", "order": 1}],
                },
                {
                    "note_id": "note-1",
                    "note_url": "https://www.xiaohongshu.com/explore/note-1",
                    "canonical_url": "https://www.xiaohongshu.com/explore/note-1",
                    "title": "第一篇",
                    "title_preview": "第一篇",
                    "author_name": "作者甲",
                    "author_id": "user-a",
                    "profile_url": "https://www.xiaohongshu.com/user/profile/user-a",
                    "content": "补充内容",
                    "note_type": "普通",
                    "likes": 18,
                    "cover_url": "https://img.example.com/1.jpg",
                    "media_urls": ["https://img.example.com/1.jpg"],
                    "fetch_status": "partial",
                    "note_time": "2025-04-07",
                    "note_time_source": "note_id",
                    "source_actions": ["喜欢"],
                    "source_refs": [{"id": "liked", "name": "喜欢", "order": 1}],
                },
            ]
        )

        self.assertEqual(len(merged), 1)
        row = merged[0]
        self.assertEqual(sorted(row["source_actions"]), ["喜欢", "收藏"])
        self.assertEqual(
            row["source_refs"],
            [
                {"id": "favorites", "name": "收藏", "order": 1},
                {"id": "liked", "name": "喜欢", "order": 1},
            ],
        )
        self.assertEqual(row["likes"], 18)
        self.assertEqual(row["content"], "补充内容")
        self.assertEqual(row["note_time"], "2025-04-07")
        self.assertEqual(row["note_time_source"], "note_id")


if __name__ == "__main__":
    unittest.main()
