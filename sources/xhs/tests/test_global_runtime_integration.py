import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SYNC_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_xhs_favorites.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SyncXhsGlobalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.sync = load_module(SYNC_PATH, "sync_xhs_global_runtime_test")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="xhs-global-runtime-test-"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_create_archive_uses_global_search_and_rubbish_roots(self):
        taxonomy = self.temp_dir / "ROOT分类目录.md"
        taxonomy.write_text(
            """# ROOT分类目录

FORMAT: AI_OUTLINE_V1
ROOT_LABEL: ROOT
TOTAL_CANONICAL_PATHS: 3
CONTAINS_URLS: false
PRIMARY_GOAL: test

## 一级主类速览

### 工具

- 人工智能：测试分类

## 机器大纲

3.0 ROOT | type=root | note=唯一根节点

### 工具

3.1 工具 | type=macro_group | child_count=1 | scope=工具
3.1.1 人工智能 | type=primary_category | alias=- | child_count=1 | scope=AI
3.1.1.1 测试分类 | type=category | child_count=0 | scope=测试
""",
            encoding="utf-8",
        )
        input_json = self.temp_dir / "input.json"
        input_json.write_text(
            json.dumps(
                {
                    "collections": [],
                    "notes": [
                        {
                            "note_id": "note-1",
                            "note_url": "https://www.xiaohongshu.com/explore/note-1?xsec_token=abc",
                            "canonical_url": "https://www.xiaohongshu.com/explore/note-1",
                            "title": "XHS Note",
                            "title_preview": "XHS Note",
                            "author_name": "作者甲",
                            "author_id": "user-a",
                            "note_time": "2026-04-01",
                            "note_time_source": "note_id",
                            "content": "内容",
                            "likes": 1,
                            "collects": 1,
                            "comments": 0,
                            "cover_url": "",
                            "media_urls": [],
                            "fetch_status": "full",
                            "note_type": "普通",
                            "source_actions": ["收藏"],
                            "source_refs": [],
                        }
                    ],
                    "run_meta": {"crawled_at": "2026-04-04T12:00:00Z"},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
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
        self.assertFalse((output_root / "06 搜索").exists())
        self.assertFalse((output_root / "07 废弃").exists())
        self.assertTrue((output_root.parent / "搜索").exists())
        self.assertTrue((output_root.parent / "废弃").exists())


if __name__ == "__main__":
    unittest.main()
