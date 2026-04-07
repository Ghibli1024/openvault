import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "detect_source.py"


def load_module(testcase: unittest.TestCase):
    if not SCRIPT_PATH.exists():
        testcase.fail(f"missing routing helper: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("detect_source_runtime", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        testcase.fail(f"unable to load routing helper from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DetectSourceTests(unittest.TestCase):
    def test_detects_bilibili_from_text(self):
        module = load_module(self)
        result = module.detect_source("把 B 站收藏导入 Obsidian")
        self.assertEqual(result["source"], "bilibili")
        self.assertFalse(result["ambiguous"])

    def test_detects_xiaohongshu_from_text(self):
        module = load_module(self)
        result = module.detect_source("导入小红书收藏")
        self.assertEqual(result["source"], "xhs")
        self.assertFalse(result["ambiguous"])

    def test_detects_bookmarks_from_html_filename(self):
        module = load_module(self)
        result = module.detect_source("", "/tmp/bookmarks.html")
        self.assertEqual(result["source"], "bookmarks")
        self.assertFalse(result["ambiguous"])

    def test_detects_x_likes_from_json_filename(self):
        module = load_module(self)
        result = module.detect_source("", "/tmp/x-likes-export.json")
        self.assertEqual(result["source"], "x-likes")
        self.assertFalse(result["ambiguous"])

    def test_marks_generic_request_as_ambiguous(self):
        module = load_module(self)
        result = module.detect_source("整理资源到 Obsidian")
        self.assertEqual(result["source"], "ambiguous")
        self.assertTrue(result["ambiguous"])


if __name__ == "__main__":
    unittest.main()
