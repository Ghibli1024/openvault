import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginSurfaceTests(unittest.TestCase):
    def test_only_archive_router_is_ui_visible(self):
        visible = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.glob("skills/*/agents/openai.yaml"))
        self.assertEqual(visible, ["skills/archive-router/agents/openai.yaml"])

    def test_plugin_default_prompt_points_only_to_router(self):
        plugin_json = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        prompts = plugin_json["interface"]["defaultPrompt"]
        self.assertEqual(prompts, ["Use $archive-router as the single visible openvault entry for import, sync, search, and rubbish cleanup workflows."])


if __name__ == "__main__":
    unittest.main()
