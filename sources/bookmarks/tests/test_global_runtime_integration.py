import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_bookmark_html.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sync_bookmark_global_runtime_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SyncBookmarkGlobalRuntimeTests(unittest.TestCase):
    def test_global_rubbish_urls_are_removed_from_rendered_archive(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            resources_root = Path(tmpdir) / "04-Resources"
            html_path = Path(tmpdir) / "bookmarks.html"
            html_path.write_text(
                textwrap.dedent(
                    """\
                    <!DOCTYPE NETSCAPE-Bookmark-file-1>
                    <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
                    <TITLE>Bookmarks</TITLE>
                    <H1>Bookmarks</H1>
                    <DL><p>
                      <DT><H3>Root</H3>
                      <DL><p>
                        <DT><A HREF="https://keep.example.com">Keep</A>
                        <DT><A HREF="https://blocked.example.com">Blocked</A>
                      </DL><p>
                    </DL><p>
                    """
                ),
                encoding="utf-8",
            )
            rubbish_root = resources_root / "废弃"
            rubbish_root.mkdir(parents=True, exist_ok=True)
            (rubbish_root / "blocked.md").write_text("- https://blocked.example.com\n", encoding="utf-8")

            argv = [
                "sync_bookmark_html.py",
                "--input-html",
                str(html_path),
                "--target-root",
                str(resources_root),
                "--container-name",
                "书签",
                "--archive-profile",
                "categories-only",
                "--layout",
                "compact",
                "--mode",
                "merge",
                "--taxonomy-bootstrap-source",
                "internal-default",
            ]
            with mock.patch.object(sys, "argv", argv):
                module.main()

            archive_root = resources_root / "书签"
            rendered = "\n".join(path.read_text(encoding="utf-8") for path in archive_root.rglob("*.md"))
            self.assertIn("keep.example.com", rendered)
            self.assertNotIn("blocked.example.com", rendered)


if __name__ == "__main__":
    unittest.main()
