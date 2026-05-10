import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_WORKFLOW_REFS = (
    "sources/bookmarks/WORKFLOW.md",
    "sources/xhs/WORKFLOW.md",
    "sources/bilibili/WORKFLOW.md",
    "sources/x-likes/WORKFLOW.md",
)

REMOVED_PLUGIN_REFS = (
    "$html-bookmarks-to-markdown",
    "$xhs-favorites-to-obsidian",
    "$bilibili-favorites-to-obsidian",
    "$x-to-obsidian",
    "$archive-bookmarks",
    "$archive-xhs",
    "$archive-bilibili",
    "$archive-x-likes",
)


class RouterHandoffTests(unittest.TestCase):
    def test_root_skill_points_to_source_workflows(self):
        skill_md = ROOT / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        for expected_ref in EXPECTED_WORKFLOW_REFS:
            with self.subTest(workflow=expected_ref):
                self.assertIn(expected_ref, content)
        for removed_ref in REMOVED_PLUGIN_REFS:
            with self.subTest(removed=removed_ref):
                self.assertNotIn(removed_ref, content)
        self.assertNotIn("/Users/Totoro/.codex/skills/", content)
        self.assertNotIn("/Users/Totoro/Desktop/", content)
        self.assertNotIn("archive-router", content)


if __name__ == "__main__":
    unittest.main()
