import importlib.util
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
FILTERS_PATH = SKILL_ROOT / "scripts" / "bilibili_record_filters.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BilibiliRecordFiltersTest(unittest.TestCase):
    def setUp(self):
        self.filters = load_module(FILTERS_PATH, "bilibili_record_filters_test")

    def test_exact_placeholder_title_is_invalid(self):
        media = {"title": "已失效视频", "bvid": ""}

        self.assertTrue(self.filters.is_invalid_bilibili_media(media))
        self.assertEqual(
            self.filters.invalid_bilibili_media_reason(media),
            self.filters.INVALID_TITLE_REASON,
        )

    def test_effectively_exact_placeholder_title_with_wrappers_is_invalid(self):
        media = {"title": "  【 已失效视频 】  "}

        self.assertTrue(self.filters.is_invalid_bilibili_media(media))

    def test_known_invalid_attr_flag_is_invalid(self):
        media = {"title": "原标题可能还在", "attr": 1}

        self.assertTrue(self.filters.is_invalid_bilibili_media(media))
        self.assertEqual(
            self.filters.invalid_bilibili_media_reason(media),
            self.filters.INVALID_ATTR_REASON,
        )

    def test_recordish_dict_can_use_raw_media_signals(self):
        record = {
            "title": "归档标题",
            "raw_media": {"title": "已失效视频"},
        }

        self.assertTrue(self.filters.is_invalid_bilibili_media(record))

    def test_normal_title_or_intro_with_failed_link_language_is_not_invalid(self):
        media = {
            "title": "Claude Code 失效链接排查指南",
            "intro": "这个视频讲的是如何修复失效链接，不是视频本身失效。",
            "bvid": "BV1VALID1234",
            "attr": 0,
        }

        self.assertFalse(self.filters.is_invalid_bilibili_media(media))
        self.assertIsNone(self.filters.invalid_bilibili_media_reason(media))

    def test_filter_valid_media_splits_items_and_preserves_order(self):
        valid_items, invalid_items = self.filters.filter_valid_media(
            [
                {"title": "正常视频 A", "bvid": "BV1A"},
                {"title": "已失效视频"},
                {"title": "正常视频 B", "intro": "讲如何定位失效链接"},
                {"title": "正常视频 C", "attr": 1},
            ]
        )

        self.assertEqual([item["title"] for item in valid_items], ["正常视频 A", "正常视频 B"])
        self.assertEqual([item["title"] for item in invalid_items], ["已失效视频", "正常视频 C"])


if __name__ == "__main__":
    unittest.main()
