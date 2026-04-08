import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search_resources.py"


def load_module(testcase: unittest.TestCase):
    if not SCRIPT_PATH.exists():
        testcase.fail(f"missing search helper: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("search_resources_test_module", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        testcase.fail(f"unable to load search helper from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_note(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


class GlobalSearchRuntimeTests(unittest.TestCase):
    def test_search_all_sources_includes_global_rubbish(self):
        module = load_module(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            _write_note(
                resources_root / "X" / "01 Date" / "2026" / "3 月" / "Agent 工具.md",
                [
                    "---",
                    'tweet_id: "123"',
                    'title: "Agent 工具"',
                    'source: "https://x.com/alice/status/123"',
                    "---",
                    "",
                    "跨来源 agent tool 搜索",
                ],
            )
            _write_note(
                resources_root / "废弃" / "已废弃教程.md",
                [
                    "---",
                    'platform: "xiaohongshu"',
                    'note_id: "note-1"',
                    'title: "已废弃教程"',
                    "---",
                    "",
                    "这条 agent 记录也能被搜索到。",
                ],
            )

            matched = module.search_resources(resources_root, query="agent")

            self.assertEqual(len(matched), 2)
            self.assertEqual({item.source_name for item in matched}, {"X", "废弃"})

    def test_search_single_source_limits_results_and_writes_into_global_search_root(self):
        module = load_module(self)
        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            _write_note(
                resources_root / "X" / "01 Date" / "2026" / "3 月" / "Telegram CLI.md",
                [
                    "---",
                    'tweet_id: "111"',
                    'title: "Telegram CLI"',
                    'source: "https://x.com/alice/status/111"',
                    "---",
                    "",
                    "telegram cli workflow",
                ],
            )
            _write_note(
                resources_root / "B站" / "01 日期" / "2026" / "3 月" / "B 站教程.md",
                [
                    "---",
                    'bvid: "BV1TEST1234"',
                    'title: "B 站教程"',
                    'video_url: "https://www.bilibili.com/video/BV1TEST1234"',
                    "---",
                    "",
                    "bilibili tutorial",
                ],
            )

            matched = module.search_resources(resources_root, query="telegram cli", source_name="X")
            output = module.write_search_note(resources_root, query="telegram cli", matched=matched, source_name="X")

            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0].source_name, "X")
            self.assertTrue(output.exists())
            self.assertEqual(output.parent.resolve(), (resources_root / "搜索").resolve())
            content = output.read_text(encoding="utf-8")
            self.assertIn("telegram cli", content.lower())
            self.assertIn("[X]", content)
            self.assertNotIn("B 站教程", content)


if __name__ == "__main__":
    unittest.main()
