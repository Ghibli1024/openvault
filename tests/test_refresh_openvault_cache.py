import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "refresh_openvault_cache.py"


def load_module(testcase: unittest.TestCase):
    if not SCRIPT_PATH.exists():
        testcase.fail(f"missing refresh helper: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("refresh_openvault_cache_runtime", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        testcase.fail(f"unable to load refresh helper from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def write_plugin_files(repo: Path, *, short_description: str, visible_skills: list[str]) -> None:
    plugin_dir = repo / ".codex-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "openvault",
                "version": "0.1.0",
                "skills": "./skills/",
                "interface": {
                    "displayName": "openvault",
                    "shortDescription": short_description,
                    "defaultPrompt": ["Use $archive-router as the single visible entry."],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    skills_root = repo / "skills"
    if skills_root.exists():
        for existing in skills_root.iterdir():
            if existing.is_dir():
                subprocess.run(["rm", "-rf", str(existing)], check=True)
    skills_root.mkdir(parents=True, exist_ok=True)
    for skill_name in visible_skills:
        agent_dir = skills_root / skill_name / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "openai.yaml").write_text(
            textwrap.dedent(
                f"""\
                interface:
                  display_name: "{skill_name}"
                """
            ),
            encoding="utf-8",
        )


class RefreshOpenvaultCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="openvault-refresh-test-")
        self.root = Path(self.temp_dir.name)
        self.remote = self.root / "remote.git"
        self.source = self.root / "source"
        self.cache_root = self.root / ".codex" / "plugins" / "cache"
        self.cache_repo = self.cache_root / "totoro-local" / "openvault" / "local"
        self.config_path = self.root / ".codex" / "config.toml"

        run_git(self.root, "init", "--bare", str(self.remote))
        run_git(self.root, "clone", str(self.remote), str(self.source))
        run_git(self.source, "config", "user.name", "Totoro")
        run_git(self.source, "config", "user.email", "totoro@example.com")

        write_plugin_files(
            self.source,
            short_description="old cache",
            visible_skills=["archive-router", "archive-bilibili", "archive-bookmarks"],
        )
        run_git(self.source, "add", ".")
        run_git(self.source, "commit", "-m", "initial")
        run_git(self.source, "push", "origin", "main")

        self.cache_repo.parent.mkdir(parents=True, exist_ok=True)
        run_git(self.root, "clone", str(self.remote), str(self.cache_repo))
        run_git(self.cache_repo, "config", "user.name", "Totoro")
        run_git(self.cache_repo, "config", "user.email", "totoro@example.com")

        write_plugin_files(
            self.source,
            short_description="single entry",
            visible_skills=["archive-router"],
        )
        run_git(self.source, "add", ".")
        run_git(self.source, "commit", "-m", "shrink skills")
        run_git(self.source, "push", "origin", "main")

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            textwrap.dedent(
                """\
                [plugins."openvault@totoro-local"]
                enabled = true
                """
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_status_detects_outdated_cache_clone(self):
        module = load_module(self)
        status = module.get_refresh_status(
            source_repo=self.source,
            config_path=self.config_path,
            cache_root=self.cache_root,
        )

        self.assertTrue(status["plugin_enabled"])
        self.assertTrue(status["needs_refresh"])
        self.assertNotEqual(status["cache_head"], status["target_head"])
        self.assertEqual(status["visible_skill_count"], 3)

    def test_refresh_updates_cache_clone_and_visible_skill_count(self):
        module = load_module(self)
        result = module.refresh_cache_clone(
            source_repo=self.source,
            config_path=self.config_path,
            cache_root=self.cache_root,
            branch="main",
        )

        self.assertTrue(result["plugin_enabled"])
        self.assertTrue(result["refreshed"])
        self.assertEqual(result["before_head"], result["cache_head_before"])
        self.assertEqual(result["after_head"], result["target_head"])
        self.assertFalse(result["needs_refresh"])
        self.assertEqual(result["visible_skill_count"], 1)
        self.assertEqual(result["visible_skill_entries"], ["skills/archive-router/agents/openai.yaml"])

    def test_refresh_dry_run_keeps_cache_unchanged(self):
        module = load_module(self)
        before = run_git(self.cache_repo, "rev-parse", "HEAD")
        result = module.refresh_cache_clone(
            source_repo=self.source,
            config_path=self.config_path,
            cache_root=self.cache_root,
            branch="main",
            dry_run=True,
        )
        after = run_git(self.cache_repo, "rev-parse", "HEAD")

        self.assertFalse(result["refreshed"])
        self.assertEqual(before, after)
        self.assertTrue(result["needs_refresh"])


if __name__ == "__main__":
    unittest.main()
