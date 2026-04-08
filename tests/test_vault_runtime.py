import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "vault_runtime.py"


def load_module(testcase: unittest.TestCase):
    if not SCRIPT_PATH.exists():
        testcase.fail(f"missing runtime helper: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("vault_runtime_test_module", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        testcase.fail(f"unable to load runtime helper from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VaultRuntimeTests(unittest.TestCase):
    def test_resolve_resources_root_prefers_explicit_then_detects_known_candidates(self):
        runtime = load_module(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir) / "Vault"
            detected = vault_root / "04-Resources"
            detected.mkdir(parents=True, exist_ok=True)
            explicit = vault_root / "CustomResources"
            explicit.mkdir(parents=True, exist_ok=True)

            self.assertEqual(
                runtime.resolve_resources_root(vault_root=vault_root, explicit_root=explicit),
                explicit.resolve(),
            )
            self.assertEqual(
                runtime.resolve_resources_root(vault_root=vault_root, explicit_root=None),
                detected.resolve(),
            )

            detected.rmdir()
            compact = vault_root / "04Resources"
            compact.mkdir(parents=True, exist_ok=True)
            self.assertEqual(
                runtime.resolve_resources_root(vault_root=vault_root, explicit_root=None),
                compact.resolve(),
            )

    def test_migrate_resources_layout_renames_legacy_roots_and_lifts_search_rubbish(self):
        runtime = load_module(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            (resources_root / "书签库").mkdir(parents=True)
            (resources_root / "X Likes" / "04 Search").mkdir(parents=True)
            (resources_root / "B站" / "06 搜索").mkdir(parents=True)
            (resources_root / "小红书" / "07 废弃").mkdir(parents=True)
            (resources_root / "X Likes" / "04 Search" / "query.md").write_text("x-search\n", encoding="utf-8")
            (resources_root / "B站" / "06 搜索" / "bili.md").write_text("bili-search\n", encoding="utf-8")
            (resources_root / "小红书" / "07 废弃" / "xhs.md").write_text("xhs-rubbish\n", encoding="utf-8")

            runtime.migrate_resources_layout(resources_root)

            self.assertTrue((resources_root / "书签").exists())
            self.assertTrue((resources_root / "X").exists())
            self.assertFalse((resources_root / "书签库").exists())
            self.assertFalse((resources_root / "X Likes").exists())
            self.assertFalse((resources_root / "B站" / "06 搜索").exists())
            self.assertFalse((resources_root / "小红书" / "07 废弃").exists())
            self.assertTrue((resources_root / "搜索" / "query.md").exists())
            self.assertTrue((resources_root / "搜索" / "bili.md").exists())
            self.assertTrue((resources_root / "废弃" / "xhs.md").exists())

    def test_collect_global_rubbish_signals_reads_notes_urls_and_wikilinks(self):
        runtime = load_module(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            active_x = resources_root / "X" / "01 Date" / "2026" / "3 月" / "Hello.md"
            active_x.parent.mkdir(parents=True, exist_ok=True)
            active_x.write_text(
                "\n".join(
                    [
                        "---",
                        'tweet_id: "123"',
                        'title: "Hello"',
                        "---",
                        "",
                        "# Hello",
                    ]
                ),
                encoding="utf-8",
            )

            rubbish_root = resources_root / "废弃"
            rubbish_root.mkdir(parents=True, exist_ok=True)
            (rubbish_root / "delete-xhs.md").write_text(
                "\n".join(
                    [
                        "---",
                        'platform: "xiaohongshu"',
                        'note_id: "note-1"',
                        'canonical_url: "https://www.xiaohongshu.com/explore/note-1"',
                        "---",
                    ]
                ),
                encoding="utf-8",
            )
            (rubbish_root / "cleanup.md").write_text(
                "\n".join(
                    [
                        "- [[X/01 Date/2026/3 月/Hello|Hello]]",
                        "- https://x.com/alice/status/456",
                        "- https://www.bilibili.com/video/BV1TEST1234",
                        "- https://example.com/bookmark-entry",
                    ]
                ),
                encoding="utf-8",
            )

            signals = runtime.collect_global_rubbish_signals(resources_root)

            self.assertEqual(signals["X"]["ids"], {"123", "456"})
            self.assertEqual(signals["小红书"]["ids"], {"note-1"})
            self.assertEqual(signals["B站"]["ids"], {"BV1TEST1234"})
            self.assertIn("https://example.com/bookmark-entry", signals["书签"]["urls"])

    def test_unique_flat_file_path_only_adds_source_suffix_on_collision(self):
        runtime = load_module(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            target_root = Path(tmpdir)
            first = runtime.unique_flat_file_path(target_root, "同名帖子.md", source_name="X", stable_id="123")
            first.write_text("first\n", encoding="utf-8")
            second = runtime.unique_flat_file_path(target_root, "同名帖子.md", source_name="B站", stable_id="BV1AA")

            self.assertEqual(first.name, "同名帖子.md")
            self.assertEqual(second.name, "同名帖子__B站__BV1AA.md")

    def test_send_paths_to_trash_uses_osascript(self):
        runtime = load_module(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "first.md"
            second = Path(tmpdir) / "second.md"
            first.write_text("a\n", encoding="utf-8")
            second.write_text("b\n", encoding="utf-8")

            with mock.patch.object(runtime.platform, "system", return_value="Darwin"), mock.patch.object(
                runtime.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(args=["osascript"], returncode=0, stdout="", stderr=""),
            ) as run_mock:
                runtime.send_paths_to_trash([first, second])

        command = run_mock.call_args[0][0]
        self.assertEqual(command[0], "osascript")

    def test_trash_markdown_notes_by_frontmatter_field_uses_matching_ids(self):
        runtime = load_module(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "X" / "01 Date" / "2026" / "3 月"
            root.mkdir(parents=True, exist_ok=True)
            keep = root / "keep.md"
            remove = root / "remove.md"
            keep.write_text('---\ntweet_id: "100"\n---\n', encoding="utf-8")
            remove.write_text('---\ntweet_id: "200"\n---\n', encoding="utf-8")

            with mock.patch.object(runtime, "send_paths_to_trash") as trash_mock:
                moved = runtime.trash_markdown_notes_by_frontmatter_field(root.parent.parent.parent, field="tweet_id", ids={"200"})

            self.assertEqual(moved, [remove])
            trash_mock.assert_called_once_with([remove])


if __name__ == "__main__":
    unittest.main()
