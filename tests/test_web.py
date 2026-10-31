# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_web import ROOT, SOURCE_REPOSITORY, build


class WebsiteTests(unittest.TestCase):
    def test_static_build_and_pair_integrity(self):
        with tempfile.TemporaryDirectory(prefix="gintama-site-") as temp:
            site = Path(temp) / "site"
            with patch.dict(
                os.environ, {"GITHUB_REPOSITORY": "zthegin/zthegin.github.io"}
            ):
                report = build(site, repository=SOURCE_REPOSITORY)
            self.assertEqual(build(site, repository=SOURCE_REPOSITORY), report)
            full_title = (
                "Gintama: Gintoki vs. Hijikata!? "
                "Kabukichou Gintama Dai Soudatsusen!!"
            )
            for page in (
                "index.html", "graphics.html", "cutscenes.html", "battle.html", "guide.html", "install.html", "rights.html"
            ):
                html = (site / page).read_text(encoding="utf-8")
                visible = " ".join(html.split())
                with self.subTest(page=page):
                    self.assertIn(full_title, html)
                    self.assertIn("Nintendo DS English translation project", visible)
                    self.assertIn("I do not own Gintama or any original game content.", visible)
                    self.assertIn("I do not support piracy.", visible)
                    self.assertIn("Use only your own legally obtained ROM", visible)
                    self.assertIn(
                        "do not share game files or unauthorized download links.", visible
                    )
                    self.assertIn("your authority to act", visible)
                    self.assertIn(
                        "For a verified request, I will remove or disable the affected material I control and stop the related work.",
                        visible,
                    )
                    self.assertNotIn("remove this project and its published files", visible)
                    self.assertIn('href="rights.html"', html)
            rights_html = (site / "rights.html").read_text(encoding="utf-8")
            self.assertIn("Bundled English dialogue adapts", rights_html)
            self.assertNotIn("gameplay screenshot", rights_html)
            field_dialogue = json.loads(
                (site / "assets/translations/ready/field_dialogue.json").read_text(encoding="utf-8")
            )
            self.assertEqual(field_dialogue, json.loads(
                (ROOT / "translations/ready/field_dialogue.json").read_text(encoding="utf-8")
            ))
            metadata = json.loads(
                (site / "assets/metadata/ready/field_dialogue.json").read_text(encoding="utf-8")
            )
            colored = next(row for row in metadata if row["id"] == "msb_00003E44")
            self.assertEqual(colored["control_sequence"], [0xFF82, 0xFF84, 0xFF72, 0xFF72])
            self.assertFalse((site / "screenshots/gameplay.png").exists())
            sources = {
                path.relative_to(ROOT / "translations").as_posix(): json.loads(
                    path.read_text(encoding="utf-8")
                )
                for path in (ROOT / "translations").rglob("*.json")
                if path.parent.name != "graphics"
            }
            self.assertTrue(sources)
            self.assertEqual(report["batches"], len(sources))
            self.assertEqual(
                report["records"], sum(len(batch["records"]) for batch in sources.values())
            )
            catalog = json.loads((site / "assets/catalog.json").read_text())
            self.assertEqual(catalog["repository"], SOURCE_REPOSITORY)
            self.assertEqual(len(catalog["batches"]), len(sources))
            self.assertEqual({batch["file"] for batch in catalog["batches"]}, set(sources))
            graphics = json.loads((site / "assets/graphics/catalog.json").read_text())
            self.assertEqual(len(graphics["entries"]), 193)
            self.assertEqual(
                (site / "assets/opening_scene.json").read_bytes(),
                (ROOT / "reference/opening_scene.json").read_bytes(),
            )
            self.assertEqual((site / "assets/battle.json").read_bytes(),
                             (ROOT / "reference/battle.json").read_bytes())
            self.assertTrue((site / "battle-codec.mjs").is_file())
            self.assertTrue((site / "battle.mjs").is_file())
            self.assertTrue((site / "cutscene-codec.mjs").is_file())
            self.assertTrue((site / "cutscenes.mjs").is_file())
            self.assertTrue((site / "graphics.html").is_file())
            self.assertTrue((site / "rights.html").is_file())
            self.assertTrue((site / "install.html").is_file())
            for name in [
                "image-label.png",
                "two-line-label.png",
                "dialogue-editor.png",
            ]:
                self.assertEqual(
                    (site / "screenshots" / name).read_bytes(),
                    (ROOT / "docs/screenshots" / name).read_bytes(),
                )
            self.assertIn(
                "legally obtained", (site / "install.html").read_text(encoding="utf-8")
            )
            glossary = json.loads((site / "assets/glossary.json").read_text())
            self.assertFalse(
                any(
                    "original_description_Japanese" in row
                    for row in glossary["entries"]
                )
            )
            for batch in catalog["batches"]:
                public = json.loads(
                    (site / "assets/translations" / batch["file"]).read_text()
                )
                metadata = json.loads(
                    (site / "assets/metadata" / batch["file"]).read_text()
                )
                self.assertEqual(public, sources[batch["file"]])
                self.assertEqual(batch["count"], len(public["records"]))
                self.assertEqual(
                    [row["id"] for row in public["records"]],
                    [row["id"] for row in metadata],
                )
                self.assertFalse(
                    any(
                        "japanese" in row or "raw_words_hex" in row
                        for row in public["records"]
                    )
                )
                self.assertFalse(
                    any("japanese" in row or "raw_words_hex" in row for row in metadata)
                )
            self.assertFalse(
                any(
                    p.suffix.lower() in {".nds", ".cdb", ".msb", ".bin", ".bps"}
                    for p in site.rglob("*")
                    if p.is_file()
                )
            )

    def test_no_unowned_directory_deletion(self):
        with tempfile.TemporaryDirectory(prefix="gintama-not-site-") as temp:
            with self.assertRaises(ValueError):
                build(Path(temp))

    def test_marked_site_cannot_delete_git_or_custom_content(self):
        for extra in (".git/config", "notes.txt", "assets/custom.txt", "empty-folder"):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "site"
                output.mkdir()
                (output / ".gintama-site-build").write_text(
                    "Static translation editor build\n", encoding="utf-8"
                )
                (output / "index.html").write_text("Previous build", encoding="utf-8")
                protected = output / extra
                if extra == "empty-folder":
                    protected.mkdir()
                else:
                    protected.parent.mkdir(parents=True, exist_ok=True)
                    protected.write_text("Keep this", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "unexpected site content"):
                    build(output)
                self.assertEqual((output / "index.html").read_text(), "Previous build")
                self.assertTrue(protected.exists())
                if protected.is_file():
                    self.assertEqual(protected.read_text(), "Keep this")

    def test_marked_site_rejects_symlink_even_at_generated_path(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "site"
            output.mkdir()
            (output / ".gintama-site-build").write_text(
                "Static translation editor build\n", encoding="utf-8"
            )
            linked = output / "index.html"
            linked.write_text("Keep this", encoding="utf-8")
            original = Path.is_symlink
            with (
                patch.object(
                    Path, "is_symlink", lambda path: path == linked or original(path)
                ),
                self.assertRaisesRegex(ValueError, "unexpected site content"),
            ):
                build(output)
            self.assertEqual(linked.read_text(), "Keep this")

    def test_no_inside_repo_build(self):
        with self.assertRaises(ValueError):
            build(ROOT / "site")

    def test_no_ancestor_directory_deletion(self):
        with self.assertRaises(ValueError):
            build(ROOT.parent)

    def test_invalid_repository_link_is_refused_without_writing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "site"
            for repository in [
                "https://github.com/example/project",
                "owner/name\nextra",
                "../name",
            ]:
                with self.assertRaises(ValueError):
                    build(output, repository=repository)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
