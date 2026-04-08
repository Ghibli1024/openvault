import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SYNC_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_x_likes.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sync_xlikes_global_runtime_test", SYNC_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SyncXLikesGlobalRuntimeTests(unittest.TestCase):
    def test_collect_rubbish_tweet_ids_reads_global_rubbish_root(self):
        sync = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            note = resources_root / "X" / "01 Date" / "2026" / "3 月" / "Hello.md"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(
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
            rubbish = resources_root / "废弃" / "cleanup.md"
            rubbish.parent.mkdir(parents=True, exist_ok=True)
            rubbish.write_text("- [[X/01 Date/2026/3 月/Hello|Hello]]\n", encoding="utf-8")

            ids = sync.collect_rubbish_tweet_ids(resources_root)

            self.assertEqual(ids, {"123"})

    def test_replace_target_no_longer_creates_local_search_or_rubbish_roots(self):
        sync = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            output_root = resources_root / "X"
            stage_root = Path(tmpdir) / "stage"

            for folder in ["01 Date", "02 Author", "03 Domain"]:
                (stage_root / folder).mkdir(parents=True, exist_ok=True)
                (stage_root / folder / "Index.md").write_text("# index\n", encoding="utf-8")
            (stage_root / "Dashboard.md").write_text("# dash\n", encoding="utf-8")

            sync.replace_target(output_root, stage_root)

            self.assertTrue((resources_root / "搜索").exists())
            self.assertTrue((resources_root / "废弃").exists())
            self.assertFalse((output_root / "04 Search").exists())
            self.assertFalse((output_root / "05 Rubbish").exists())


if __name__ == "__main__":
    unittest.main()
