import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillStructureTests(unittest.TestCase):
    def test_repo_contains_only_router_and_four_canonical_skills(self):
        actual = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())
        self.assertEqual(actual, ["archive-router", "bilibili", "bookmarks", "x-likes", "xhs"])


if __name__ == "__main__":
    unittest.main()
