import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SYNC_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_x_likes.py"


class SyncXLikesSearchFolderTests(unittest.TestCase):
    def _load_module(self):
        spec = importlib.util.spec_from_file_location("sync_xlikes_search_test_module", SYNC_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_replace_target_preserves_existing_search_folder(self):
        sync = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            resources_root = Path(tmp) / "04-Resources"
            root = resources_root / "X"
            stage = Path(tmp) / "stage"
            for folder in ["01 Date", "02 Author", "03 Domain"]:
                (stage / folder).mkdir(parents=True)
                (stage / folder / "Index.md").write_text("# index\n", encoding="utf-8")
            (stage / "Dashboard.md").write_text("# dash\n", encoding="utf-8")

            search_dir = resources_root / "搜索"
            search_dir.mkdir(parents=True)
            (search_dir / "query-result.md").write_text("keep me\n", encoding="utf-8")
            rubbish_dir = resources_root / "废弃"
            rubbish_dir.mkdir(parents=True)
            (rubbish_dir / "trash.md").write_text("keep me\n", encoding="utf-8")

            sync.replace_target(root, stage)

            self.assertTrue((resources_root / "搜索").exists())
            self.assertTrue((resources_root / "搜索" / "query-result.md").exists())
            self.assertTrue((resources_root / "废弃").exists())
            self.assertTrue((resources_root / "废弃" / "trash.md").exists())

    def test_replace_target_creates_search_folder_when_missing(self):
        sync = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            resources_root = Path(tmp) / "04-Resources"
            root = resources_root / "X"
            root.mkdir(parents=True)
            stage = Path(tmp) / "stage"
            for folder in ["01 Date", "02 Author", "03 Domain"]:
                (stage / folder).mkdir(parents=True)
                (stage / folder / "Index.md").write_text("# index\n", encoding="utf-8")
            (stage / "Dashboard.md").write_text("# dash\n", encoding="utf-8")

            sync.replace_target(root, stage)

            self.assertTrue((resources_root / "搜索").exists())
            self.assertTrue((resources_root / "废弃").exists())


if __name__ == "__main__":
    unittest.main()
