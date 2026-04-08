import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = SKILL_ROOT / "scripts" / "sync_xhs_favorites.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SyncXhsFavoritesTest(unittest.TestCase):
    def setUp(self):
        self.sync = load_module(SYNC_PATH, "sync_xhs_favorites_test")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="xhs-favorites-sync-test-"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def write_taxonomy(self, path: Path) -> None:
        path.write_text(
            """# ROOT分类目录

FORMAT: AI_OUTLINE_V1
ROOT_LABEL: ROOT
TOTAL_CANONICAL_PATHS: 8
CONTAINS_URLS: false
PRIMARY_GOAL: taxonomy test

## 一级主类速览

### 工具

- 人工智能：聊天画图等大模型
- 在线工具：在线工具

### 信息

- 学习充电：学习与课程

## 一级分组索引

2.1 工具 | category_count=2 | path_count=4 | node_count=4 | scope=软件工具与 AI
2.2 信息 | category_count=1 | path_count=2 | node_count=2 | scope=信息学习

## 机器大纲

3.0 ROOT | type=root | note=唯一根节点

### 工具

3.1 工具 | type=macro_group | child_count=2 | scope=软件工具与 AI
3.1.1 人工智能 | type=primary_category | alias=- | child_count=1 | scope=聊天画图等大模型
3.1.1.1 AI图像生成 | type=category | child_count=0 | scope=文生图 绘图 图像生成 comfyui stable diffusion flux
3.1.2 在线工具 | type=primary_category | alias=- | child_count=1 | scope=在线转换与效率工具
3.1.2.1 文本相关 | type=category | child_count=0 | scope=文本 OCR 文档处理 提取

### 信息

3.2 信息 | type=macro_group | child_count=1 | scope=信息学习
3.2.1 学习充电 | type=primary_category | alias=- | child_count=1 | scope=学习与课程
3.2.1.1 AI学习指南 | type=category | child_count=0 | scope=教程 学习 指南 课程

## 4. 规范路径清单

4.1 PATH = ROOT / 工具
4.2 PATH = ROOT / 工具 / 人工智能
4.3 PATH = ROOT / 工具 / 人工智能 / AI图像生成
4.4 PATH = ROOT / 工具 / 在线工具
4.5 PATH = ROOT / 工具 / 在线工具 / 文本相关
4.6 PATH = ROOT / 信息
4.7 PATH = ROOT / 信息 / 学习充电
4.8 PATH = ROOT / 信息 / 学习充电 / AI学习指南
""",
            encoding="utf-8",
        )

    def write_input(self, path: Path, notes: list[dict], collections: list[dict] | None = None) -> None:
        payload = {
            "collections": collections or [],
            "notes": notes,
            "run_meta": {
                "crawled_at": "2026-04-04T12:00:00Z",
                "collection_count": len(collections or []),
                "note_count_raw": len(notes),
                "note_count_unique": len(notes),
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_create_archive_writes_collections_indexes_and_collection_tags(self):
        taxonomy = self.temp_dir / "ROOT分类目录.md"
        self.write_taxonomy(taxonomy)

        input_json = self.temp_dir / "input.json"
        self.write_input(
            input_json,
            notes=[
                {
                    "note_id": "note-1",
                    "note_url": "https://www.xiaohongshu.com/explore/note-1?xsec_token=abc",
                    "canonical_url": "https://www.xiaohongshu.com/explore/note-1",
                    "title": "ComfyUI 生图指南",
                    "title_preview": "ComfyUI 生图指南",
                    "author_name": "作者甲",
                    "author_id": "user-a",
                    "profile_url": "https://www.xiaohongshu.com/user/profile/user-a",
                    "note_time": "2026-04-01",
                    "note_time_source": "note_id",
                    "content": "这是一篇关于 ComfyUI 和图像生成工作流的教程。",
                    "likes": 10,
                    "collects": 20,
                    "comments": 3,
                    "cover_url": "https://img.example.com/cover-1.jpg",
                    "media_urls": ["https://img.example.com/1.jpg"],
                    "fetch_status": "full",
                    "note_type": "视频",
                    "source_actions": ["收藏"],
                    "source_refs": [{"id": "favorites", "name": "收藏", "order": 1}],
                },
                {
                    "note_id": "note-2",
                    "note_url": "https://www.xiaohongshu.com/explore/note-2?xsec_token=def",
                    "canonical_url": "https://www.xiaohongshu.com/explore/note-2",
                    "title": "OCR 文本提取工具",
                    "title_preview": "OCR 文本提取工具",
                    "author_name": "作者乙",
                    "author_id": "user-b",
                    "profile_url": "https://www.xiaohongshu.com/user/profile/user-b",
                    "note_time": "2026-04-02",
                    "note_time_source": "note_id",
                    "content": "在线 OCR 和文本提取工具整理。",
                    "likes": 6,
                    "collects": 9,
                    "comments": 1,
                    "cover_url": "https://img.example.com/cover-2.jpg",
                    "media_urls": [],
                    "fetch_status": "partial",
                    "note_type": "普通",
                    "source_actions": ["喜欢"],
                    "source_refs": [{"id": "liked", "name": "喜欢", "order": 1}],
                },
            ],
            collections=[
                {"id": "favorites", "name": "收藏", "note_count_estimate": 1},
                {"id": "liked", "name": "喜欢", "note_count_estimate": 1},
            ],
        )

        summary = self.sync.sync_archive(
            input_json=input_json,
            target_root=self.temp_dir / "vault",
            mode="create",
            classification="auto",
            title_language="zh",
            taxonomy_path=taxonomy,
        )

        output_root = Path(summary["output_root"])
        self.assertTrue((output_root / "03 来源" / "Index.md").exists())
        self.assertTrue((output_root / "03 来源" / "收藏.md").exists())
        self.assertTrue((output_root / "03 来源" / "喜欢.md").exists())
        self.assertTrue((output_root / "04 领域" / "ROOT分类目录.md").exists())
        self.assertTrue((output_root / "05 粗分类" / "Index.md").exists())
        self.assertTrue((output_root.parent / "搜索").exists())
        self.assertTrue((output_root.parent / "废弃").exists())
        dashboard = (output_root / "Dashboard.md").read_text(encoding="utf-8")
        self.assertIn("来源统计", dashboard)
        self.assertIn("粗分类统计", dashboard)

        source_index = (output_root / "03 来源" / "Index.md").read_text(encoding="utf-8")
        self.assertIn("收藏", source_index)
        self.assertIn("喜欢", source_index)

        note_path = output_root / "01 日期" / "2026" / "4 月" / "ComfyUI 生图指南.md"
        note_text = note_path.read_text(encoding="utf-8")
        self.assertIn('platform: "xiaohongshu"', note_text)
        self.assertIn('note_id: "note-1"', note_text)
        self.assertIn('note_time: "2026-04-01"', note_text)
        self.assertIn('note_time_source: "note_id"', note_text)
        self.assertIn('fetch_status: "full"', note_text)
        self.assertIn('source_actions: ["收藏"]', note_text)
        self.assertIn('source/收藏', note_text)
        self.assertTrue(any(path.name != "Index.md" for path in (output_root / "05 粗分类").glob("*.md")))

    def test_merge_removes_missing_notes_without_local_rubbish_output(self):
        taxonomy = self.temp_dir / "ROOT分类目录.md"
        self.write_taxonomy(taxonomy)
        target_root = self.temp_dir / "vault"

        input_one = self.temp_dir / "input-one.json"
        self.write_input(
            input_one,
            notes=[
                {
                    "note_id": "note-1",
                    "note_url": "https://www.xiaohongshu.com/explore/note-1?xsec_token=abc",
                    "canonical_url": "https://www.xiaohongshu.com/explore/note-1",
                    "title": "ComfyUI 生图指南",
                    "title_preview": "ComfyUI 生图指南",
                    "author_name": "作者甲",
                    "author_id": "user-a",
                    "note_time": "2026-04-01",
                    "note_time_source": "note_id",
                    "content": "图像生成工作流",
                    "likes": 10,
                    "collects": 20,
                    "comments": 3,
                    "cover_url": "",
                    "media_urls": [],
                    "fetch_status": "full",
                    "note_type": "普通",
                    "source_actions": ["收藏"],
                    "source_refs": [{"id": "favorites", "name": "收藏", "order": 1}],
                },
                {
                    "note_id": "note-2",
                    "note_url": "https://www.xiaohongshu.com/explore/note-2?xsec_token=def",
                    "canonical_url": "https://www.xiaohongshu.com/explore/note-2",
                    "title": "OCR 文本提取工具",
                    "title_preview": "OCR 文本提取工具",
                    "author_name": "作者乙",
                    "author_id": "user-b",
                    "note_time": "2026-04-02",
                    "note_time_source": "note_id",
                    "content": "在线 OCR 和文本提取工具整理。",
                    "likes": 6,
                    "collects": 9,
                    "comments": 1,
                    "cover_url": "",
                    "media_urls": [],
                    "fetch_status": "partial",
                    "note_type": "普通",
                    "source_actions": ["喜欢"],
                    "source_refs": [{"id": "liked", "name": "喜欢", "order": 1}],
                },
            ],
        )
        self.sync.sync_archive(
            input_json=input_one,
            target_root=target_root,
            mode="create",
            classification="auto",
            title_language="zh",
            taxonomy_path=taxonomy,
        )

        input_two = self.temp_dir / "input-two.json"
        self.write_input(
            input_two,
            notes=[
                {
                    "note_id": "note-2",
                    "note_url": "https://www.xiaohongshu.com/explore/note-2?xsec_token=def",
                    "canonical_url": "https://www.xiaohongshu.com/explore/note-2",
                    "title": "OCR 文本提取工具",
                    "title_preview": "OCR 文本提取工具",
                    "author_name": "作者乙",
                    "author_id": "user-b",
                    "note_time": "2026-04-02",
                    "note_time_source": "note_id",
                    "content": "在线 OCR 和文本提取工具整理。",
                    "likes": 7,
                    "collects": 12,
                    "comments": 2,
                    "cover_url": "",
                    "media_urls": [],
                    "fetch_status": "full",
                    "note_type": "普通",
                    "source_actions": ["喜欢"],
                    "source_refs": [{"id": "liked", "name": "喜欢", "order": 1}],
                },
            ],
        )
        summary = self.sync.sync_archive(
            input_json=input_two,
            target_root=target_root,
            mode="merge",
            classification="auto",
            title_language="zh",
            taxonomy_path=taxonomy,
        )

        output_root = Path(summary["output_root"])
        active_note = output_root / "01 日期" / "2026" / "4 月" / "OCR 文本提取工具.md"
        removed_note = output_root / "01 日期" / "2026" / "4 月" / "ComfyUI 生图指南.md"
        self.assertTrue(active_note.exists())
        self.assertFalse(removed_note.exists())
        self.assertFalse((output_root / "07 废弃").exists())
        self.assertTrue((output_root.parent / "废弃").exists())
        self.assertEqual(summary["final_notes"], 1)
        self.assertEqual(summary["rubbish_moved"], 0)

    def test_normalize_output_tree_repairs_duplicate_suffix_files(self):
        root = self.temp_dir / "小红书"
        date_dir = root / "01 日期" / "未知日期"
        author_dir = root / "02 作者"
        source_dir = root / "03 来源"
        domain_dir = root / "04 领域"
        coarse_dir = root / "05 粗分类"
        search_dir = root / "06 搜索"
        rubbish_dir = root / "07 废弃"
        for path in (date_dir, author_dir, source_dir, domain_dir, coarse_dir, search_dir, rubbish_dir):
            path.mkdir(parents=True, exist_ok=True)

        orphan = date_dir / "Example 2.md"
        orphan.write_text("orphan\n", encoding="utf-8")
        canonical_author = author_dir / "alice.md"
        duplicate_author = author_dir / "alice 3.md"
        canonical_author.write_text("new\n", encoding="utf-8")
        duplicate_author.write_text("old\n", encoding="utf-8")
        canonical_domain = domain_dir / "工具.md"
        duplicate_domain = domain_dir / "工具 3.md"
        canonical_domain.write_text("new\n", encoding="utf-8")
        duplicate_domain.write_text("old\n", encoding="utf-8")
        canonical_source = source_dir / "收藏.md"
        duplicate_source = source_dir / "收藏 3.md"
        canonical_source.write_text("new\n", encoding="utf-8")
        duplicate_source.write_text("old\n", encoding="utf-8")
        canonical_domain_dir = domain_dir / "工具"
        duplicate_domain_dir = domain_dir / "工具 2"
        canonical_domain_dir.mkdir(parents=True, exist_ok=True)
        duplicate_domain_dir.mkdir(parents=True, exist_ok=True)
        (canonical_domain_dir / "Index.md").write_text("canonical\n", encoding="utf-8")
        (duplicate_domain_dir / "extra.md").write_text("extra\n", encoding="utf-8")
        (coarse_dir / "AI与前沿科技.md").write_text("canonical-coarse\n", encoding="utf-8")
        (coarse_dir / "AI与前沿科技 2.md").write_text("duplicate-coarse\n", encoding="utf-8")
        (root / "Dashboard.md").write_text("dashboard\n", encoding="utf-8")
        (root / "Dashboard 2.md").write_text("dashboard-dup\n", encoding="utf-8")

        self.sync.normalize_output_tree(root)

        self.assertTrue((date_dir / "Example.md").exists())
        self.assertFalse(orphan.exists())
        self.assertTrue(canonical_author.exists())
        self.assertFalse(duplicate_author.exists())
        self.assertTrue(canonical_domain.exists())
        self.assertFalse(duplicate_domain.exists())
        self.assertTrue(canonical_source.exists())
        self.assertFalse(duplicate_source.exists())
        self.assertTrue((canonical_domain_dir / "extra.md").exists())
        self.assertFalse(duplicate_domain_dir.exists())
        self.assertFalse((coarse_dir / "AI与前沿科技 2.md").exists())
        self.assertFalse((root / "Dashboard 2.md").exists())
        self.assertTrue((root.parent / "废弃").exists())

    def test_migrate_legacy_root_layout_renames_old_root_numbers(self):
        root = self.temp_dir / "小红书"
        legacy_search = root / "04 Search"
        legacy_collections = root / "05 Collections"
        legacy_rubbish = root / "05 Rubbish"
        legacy_date = root / "01 Date"
        legacy_author = root / "02 Author"
        legacy_domain = root / "03 Domain"
        for path in (legacy_search, legacy_collections, legacy_rubbish, legacy_date, legacy_author, legacy_domain):
            path.mkdir(parents=True, exist_ok=True)
        (legacy_search / "old-search.md").write_text("search\n", encoding="utf-8")
        (legacy_collections / "old-collection.md").write_text("collection\n", encoding="utf-8")
        (legacy_rubbish / "old-rubbish.md").write_text("rubbish\n", encoding="utf-8")
        (legacy_date / "sample.md").write_text("date\n", encoding="utf-8")
        (legacy_author / "alice.md").write_text("author\n", encoding="utf-8")
        (legacy_domain / "ROOT分类目录.md").write_text("# ROOT分类目录\n", encoding="utf-8")

        self.sync.migrate_legacy_root_layout(root)

        self.assertFalse(legacy_rubbish.exists())
        self.assertFalse(legacy_collections.exists())
        self.assertFalse(legacy_search.exists())
        self.assertFalse(legacy_date.exists())
        self.assertFalse(legacy_author.exists())
        self.assertFalse(legacy_domain.exists())
        self.assertTrue((root / "01 日期" / "sample.md").exists())
        self.assertTrue((root / "02 作者" / "alice.md").exists())
        self.assertTrue((root / "03 来源" / "old-collection.md").exists())
        self.assertTrue((root / "04 领域" / "ROOT分类目录.md").exists())
        self.assertTrue((root.parent / "搜索" / "old-search.md").exists())
        self.assertTrue((root.parent / "废弃" / "old-rubbish.md").exists())


if __name__ == "__main__":
    unittest.main()
