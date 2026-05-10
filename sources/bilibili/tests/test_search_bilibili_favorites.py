import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search_bilibili_favorites.py"


def load_module():
    spec = importlib.util.spec_from_file_location("search_bilibili_runtime", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["search_bilibili_runtime"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_note(path: Path, *, record_id: str, bvid: str, title: str, up_name: str, domain: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                f'record_id: "{record_id}"',
                f'bvid: "{bvid}"',
                f'title: "{title}"',
                f'up_name: "{up_name}"',
                'fav_time: "2026-03-20"',
                f'domain_parts: ["{domain}"]',
                f'video_url: "https://www.bilibili.com/video/{bvid}"',
                "---",
                "",
                f"# {title}",
                "",
                content,
            ]
        ),
        encoding="utf-8",
    )


class SearchBilibiliFavoritesTests(unittest.TestCase):
    def test_search_results_are_written_into_global_search_root(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            archive_root = resources_root / "B站"
            _write_note(
                archive_root / "01 日期" / "2026" / "3 月" / "Agent 教程.md",
                record_id="1",
                bvid="BV1TEST1234",
                title="Agent 教程",
                up_name="UP主甲",
                domain="AI",
                content="agent workflow tutorial",
            )
            _write_note(
                archive_root / "01 日期" / "2026" / "3 月" / "普通视频.md",
                record_id="2",
                bvid="BV1TEST5678",
                title="普通视频",
                up_name="UP主乙",
                domain="生活",
                content="other content",
            )

            records = module.load_records(archive_root)
            matched = module.match_records(records, "agent tutorial")
            output = module.write_search_note(archive_root, "agent tutorial", matched, note_title="Agent 教程检索")

            self.assertEqual(len(matched), 1)
            self.assertTrue(output.exists())
            self.assertEqual(output.parent.resolve(), (resources_root / "搜索").resolve())
            content = output.read_text(encoding="utf-8")
            self.assertIn("Agent 教程检索", content)
            self.assertIn("Agent 教程", content)
            self.assertNotIn("普通视频", content)


if __name__ == "__main__":
    unittest.main()
