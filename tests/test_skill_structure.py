import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillStructureTests(unittest.TestCase):
    def test_repo_exposes_only_root_skill(self):
        self.assertTrue((ROOT / "SKILL.md").exists())
        nested_skills = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.glob("**/SKILL.md") if path != ROOT / "SKILL.md")
        self.assertEqual(nested_skills, [])

    def test_sources_hold_the_four_canonical_workflows(self):
        actual = sorted(path.name for path in (ROOT / "sources").iterdir() if path.is_dir())
        self.assertEqual(actual, ["bilibili", "bookmarks", "x-likes", "xhs"])
        for source in actual:
            with self.subTest(source=source):
                self.assertTrue((ROOT / "sources" / source / "WORKFLOW.md").exists())

    def test_root_agent_metadata_exists(self):
        self.assertTrue((ROOT / "agents" / "openai.yaml").exists())


if __name__ == "__main__":
    unittest.main()
