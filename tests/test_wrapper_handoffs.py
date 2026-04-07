import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_TARGETS = {
    "archive-bookmarks": "../bookmarks/SKILL.md",
    "archive-xhs": "../xhs/SKILL.md",
    "archive-bilibili": "../bilibili/SKILL.md",
    "archive-x-likes": "../x-likes/SKILL.md",
}


class WrapperHandoffTests(unittest.TestCase):
    def test_wrappers_use_in_repo_backend_paths(self):
        for wrapper_name, expected_target in EXPECTED_TARGETS.items():
            with self.subTest(wrapper=wrapper_name):
                skill_md = ROOT / "skills" / wrapper_name / "SKILL.md"
                content = skill_md.read_text(encoding="utf-8")
                self.assertIn(expected_target, content)
                self.assertNotIn("/Users/Totoro/.codex/skills/", content)
                self.assertNotIn("/Users/Totoro/Desktop/", content)


if __name__ == "__main__":
    unittest.main()
