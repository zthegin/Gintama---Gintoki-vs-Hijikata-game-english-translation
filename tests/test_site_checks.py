# Unofficial fan translation tools. No game ownership or endorsement is implied.
# Use your own legally obtained ROM; piracy is discouraged. See RIGHTS.md.
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_site import inspect_site

HTML = """<!doctype html><html><head><title>Unofficial editor</title>
<meta name="description" content="Unofficial fan tools"></head><body id="main">
Unofficial. I do not own Gintama. Use a legally obtained ROM. I do not support piracy.
<a href="rights.html">Rights</a><a href="#main">Top</a>
<script type="module" src="app.mjs"></script></body></html>"""


class SiteCheckTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(folder)
        for name in ("index", "cutscenes", "battle", "graphics", "guide", "install", "rights"):
            (self.root / (name + ".html")).write_text(HTML, encoding="utf-8")
        (self.root / "app.mjs").write_text("import { x } from './codec.mjs';", encoding="utf-8")
        (self.root / "codec.mjs").write_text("export const x = 1;", encoding="utf-8")
        (self.root / "assets").mkdir()
        (self.root / "assets/catalog.json").write_text('{"batches":[]}', encoding="utf-8")

    def index(self, text):
        (self.root / "index.html").write_text(text, encoding="utf-8")

    def test_valid_editor_links_modules_and_notices_pass(self):
        report = inspect_site(self.root)
        self.assertEqual(report["pages"], 7)
        self.assertEqual(report["local_references"], 22)

    def test_missing_page_module_asset_and_anchor_fail(self):
        for old, new in (("rights.html", "missing.html"), ("#main", "#missing"),
                         ("app.mjs", "missing.mjs"), ("rights.html", "../outside.html")):
            self.index(HTML.replace(old, new))
            with self.assertRaises(ValueError):
                inspect_site(self.root)
        self.index(HTML)
        (self.root / "codec.mjs").unlink()
        with self.assertRaisesRegex(ValueError, "codec"):
            inspect_site(self.root)

    def test_every_page_needs_unofficial_metadata_and_visible_notices(self):
        for text in (
            HTML.replace("<title>Unofficial editor", "<title>Editor"),
            HTML.replace('content="Unofficial fan tools"', 'content="Fan tools"'),
            HTML.replace("I do not own Gintama.", ""),
            HTML.replace("I do not support piracy.", ""),
            HTML.replace("legally obtained ROM", "ROM"),
            HTML.replace('id="main"', 'id="main"><span id="main"></span'),
        ):
            self.index(text)
            with self.assertRaises(ValueError):
                inspect_site(self.root)

    def test_script_text_cannot_supply_a_missing_visible_notice(self):
        self.index(HTML.replace("I do not own Gintama.", "") + '<script>"I do not own Gintama"</script>')
        with self.assertRaisesRegex(ValueError, "visible notice"):
            inspect_site(self.root)

    def test_batch_assets_are_required_and_paths_cannot_escape(self):
        catalog = self.root / "assets/catalog.json"
        for value in ("ready/batch_0001.json", "../../index.html", "https://example.com/file.json"):
            catalog.write_text(json.dumps({"batches": [{"file": value}]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                inspect_site(self.root)
        for kind in ("translations", "metadata"):
            folder = self.root / "assets" / kind / "ready"
            folder.mkdir(parents=True)
            (folder / "batch_0001.json").write_text("{}", encoding="utf-8")
        catalog.write_text('{"batches":[{"file":"ready/batch_0001.json"}]}', encoding="utf-8")
        self.assertEqual(inspect_site(self.root)["batches"], 1)

    def test_insecure_and_executable_link_schemes_fail(self):
        for target in ("http://example.com", "javascript:alert(1)", "//example.com", "data:text/plain,hello"):
            self.index(HTML.replace("#main", target))
            with self.assertRaisesRegex(ValueError, "scheme"):
                inspect_site(self.root)
