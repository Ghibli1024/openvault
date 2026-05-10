import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = SKILL_ROOT / "scripts" / "sync_bilibili_favorites.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SyncBilibiliFavoritesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bili-favs-test-"))
        self.taxonomy_path = self.temp_dir / "ROOT分类目录.md"
        self.taxonomy_path.write_text(
            """# ROOT分类目录

FORMAT: AI_OUTLINE_V1
ROOT_LABEL: ROOT
TOTAL_CANONICAL_PATHS: 6
CONTAINS_URLS: false
PRIMARY_GOAL: taxonomy test

## 一级主类速览

### 工具

- 人工智能：AI 工具与学习
- 各行各业：行业工具

### 信息

- 学习充电：课程与教程
- 生活百科：生活与出行

## 一级分组索引

2.1 工具 | category_count=2 | path_count=3 | node_count=3 | scope=工具与 AI
2.2 信息 | category_count=2 | path_count=3 | node_count=3 | scope=学习与生活

## 机器大纲

3.0 ROOT | type=root | note=唯一根节点

### 工具

3.1 工具 | type=macro_group | child_count=2 | scope=工具与 AI
3.1.1 人工智能 | type=primary_category | alias=- | child_count=1 | scope=AI 工具与学习
3.1.1.1 AI学习指南 | type=category | child_count=0 | scope=AI 教程 学习 指南 路线 课程
3.1.2 各行各业 | type=primary_category | alias=- | child_count=1 | scope=行业工具
3.1.2.1 电商采销 | type=category | child_count=0 | scope=电商 拼多多 天猫 淘宝 店铺 运营 品牌店

### 信息

3.2 信息 | type=macro_group | child_count=2 | scope=学习与生活
3.2.1 学习充电 | type=primary_category | alias=- | child_count=2 | scope=课程与教程
3.2.1.1 视频教程 | type=category | child_count=0 | scope=视频 教程 课程 学习
3.2.1.2 个人成长 | type=category | child_count=0 | scope=逆袭 励志 成长 人生 自律 习惯 心态
3.2.2 生活百科 | type=primary_category | alias=- | child_count=1 | scope=生活与出行
3.2.2.1 个人生活 | type=category | child_count=0 | scope=生活 出行 安全 避坑 共享单车
""",
            encoding="utf-8",
        )
        self.sync = load_module(SYNC_PATH, "sync_bilibili_favorites_test")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def sample_payload(self) -> dict:
        return {
            "uid": "356140132",
            "fetched_at": "2026-04-04T12:00:00Z",
            "folders": [
                {"id": "100", "title": "AI教程", "media_count": 2},
                {"id": "200", "title": "默认收藏夹", "media_count": 1},
            ],
            "items": [
                {
                    "folder_id": "100",
                    "folder_name": "AI教程",
                    "media": {
                        "id": 1,
                        "bvid": "BV1TEST1111",
                        "title": "AI 学习路线整理",
                        "intro": "适合入门的 AI 教程与学习路线",
                        "cover": "https://img.example.com/cover-a.jpg",
                        "upper": {"name": "知识区UP主"},
                        "fav_time": 1711000000,
                        "pubtime": 1710000000,
                        "ctime": 1710000000,
                    },
                },
                {
                    "folder_id": "200",
                    "folder_name": "默认收藏夹",
                    "media": {
                        "id": 2,
                        "bvid": "BV1TEST1111",
                        "title": "AI 学习路线整理",
                        "intro": "适合入门的 AI 教程与学习路线",
                        "cover": "https://img.example.com/cover-a.jpg",
                        "upper": {"name": "知识区UP主"},
                        "fav_time": 1711000000,
                        "pubtime": 1710000000,
                        "ctime": 1710000000,
                    },
                },
                {
                    "folder_id": "100",
                    "folder_name": "AI教程",
                    "media": {
                        "id": 3,
                        "bvid": "BV1TEST2222",
                        "title": "视频教程：高效学习方法",
                        "intro": "课程总结与视频教程",
                        "cover": "https://img.example.com/cover-b.jpg",
                        "upper": {"name": "另一个UP主"},
                        "fav_time": 1712000000,
                        "pubtime": 1711500000,
                        "ctime": 1711500000,
                    },
                },
            ],
        }

    def collision_payload(self) -> dict:
        return {
            "uid": "356140132",
            "fetched_at": "2026-04-04T12:00:00Z",
            "folders": [
                {"id": "301", "title": "AI", "media_count": 1},
                {"id": "302", "title": "ai", "media_count": 1},
                {"id": "401", "title": "计算机", "media_count": 1},
                {"id": "402", "title": "计算机", "media_count": 1},
            ],
            "items": [
                {
                    "folder_id": "301",
                    "folder_name": "AI",
                    "media": {
                        "id": 11,
                        "bvid": "BV1AI000001",
                        "title": "Agent 的“正确答案”来了",
                        "intro": "Agent 工作流",
                        "cover": "https://img.example.com/cover-c.jpg",
                        "upper": {"name": "程序员YT"},
                        "fav_time": 1713000000,
                        "pubtime": 1712500000,
                        "ctime": 1712500000,
                    },
                },
                {
                    "folder_id": "302",
                    "folder_name": "ai",
                    "media": {
                        "id": 12,
                        "bvid": "BV1AI000002",
                        "title": "吴恩达精读论文指南",
                        "intro": "论文与学习路线",
                        "cover": "https://img.example.com/cover-d.jpg",
                        "upper": {"name": "AI史努比"},
                        "fav_time": 1713100000,
                        "pubtime": 1712600000,
                        "ctime": 1712600000,
                    },
                },
                {
                    "folder_id": "401",
                    "folder_name": "计算机",
                    "media": {
                        "id": 13,
                        "bvid": "BV1CS000001",
                        "title": "计算机基础教程 A",
                        "intro": "计算机课程",
                        "cover": "https://img.example.com/cover-e.jpg",
                        "upper": {"name": "课程UP"},
                        "fav_time": 1713200000,
                        "pubtime": 1712700000,
                        "ctime": 1712700000,
                    },
                },
                {
                    "folder_id": "402",
                    "folder_name": "计算机",
                    "media": {
                        "id": 14,
                        "bvid": "BV1CS000002",
                        "title": "计算机基础教程 B",
                        "intro": "计算机课程",
                        "cover": "https://img.example.com/cover-f.jpg",
                        "upper": {"name": "课程UP"},
                        "fav_time": 1713300000,
                        "pubtime": 1712800000,
                        "ctime": 1712800000,
                    },
                },
            ],
        }

    def invalid_payload(self) -> dict:
        return {
            "uid": "356140132",
            "fetched_at": "2026-04-04T12:00:00Z",
            "folders": [
                {"id": "900", "title": "默认收藏夹", "media_count": 3},
            ],
            "items": [
                {
                    "folder_id": "900",
                    "folder_name": "默认收藏夹",
                    "media": {
                        "id": 91,
                        "bvid": "BV1VALID9999",
                        "title": "正常视频",
                        "intro": "正常内容",
                        "cover": "https://img.example.com/valid.jpg",
                        "upper": {"name": "正常UP"},
                        "fav_time": 1711000000,
                        "pubtime": 1710000000,
                        "ctime": 1710000000,
                    },
                },
                {
                    "folder_id": "900",
                    "folder_name": "默认收藏夹",
                    "media": {
                        "id": 92,
                        "bvid": "BV1INVALID1",
                        "title": "已失效视频",
                        "intro": "-",
                        "cover": "https://img.example.com/invalid.jpg",
                        "upper": {"name": "失效UP"},
                        "attr": 1,
                        "fav_time": 1711000000,
                        "pubtime": 1710000000,
                        "ctime": 1710000000,
                    },
                },
                {
                    "folder_id": "900",
                    "folder_name": "默认收藏夹",
                    "media": {
                        "id": 93,
                        "bvid": "",
                        "title": "",
                        "intro": "",
                        "cover": "",
                        "upper": {"name": ""},
                        "fav_time": 1711000000,
                        "pubtime": 1710000000,
                        "ctime": 1710000000,
                    },
                },
            ],
        }

    def make_record(self, **overrides):
        base = {
            "record_id": "BV1BASE0001",
            "item_id": "42",
            "bvid": "BV1BASE0001",
            "title": "默认标题",
            "video_url": "https://www.bilibili.com/video/BV1BASE0001",
            "up_name": "默认UP主",
            "fav_time": "2026-04-01T00:00:00+08:00",
            "publish_time": "2026-03-30T00:00:00+08:00",
            "intro": "默认简介",
            "cover_url": "https://img.example.com/default.jpg",
            "folder_ids": ["100"],
            "folder_names": ["默认收藏夹"],
            "folder_refs": [{"id": "100", "name": "默认收藏夹"}],
            "tags": ["学习"],
            "keywords": ["教程"],
            "domain_parts": ["工具", "人工智能", "AI学习指南"],
            "source_category_paths": [["默认收藏夹"]],
            "raw_media": {"id": 42},
        }
        base.update(overrides)
        return self.sync.FavoriteRecord(**base)

    def test_normalize_payload_dedupes_items_and_unions_folders(self):
        records = self.sync.normalize_payload(self.sample_payload(), self.taxonomy_path)

        self.assertEqual(set(records), {"BV1TEST1111", "BV1TEST2222"})
        merged = records["BV1TEST1111"]
        self.assertEqual(merged.folder_names, ["AI教程", "默认收藏夹"])
        self.assertEqual(merged.folder_ids, ["100", "200"])
        self.assertEqual(merged.folder_refs, [{"id": "100", "name": "AI教程"}, {"id": "200", "name": "默认收藏夹"}])
        self.assertEqual(merged.domain_parts, ["工具", "人工智能", "AI学习指南"])

    def test_normalize_payload_skips_invalid_or_empty_media(self):
        records = self.sync.normalize_payload(self.invalid_payload(), self.taxonomy_path)

        self.assertEqual(set(records), {"BV1VALID9999"})

    def test_merge_records_unions_folder_membership_and_preserves_existing_metadata(self):
        existing = {
            "BV1MERGE0001": self.make_record(
                record_id="BV1MERGE0001",
                bvid="BV1MERGE0001",
                title="已存在视频",
                intro="旧简介",
                folder_ids=["100"],
                folder_names=["默认收藏夹"],
            )
        }
        incoming = {
            "BV1MERGE0001": self.make_record(
                record_id="BV1MERGE0001",
                bvid="BV1MERGE0001",
                title="已存在视频",
                intro="更新后的简介",
                folder_ids=["200"],
                folder_names=["AI教程"],
            ),
            "BV1MERGE0002": self.make_record(
                record_id="BV1MERGE0002",
                bvid="BV1MERGE0002",
                item_id="84",
                title="新视频",
                video_url="https://www.bilibili.com/video/BV1MERGE0002",
            ),
        }

        merged, new_ids = self.sync.merge_records(existing, incoming)

        self.assertEqual(set(merged), {"BV1MERGE0001", "BV1MERGE0002"})
        self.assertEqual(new_ids, {"BV1MERGE0002"})
        self.assertEqual(merged["BV1MERGE0001"].folder_names, ["AI教程", "默认收藏夹"])
        self.assertEqual(merged["BV1MERGE0001"].intro, "更新后的简介")

    def test_sync_records_authoritative_keeps_only_incoming_items(self):
        existing = {
            "BV1OLD000001": self.make_record(
                record_id="BV1OLD000001",
                bvid="BV1OLD000001",
                title="旧视频",
                video_url="https://www.bilibili.com/video/BV1OLD000001",
            ),
            "BV1KEEP00001": self.make_record(
                record_id="BV1KEEP00001",
                bvid="BV1KEEP00001",
                title="保留视频",
                video_url="https://www.bilibili.com/video/BV1KEEP00001",
            ),
        }
        incoming = {
            "BV1KEEP00001": self.make_record(
                record_id="BV1KEEP00001",
                bvid="BV1KEEP00001",
                title="保留视频",
                video_url="https://www.bilibili.com/video/BV1KEEP00001",
            ),
            "BV1NEW000001": self.make_record(
                record_id="BV1NEW000001",
                bvid="BV1NEW000001",
                title="新视频",
                video_url="https://www.bilibili.com/video/BV1NEW000001",
            ),
        }

        synced, new_ids, removed_ids = self.sync.sync_records_authoritative(existing, incoming)

        self.assertEqual(set(synced), {"BV1KEEP00001", "BV1NEW000001"})
        self.assertEqual(new_ids, {"BV1NEW000001"})
        self.assertEqual(removed_ids, {"BV1OLD000001"})

    def test_render_folder_indexes_handles_casefold_and_same_name_collisions(self):
        output_root = self.temp_dir / "B站"
        records = self.sync.normalize_payload(self.collision_payload(), self.taxonomy_path)
        result = self.sync.render_structure(
            output_root,
            records,
            set(records),
            self.taxonomy_path,
            self.collision_payload()["folders"],
        )

        self.assertEqual(result["folder_count"], 4)
        folder_files = sorted((output_root / "03 收藏夹").glob("*.md"))
        self.assertEqual(len(folder_files), 4)
        names = [file.name for file in folder_files]
        self.assertTrue(any(name.startswith("AI") for name in names))
        self.assertTrue(any(name.startswith("ai") for name in names))
        self.assertGreaterEqual(sum(name.startswith("计算机") for name in names), 2)

    def test_render_structure_creates_expected_views_and_dashboard(self):
        output_root = self.temp_dir / "B站收藏"
        records = self.sync.normalize_payload(self.sample_payload(), self.taxonomy_path)

        result = self.sync.render_structure(output_root, records, {"BV1TEST2222"}, self.taxonomy_path, self.sample_payload()["folders"])

        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["folder_count"], 2)
        self.assertTrue((output_root / "01 日期").exists())
        self.assertTrue((output_root / "02 UP主" / "知识区UP主.md").exists())
        self.assertTrue((output_root / "03 收藏夹" / "AI教程.md").exists())
        self.assertTrue((output_root / "04 领域" / "ROOT分类目录.md").exists())
        self.assertTrue((output_root / "05 粗分类" / "AI与前沿科技.md").exists())
        self.assertTrue((output_root / "05 粗分类" / "Index.md").exists())
        self.assertTrue((output_root / "05 粗分类" / "学习成长.md").exists())
        self.assertTrue((output_root.parent / "搜索").exists())
        self.assertTrue((output_root.parent / "废弃").exists())
        dashboard = (output_root / "Dashboard.md").read_text(encoding="utf-8")
        self.assertIn("总视频数", dashboard)
        self.assertIn("新增数量", dashboard)
        self.assertIn("知识区UP主", dashboard)
        self.assertIn("AI教程", dashboard)

    def test_normalize_output_tree_repairs_duplicate_suffix_roots(self):
        root = self.temp_dir / "B站"
        canonical_date = root / "01 日期"
        duplicate_date = root / "01 日期 2"
        canonical_folder = root / "03 收藏夹"
        duplicate_folder = root / "03 收藏夹 2"
        canonical_domain = root / "04 领域"
        duplicate_domain = root / "04 领域 2"
        for path in (canonical_date, duplicate_date, canonical_folder, duplicate_folder, canonical_domain, duplicate_domain):
            path.mkdir(parents=True, exist_ok=True)

        (canonical_date / "2026").mkdir(parents=True, exist_ok=True)
        (duplicate_date / "2025").mkdir(parents=True, exist_ok=True)
        (canonical_folder / "Index.md").write_text("canonical-folder\n", encoding="utf-8")
        (duplicate_folder / "extra.md").write_text("duplicate-folder\n", encoding="utf-8")
        (canonical_domain / "Index.md").write_text("canonical-domain\n", encoding="utf-8")
        (duplicate_domain / "工具.md").write_text("duplicate-domain\n", encoding="utf-8")
        (root / "Dashboard.md").write_text("canonical-dashboard\n", encoding="utf-8")
        (root / "Dashboard 2.md").write_text("duplicate-dashboard\n", encoding="utf-8")

        self.sync.normalize_output_tree(root)

        self.assertTrue((canonical_date / "2026").exists())
        self.assertTrue((canonical_date / "2025").exists())
        self.assertFalse(duplicate_date.exists())
        self.assertTrue((canonical_folder / "extra.md").exists())
        self.assertFalse(duplicate_folder.exists())
        self.assertTrue((canonical_domain / "工具.md").exists())
        self.assertFalse(duplicate_domain.exists())
        self.assertFalse((root / "Dashboard 2.md").exists())
        self.assertFalse((root / "Dashboard (2).md").exists())

    def test_run_delayed_duplicate_audit_waits_and_repairs_duplicate_suffix_roots(self):
        root = self.temp_dir / "B站"
        canonical_date = root / "01 日期"
        duplicate_date = root / "01 日期 2"
        canonical_date.mkdir(parents=True, exist_ok=True)
        duplicate_date.mkdir(parents=True, exist_ok=True)
        (duplicate_date / "2026").mkdir(parents=True, exist_ok=True)

        with mock.patch.object(self.sync.time, "sleep") as mocked_sleep:
            self.sync.run_delayed_duplicate_audit(root, delay_seconds=90)

        mocked_sleep.assert_called_once_with(90)
        self.assertTrue((canonical_date / "2026").exists())
        self.assertFalse(duplicate_date.exists())

    def test_parse_existing_records_round_trips_primary_notes(self):
        output_root = self.temp_dir / "B站收藏"
        records = self.sync.normalize_payload(self.sample_payload(), self.taxonomy_path)
        self.sync.render_structure(output_root, records, set(), self.taxonomy_path, self.sample_payload()["folders"])

        parsed = self.sync.parse_existing_records(output_root / "01 日期")

        self.assertEqual(set(parsed), {"BV1TEST1111", "BV1TEST2222"})
        self.assertEqual(parsed["BV1TEST1111"].folder_names, ["AI教程", "默认收藏夹"])
        self.assertEqual(parsed["BV1TEST1111"].up_name, "知识区UP主")

    def test_fetch_payload_uses_helper_when_input_json_missing(self):
        helper_output = self.temp_dir / "payload.json"
        helper_output.write_text(json.dumps(self.sample_payload(), ensure_ascii=False), encoding="utf-8")
        completed = mock.Mock(stdout=str(helper_output) + "\n", returncode=0)

        with mock.patch.object(self.sync.subprocess, "run", return_value=completed) as mocked_run:
            payload = self.sync.fetch_payload(
                input_json=None,
                helper_script=Path("/tmp/fetch_bilibili_favorites.mjs"),
            )

        self.assertEqual(payload["uid"], "356140132")
        self.assertTrue(mocked_run.called)
        command = mocked_run.call_args.args[0]
        self.assertIn("node", command[0])
        self.assertIn("/tmp/fetch_bilibili_favorites.mjs", command)

    def test_local_build_root_for_icloud_target_uses_managed_state(self):
        target_root = Path("/Users/Totoro/Library/Mobile Documents/iCloud~md~obsidian/Documents/Totoro/04-Resources")
        build_root = self.sync.local_build_root_for_target(target_root, "B站收藏")

        self.assertIsNotNone(build_root)
        assert build_root is not None
        self.assertIn(".codex/state/bilibili-favorites-to-obsidian", str(build_root))
        self.assertEqual(build_root.name, "B站收藏")

    def test_title_language_switches_dashboard_copy(self):
        output_root = self.temp_dir / "B站收藏"
        records = self.sync.normalize_payload(self.sample_payload(), self.taxonomy_path)

        self.sync.set_active_language("en")
        self.sync.render_structure(output_root, records, set(), self.taxonomy_path, self.sample_payload()["folders"])

        dashboard = (output_root / "Dashboard.md").read_text(encoding="utf-8")
        self.assertIn("Bilibili Favorites Dashboard", dashboard)
        self.assertIn("Total Videos", dashboard)

    def test_default_container_name_is_bzhan(self):
        self.assertEqual(self.sync.DEFAULT_CONTAINER_NAME, "B站")

    def test_bilibili_specific_classification_overrides_apply(self):
        records = self.sync.normalize_payload(self.collision_payload(), self.taxonomy_path)

        self.assertEqual(records["BV1AI000002"].domain_parts[-1], "AI学习指南")
        self.assertNotEqual(records["BV1AI000002"].domain_parts[-1], "视频教程")

    def test_independent_coarse_bucket_rules(self):
        ai_record = self.make_record(
            title="AI Agent 工作流入门",
            intro="agent n8n 自动化",
            domain_parts=["工具", "人工智能", "AI学习指南"],
        )
        learning_record = self.make_record(
            record_id="BV1LEARN001",
            bvid="BV1LEARN001",
            title="高效学习方法",
            intro="课程与成长",
            domain_parts=["信息", "学习充电", "视频教程"],
        )
        business_record = self.make_record(
            record_id="BV1BIZ00001",
            bvid="BV1BIZ00001",
            title="拼多多电商运营拆解",
            intro="店铺运营",
            domain_parts=["工具", "各行各业", "电商采销"],
        )
        life_record = self.make_record(
            record_id="BV1LIFE0001",
            bvid="BV1LIFE0001",
            title="共享单车安全提醒",
            intro="出行避坑",
            domain_parts=["信息", "生活百科", "个人生活"],
        )
        resource_record = self.make_record(
            record_id="BV1RES00001",
            bvid="BV1RES00001",
            title="网盘资源合集",
            intro="资源分享",
            domain_parts=["资源", "云盘宝库"],
        )
        creative_record = self.make_record(
            record_id="BV1CREATE01",
            bvid="BV1CREATE01",
            title="视频剪辑与海报设计",
            intro="创作素材",
            domain_parts=["素材", "视频创作"],
        )
        utility_record = self.make_record(
            record_id="BV1UTIL0001",
            bvid="BV1UTIL0001",
            title="Mac 办公效率工具",
            intro="桌面工具",
            domain_parts=["工具", "办公效率"],
        )

        self.assertEqual(self.sync.coarse_bucket_for_record(ai_record), "AI与前沿科技")
        self.assertEqual(self.sync.coarse_bucket_for_record(learning_record), "学习成长")
        self.assertEqual(self.sync.coarse_bucket_for_record(business_record), "商业职场")
        self.assertEqual(self.sync.coarse_bucket_for_record(life_record), "生活见闻")
        self.assertEqual(self.sync.coarse_bucket_for_record(resource_record), "资源内容")
        self.assertEqual(self.sync.coarse_bucket_for_record(creative_record), "创作设计")
        self.assertEqual(self.sync.coarse_bucket_for_record(utility_record), "工具效率")

    def test_custom_coarse_index_rules_drive_bucket_assignment(self):
        existing_root = self.temp_dir / "existing"
        custom_index = existing_root / "05 粗分类" / "Index.md"
        custom_index.parent.mkdir(parents=True, exist_ok=True)
        custom_index.write_text(
            """# 粗分类目录

FORMAT: BILIBILI_COARSE_V1

## 分类规则

### 深度学习研究
- domain-prefix: 工具 / 人工智能
- keyword: ai
- keyword: agent

### 通用学习
- domain-prefix: 信息 / 学习充电
""",
            encoding="utf-8",
        )

        records = self.sync.normalize_payload(self.sample_payload(), self.taxonomy_path)
        output_root = self.temp_dir / "B站"
        self.sync.render_structure(
            output_root,
            records,
            set(records),
            self.taxonomy_path,
            self.sample_payload()["folders"],
            existing_root,
        )

        self.assertTrue((output_root / "05 粗分类" / "深度学习研究.md").exists())
        self.assertTrue((output_root / "05 粗分类" / "通用学习.md").exists())
        self.assertFalse((output_root / "05 粗分类" / "AI与前沿科技.md").exists())

    def test_large_coarse_bucket_uses_heading_based_subsections(self):
        output_root = self.temp_dir / "B站"
        records = {}
        raw_folders = [{"id": "100", "title": "默认收藏夹", "media_count": 18}]
        for idx in range(9):
            record = self.make_record(
                record_id=f"BV1AIA{idx:04d}",
                bvid=f"BV1AIA{idx:04d}",
                title=f"AI 学习条目 {idx}",
                domain_parts=["工具", "人工智能", "AI学习指南"],
            )
            records[record.record_id] = record
        for idx in range(9):
            record = self.make_record(
                record_id=f"BV1AIB{idx:04d}",
                bvid=f"BV1AIB{idx:04d}",
                title=f"编程条目 {idx}",
                domain_parts=["工具", "编程开发", "C C++"],
            )
            records[record.record_id] = record

        self.sync.render_structure(output_root, records, set(records), self.taxonomy_path, raw_folders)

        coarse_file = (output_root / "05 粗分类" / "AI与前沿科技.md").read_text(encoding="utf-8")
        self.assertIn("## 人工智能", coarse_file)
        self.assertIn("## 编程开发", coarse_file)

    def test_preserve_rubbish_root_copies_existing_contents(self):
        existing_root = self.temp_dir / "existing"
        stage_root = self.temp_dir / "stage"
        rubbish_root = existing_root / "07 废弃"
        rubbish_root.mkdir(parents=True, exist_ok=True)
        (rubbish_root / "keep.md").write_text("# Keep\n", encoding="utf-8")

        self.sync.ensure_rubbish_root(stage_root, existing_root)

        self.assertTrue((stage_root / "07 废弃").exists())
        self.assertTrue((stage_root / "07 废弃" / "keep.md").exists())

    def test_prune_unwanted_records_removes_invalid_existing_entries(self):
        valid = self.make_record(
            record_id="BV1VALID9999",
            bvid="BV1VALID9999",
            title="正常视频",
            raw_media={"title": "正常视频", "attr": 0},
        )
        invalid = self.make_record(
            record_id="BV1INVALID1",
            bvid="BV1INVALID1",
            title="已失效视频",
            raw_media={"title": "已失效视频", "attr": 1},
        )
        empty = self.make_record(
            record_id="empty-1",
            bvid="",
            title="视频 mpty-1",
            video_url="",
            raw_media={"title": "", "bvid": "", "intro": ""},
        )

        kept, removed = self.sync.prune_unwanted_records(
            {"BV1VALID9999": valid, "BV1INVALID1": invalid, "empty-1": empty}
        )

        self.assertEqual(set(kept), {"BV1VALID9999"})
        self.assertEqual(removed, {"BV1INVALID1", "empty-1"})

    def test_preserve_search_root_migrates_legacy_folder(self):
        existing_root = self.temp_dir / "existing"
        stage_root = self.temp_dir / "stage"
        legacy_search_root = existing_root / "05 Search"
        legacy_search_root.mkdir(parents=True, exist_ok=True)
        (legacy_search_root / "saved.md").write_text("# Saved\n", encoding="utf-8")

        self.sync.ensure_search_root(stage_root, existing_root)

        self.assertTrue((stage_root / "06 搜索").exists())
        self.assertTrue((stage_root / "06 搜索" / "saved.md").exists())

    def test_legacy_english_top_level_roots_migrate_to_chinese(self):
        root = self.temp_dir / "B站"
        (root / "01 Date" / "2026").mkdir(parents=True, exist_ok=True)
        (root / "04 Domain" / "ROOT分类目录.md").parent.mkdir(parents=True, exist_ok=True)
        (root / "04 Domain" / "ROOT分类目录.md").write_text("# ROOT分类目录\n", encoding="utf-8")
        (root / "06 Search").mkdir(parents=True, exist_ok=True)
        (root / "07 Rubbish").mkdir(parents=True, exist_ok=True)

        self.sync.normalize_output_tree(root)

        self.assertTrue((root / "01 日期" / "2026").exists())
        self.assertTrue((root / "04 领域" / "ROOT分类目录.md").exists())
        self.assertTrue((root / "06 搜索").exists())
        self.assertTrue((root / "07 废弃").exists())
        self.assertFalse((root / "01 Date").exists())
        self.assertFalse((root / "04 Domain").exists())


if __name__ == "__main__":
    unittest.main()
