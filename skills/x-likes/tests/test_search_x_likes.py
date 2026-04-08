import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search_x_likes.py"


def load_module():
    spec = importlib.util.spec_from_file_location("search_x_likes_runtime", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["search_x_likes_runtime"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_note(path: Path, *, tweet_id: str, title: str, author: str, domain: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                f'tweet_id: "{tweet_id}"',
                f'title: "{title}"',
                f'author_handle: "{author}"',
                f'author_name: "{author}"',
                'created_at: "2026-03-20"',
                f'source: "https://x.com/{author}/status/{tweet_id}"',
                f'domain: "{domain}"',
                "---",
                "",
                f"# {title}",
                "",
                content,
            ]
        ),
        encoding="utf-8",
    )


class SearchXLikesTests(unittest.TestCase):
    def test_search_results_are_written_into_04_search(self):
        module = load_module()
        load_records = module.load_records
        match_records = module.match_records
        write_search_note = module.write_search_note

        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            root = resources_root / "X"
            _write_note(
                root / "01 Date" / "2026" / "3 月" / "Telegram-CLI.md",
                tweet_id="1",
                title="Telegram-CLI",
                author="alice",
                domain="技术与开发/编程与开源/主题杂项/代码技术",
                content="最近我一直在用的工具：Telegram-CLI！",
            )
            _write_note(
                root / "01 Date" / "2026" / "3 月" / "bilibili-cli.md",
                tweet_id="2",
                title="bilibili-cli",
                author="bob",
                domain="AI/编程助手/主题杂项",
                content="放大招了！实现了个一个 bilibili-cli！",
            )

            records = load_records(root)
            matched = match_records(records, "telegram cli")
            output = write_search_note(root, "telegram cli", matched, note_title="Telegram CLI 检索")

            self.assertEqual(len(matched), 1)
            self.assertTrue(output.exists())
            self.assertEqual(output.parent.resolve(), (resources_root / "搜索").resolve())
            content = output.read_text(encoding="utf-8")
            self.assertIn("Telegram CLI 检索", content)
            self.assertIn("Telegram-CLI", content)
            self.assertNotIn("bilibili-cli", content)


if __name__ == "__main__":
    unittest.main()
