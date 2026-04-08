import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SYNC_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_bilibili_favorites.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SyncBilibiliGlobalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.sync = load_module(SYNC_PATH, "sync_bilibili_global_runtime_test")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bili-global-runtime-test-"))
        self.taxonomy_path = self.temp_dir / "ROOT分类目录.md"
        self.taxonomy_path.write_text(
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

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_create_archive_uses_global_search_and_rubbish_roots(self):
        payload = {
            "uid": "356140132",
            "fetched_at": "2026-04-04T12:00:00Z",
            "folders": [{"id": "100", "title": "AI教程", "media_count": 1}],
            "items": [
                {
                    "folder_id": "100",
                    "folder_name": "AI教程",
                    "media": {
                        "id": 1,
                        "bvid": "BV1TEST1111",
                        "title": "AI 学习路线整理",
                        "intro": "AI 教程与学习路线",
                        "cover": "https://img.example.com/cover-a.jpg",
                        "upper": {"name": "知识区UP主"},
                        "fav_time": 1711000000,
                        "pubtime": 1710000000,
                        "ctime": 1710000000,
                    },
                }
            ],
        }

        input_json = self.temp_dir / "input.json"
        input_json.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        target_root = self.temp_dir / "vault"
        output_root = target_root / "B站"

        self.sync.set_active_language("zh")
        self.sync.normalize_output_tree(output_root)
        incoming = self.sync.normalize_payload(payload, self.taxonomy_path)
        stage_root = self.temp_dir / "stage" / "B站"
        stage_root.mkdir(parents=True, exist_ok=True)
        self.sync.render_structure(stage_root, incoming, set(incoming.keys()), self.taxonomy_path, payload.get("folders"), output_root)
        self.sync.replace_target(output_root, stage_root)

        self.assertFalse((output_root / "06 搜索").exists())
        self.assertFalse((output_root / "07 废弃").exists())
        self.assertTrue((target_root / "搜索").exists())
        self.assertTrue((target_root / "废弃").exists())


if __name__ == "__main__":
    unittest.main()
