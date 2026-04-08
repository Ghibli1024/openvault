import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_SKILL_REFS = (
    "$html-bookmarks-to-markdown",
    "$xhs-favorites-to-obsidian",
    "$bilibili-favorites-to-obsidian",
    "$x-to-obsidian",
)

REMOVED_WRAPPER_REFS = (
    "$archive-bookmarks",
    "$archive-xhs",
    "$archive-bilibili",
    "$archive-x-likes",
)


class RouterHandoffTests(unittest.TestCase):
    def test_router_points_directly_to_canonical_skills(self):
        skill_md = ROOT / "skills" / "archive-router" / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        for expected_ref in EXPECTED_SKILL_REFS:
            with self.subTest(skill=expected_ref):
                self.assertIn(expected_ref, content)
        for removed_ref in REMOVED_WRAPPER_REFS:
            with self.subTest(removed=removed_ref):
                self.assertNotIn(removed_ref, content)
        self.assertNotIn("/Users/Totoro/.codex/skills/", content)
        self.assertNotIn("/Users/Totoro/Desktop/", content)


if __name__ == "__main__":
    unittest.main()
