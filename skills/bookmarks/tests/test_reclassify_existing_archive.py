import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path("/Users/Totoro/.codex/skills/html-bookmarks-to-markdown/scripts")
SYNC_PATH = SCRIPT_DIR / "sync_bookmark_html.py"
RECLASSIFY_PATH = SCRIPT_DIR / "reclassify_existing_archive.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def concealed_text(*codepoints: int) -> str:
    return "".join(chr(codepoint) for codepoint in codepoints)


class ReclassifyExistingArchiveTest(unittest.TestCase):
    def setUp(self):
        self.sync = load_module(SYNC_PATH, "sync_bookmark_html_test")
        self.reclassify = load_module(RECLASSIFY_PATH, "reclassify_existing_archive_test")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="reclassify-existing-archive-test-"))
        self.archive_root = self.temp_dir / "书签库"
        self.archive_root.mkdir(parents=True, exist_ok=True)
        self.state_root = self.archive_root / "_state"
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.target_taxonomy = self.temp_dir / "target_taxonomy.md"
        self._write_fixture_files()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _write_fixture_files(self):
        old_taxonomy = """# ROOT分类目录

FORMAT: AI_OUTLINE_V1
ROOT_LABEL: ROOT
TOTAL_CANONICAL_PATHS: 4
CONTAINS_URLS: false
PRIMARY_GOAL: 旧模板

## 一级主类速览

### 旧分组

- 旧类

## 一级分组索引

2.1 旧分组 | category_count=1 | path_count=1 | node_count=1 | scope=旧分组

## 机器大纲

3.0 ROOT | type=root | note=唯一根节点

### 旧分组

3.1 旧分组 | type=macro_group | child_count=1 | scope=旧分组
3.1.1 旧类 | type=primary_category | alias=- | child_count=0 | scope=旧类

## 4. 规范路径清单

4.1 PATH = ROOT / 旧分组
4.2 PATH = ROOT / 旧分组 / 旧类
"""
        new_taxonomy = """# ROOT分类目录

FORMAT: AI_OUTLINE_V1
ROOT_LABEL: ROOT
TOTAL_CANONICAL_PATHS: 4
CONTAINS_URLS: false
PRIMARY_GOAL: 新模板

## 一级主类速览

- 技术：软件 工具 AI agent 插件 cli 编辑器
- 生活：食谱 家庭 烹饪

## 3. 规范大纲树

3.0 ROOT | type=root | note=唯一根节点
3.1 技术 | type=primary_category | child_count=1 | scope=软件 工具 AI agent 插件 cli 编辑器
3.1.1 工具 | type=category | child_count=0 | scope=软件 工具 AI agent 插件 cli 编辑器
3.2 生活 | type=primary_category | child_count=1 | scope=食谱 家庭 烹饪
3.2.1 菜谱 | type=category | child_count=0 | scope=食谱 家庭 烹饪

## 4. 规范路径清单

4.1 PATH = ROOT / 技术
4.2 PATH = ROOT / 技术 / 工具
4.3 PATH = ROOT / 生活
4.4 PATH = ROOT / 生活 / 菜谱
"""
        root_index = """# ROOT

- 当前子树 URL 总数: 2
- 当前节点直挂 URL 数: 0
- 直接子分类数: 1

## 子分类

- [旧分组](旧分组/Index.md) (2)

# 手动

在下面每行填一个网址。下次运行 Skill 时会自动归类这些网址，然后清空这里的网址列表。
https://example.dev/tool
https://manual.example.ai/agent
"""
        old_root_dir = self.archive_root / "旧分组"
        old_root_dir.mkdir(parents=True, exist_ok=True)
        (old_root_dir / "Index.md").write_text("# 旧分组\n", encoding="utf-8")
        (self.archive_root / "ROOT分类目录.md").write_text(old_taxonomy, encoding="utf-8")
        (self.target_taxonomy).write_text(new_taxonomy, encoding="utf-8")
        (self.archive_root / "Index.md").write_text(root_index, encoding="utf-8")

        state = {
            "version": 1,
            "last_sync_at": "2026-04-02T00:00:00+00:00",
            "source_html": "/tmp/old.html",
            "records": {
                "https://example.dev/tool": {
                    "url": "https://example.dev/tool",
                    "host": "example.dev",
                    "title": "VS Code 插件大全",
                    "titles": ["VS Code 插件大全"],
                    "category_paths": [["ROOT", "旧分组", "旧类"]],
                    "source_category_paths": [["ROOT", "旧分组", "旧类"]],
                    "bookmark_count": 1,
                    "bookmark_add_dates": [],
                    "bookmark_last_modified_dates": [],
                    "description": "保留描述",
                    "note": "保留备注",
                    "tags": ["keep-tag"],
                    "status": "active",
                    "first_seen_at": "2026-04-01T00:00:00+00:00",
                    "last_seen_at": "2026-04-01T00:00:00+00:00",
                    "removed_at": "",
                    "source_signature": "sig-a",
                },
                "https://example.life/food": {
                    "url": "https://example.life/food",
                    "host": "example.life",
                    "title": "家庭菜谱收集",
                    "titles": ["家庭菜谱收集"],
                    "category_paths": [["ROOT", "旧分组", "旧类"]],
                    "source_category_paths": [["ROOT", "旧分组", "旧类"]],
                    "bookmark_count": 1,
                    "bookmark_add_dates": [],
                    "bookmark_last_modified_dates": [],
                    "description": "",
                    "note": "",
                    "tags": [],
                    "status": "active",
                    "first_seen_at": "2026-04-01T00:00:00+00:00",
                    "last_seen_at": "2026-04-01T00:00:00+00:00",
                    "removed_at": "",
                    "source_signature": "sig-b",
                },
            },
        }
        (self.state_root / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.state_root / "latest-summary.json").write_text("{}\n", encoding="utf-8")
        (self.state_root / "Index.md").write_text("# 状态目录\n", encoding="utf-8")

    def test_reclassifies_existing_archive_and_clears_manual_urls(self):
        with mock.patch.object(self.reclassify.sync, "fetch_url_title", return_value="AI Agent 工具箱"):
            result = self.reclassify.reclassify_existing_archive(
                archive_root=self.archive_root,
                taxonomy_reference_md=self.target_taxonomy,
                backup_root=None,
                display_category_source="reference",
            )

        backup_root = Path(result["backup_root"])
        self.assertTrue(backup_root.exists())
        self.assertTrue((backup_root / "ROOT分类目录.md").exists())

        state = json.loads((self.state_root / "state.json").read_text(encoding="utf-8"))
        summary = json.loads((self.state_root / "latest-summary.json").read_text(encoding="utf-8"))
        index_text = (self.archive_root / "Index.md").read_text(encoding="utf-8")

        self.assertEqual(state["source_mode"], "state-reclassify")
        self.assertEqual(summary["source_mode"], "state-reclassify")
        self.assertEqual(summary["manual_urls_processed"], 2)
        self.assertEqual(summary["new_urls"], 1)
        self.assertGreater(summary["changed_urls"], 0)
        self.assertEqual(summary["removed_urls"], 0)
        self.assertIn("技术", summary["top_level_categories"])
        self.assertIn("生活", summary["top_level_categories"])
        self.assertNotIn("旧分组", summary["top_level_categories"])

        existing = state["records"]["https://example.dev/tool"]
        self.assertEqual(existing["description"], "保留描述")
        self.assertEqual(existing["note"], "保留备注")
        self.assertEqual(existing["tags"], ["keep-tag"])
        self.assertEqual(existing["category_paths"], [["ROOT", "技术", "工具"]])

        manual_new = state["records"]["https://manual.example.ai/agent"]
        self.assertEqual(manual_new["status"], "active")
        self.assertEqual(manual_new["category_paths"], [["ROOT", "技术", "工具"]])

        self.assertIn("# 手动", index_text)
        self.assertNotIn("https://manual.example.ai/agent", index_text)
        self.assertNotIn("https://example.dev/tool", index_text)
        self.assertTrue((self.archive_root / "技术" / "Index.md").exists())
        self.assertTrue((self.archive_root / "生活" / "Index.md").exists())
        self.assertFalse((self.archive_root / "旧分组").exists())

    def test_parse_ai_outline_allows_ungrouped_primary_categories_alongside_macro_groups(self):
        taxonomy_path = self.temp_dir / "hybrid_taxonomy.md"
        taxonomy_path.write_text(
            """# ROOT分类目录

FORMAT: AI_OUTLINE_V1
ROOT_LABEL: ROOT
TOTAL_CANONICAL_PATHS: 8
CONTAINS_URLS: false
PRIMARY_GOAL: 混合分组模板

## 一级主类速览

### 资源

- 影视大全

### 工具

- 在线工具

## 根目录直挂主类

- 自定义入口
- 自定义项目

## 一级分组索引

2.1 资源 | category_count=1 | path_count=1 | node_count=1 | scope=资源
2.2 工具 | category_count=1 | path_count=1 | node_count=1 | scope=工具

## 机器大纲

3.0 ROOT | type=root | note=唯一根节点

### 资源

3.1 资源 | type=macro_group | child_count=1 | scope=资源
3.1.1 影视大全 | type=primary_category | alias=- | child_count=0 | scope=影视

### 工具

3.2 工具 | type=macro_group | child_count=1 | scope=工具
3.2.1 在线工具 | type=primary_category | alias=- | child_count=0 | scope=工具

3.3 自定义入口 | type=primary_category | alias=- | child_count=0 | scope=内部入口 直挂根目录
3.4 自定义项目 | type=primary_category | alias=- | child_count=0 | scope=内部项目 直挂根目录

## 4. 规范路径清单

4.1 PATH = ROOT / 资源
4.2 PATH = ROOT / 资源 / 影视大全
4.3 PATH = ROOT / 工具
4.4 PATH = ROOT / 工具 / 在线工具
4.5 PATH = ROOT / 自定义入口
4.6 PATH = ROOT / 自定义项目
""",
            encoding="utf-8",
        )

        reference = self.sync.parse_taxonomy_reference_markdown(taxonomy_path)
        rendered = self.sync.render_ai_outline_sync_sections(reference)

        self.assertEqual(reference.children_by_parent[(reference.root_label,)], ["工具", "自定义入口", "自定义项目", "资源"])
        self.assertIn(("ROOT", "自定义入口"), reference.reference_paths)
        self.assertIn(("ROOT", "自定义项目"), reference.reference_paths)
        self.assertIn("3.3 自定义入口 | type=primary_category", rendered)
        self.assertIn("3.4 自定义项目 | type=primary_category", rendered)

    def test_public_default_taxonomy_is_used_for_bootstrap_without_existing_archive_taxonomy(self):
        public_default = self.temp_dir / "public-default.md"
        public_default.write_text(
            """# ROOT分类目录

FORMAT: AI_OUTLINE_V1
ROOT_LABEL: ROOT
TOTAL_CANONICAL_PATHS: 2
CONTAINS_URLS: false
PRIMARY_GOAL: 公开模板

## 一级主类速览

- 公开分类：通用使用

## 3. 规范大纲树

3.0 ROOT | type=root | note=唯一根节点
3.1 公开分类 | type=primary_category | child_count=0 | scope=通用使用

## 4. 规范路径清单

4.1 PATH = ROOT / 公开分类
""",
            encoding="utf-8",
        )

        target_root = self.temp_dir / "bootstrap-target"
        with mock.patch.object(self.sync, "DEFAULT_ROOT_TAXONOMY_PATH", public_default):
            taxonomy_path, bootstrap_used = self.sync.ensure_taxonomy_reference_file(
                target_root=target_root,
                entries=[],
                explicit_reference=None,
                bootstrap_source="auto",
            )

        self.assertEqual(bootstrap_used, "internal-default")
        self.assertEqual(taxonomy_path, target_root / "ROOT分类目录.md")
        self.assertIn("公开分类", taxonomy_path.read_text(encoding="utf-8"))

    def test_existing_archive_taxonomy_beats_public_default(self):
        public_default = self.temp_dir / "public-default.md"
        public_default.write_text(
            "# ROOT分类目录\n\nFORMAT: AI_OUTLINE_V1\nROOT_LABEL: ROOT\nTOTAL_CANONICAL_PATHS: 1\nCONTAINS_URLS: false\nPRIMARY_GOAL: 公开模板\n\n## 一级主类速览\n\n- 公开分类\n\n## 3. 规范大纲树\n\n3.0 ROOT | type=root | note=唯一根节点\n3.1 公开分类 | type=primary_category | child_count=0\n\n## 4. 规范路径清单\n\n4.1 PATH = ROOT / 公开分类\n",
            encoding="utf-8",
        )
        target_root = self.temp_dir / "existing-archive"
        target_root.mkdir(parents=True, exist_ok=True)
        existing_taxonomy = target_root / "ROOT分类目录.md"
        existing_taxonomy.write_text(
            "# ROOT分类目录\n\nFORMAT: AI_OUTLINE_V1\nROOT_LABEL: ROOT\nTOTAL_CANONICAL_PATHS: 1\nCONTAINS_URLS: false\nPRIMARY_GOAL: 现有模板\n\n## 一级主类速览\n\n- 现有分类\n\n## 3. 规范大纲树\n\n3.0 ROOT | type=root | note=唯一根节点\n3.1 现有分类 | type=primary_category | child_count=0\n\n## 4. 规范路径清单\n\n4.1 PATH = ROOT / 现有分类\n",
            encoding="utf-8",
        )

        with mock.patch.object(self.sync, "DEFAULT_ROOT_TAXONOMY_PATH", public_default):
            taxonomy_path, bootstrap_used = self.sync.ensure_taxonomy_reference_file(
                target_root=target_root,
                entries=[],
                explicit_reference=None,
                bootstrap_source="auto",
            )

        self.assertIsNone(bootstrap_used)
        self.assertEqual(taxonomy_path, existing_taxonomy)
        self.assertIn("现有分类", taxonomy_path.read_text(encoding="utf-8"))

    def test_public_default_template_has_no_private_source_branches(self):
        default_path = Path("/Users/Totoro/.codex/skills/html-bookmarks-to-markdown/references/default_root_taxonomy.md")
        text = default_path.read_text(encoding="utf-8")
        reference = self.sync.parse_taxonomy_reference_markdown(default_path)
        private_branch_a = concealed_text(20250, 21592, 19987, 20139)
        private_branch_b = concealed_text(31449, 28857, 39033, 30446)

        self.assertNotIn(private_branch_a, text)
        self.assertNotIn(private_branch_b, text)
        self.assertNotIn(private_branch_a, reference.primary_categories)
        self.assertNotIn(private_branch_b, reference.primary_categories)


if __name__ == "__main__":
    unittest.main()
