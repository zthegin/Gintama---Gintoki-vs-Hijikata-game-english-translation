# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_approved import export
from package_source import package
from sync_csv import render
from verify import verify


class PackagingTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory) / "repo"
        root.mkdir()
        (root / "README.md").write_text(
            "Independent tools and blank templates.\n", encoding="utf-8"
        )
        return root

    def test_archive_metadata_and_bytes_do_not_depend_on_source_mtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            package(root, first)
            os.utime(root / "README.md", (1700000000, 1700000000))
            package(root, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.comment, b"")
                for info in archive.infolist():
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                    self.assertEqual(info.extra, b"")
                    self.assertEqual(info.comment, b"")
                    self.assertFalse(info.filename.startswith("/"))

    def test_invalid_source_never_leaves_an_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            (root / "game.nds").write_bytes(b"synthetic fixture")
            out = Path(directory) / "source.zip"
            with self.assertRaises(ValueError):
                package(root, out)
            self.assertFalse(out.exists())

    def test_failed_archive_verification_cleans_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            out = Path(directory) / "source.zip"
            with patch(
                "package_source.zipfile.ZipFile.testzip", return_value="bad-member"
            ):
                with self.assertRaises(ValueError):
                    package(root, out)
            self.assertFalse(out.exists())
            self.assertEqual(list(Path(directory).glob(".source-*.zip")), [])

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            out = Path(directory) / "source.zip"
            out.write_bytes(b"keep")
            with self.assertRaises(ValueError):
                package(root, out)
            self.assertEqual(out.read_bytes(), b"keep")

    def export_fixture(
        self, directory, batch_id="batch_0001", group="ready", filename=None
    ):
        root = self.fixture(directory)
        record = {
            "id": "msb_00000100",
            "source_words_sha256": "a" * 64,
            "english": None,
            "translator_note": None,
        }
        data = {
            "format": "gintama-community-translation-v1",
            "batch_id": batch_id,
            "records": [record],
        }
        filename = filename or batch_id
        for name in ("reference", "translations/" + group, "csv/" + group):
            (root / name).mkdir(parents=True)
        (root / "reference/record_index.json").write_text(
            json.dumps({"records": [{**record, "page_breaks": 0}]}), encoding="utf-8"
        )
        (root / "translations" / group / (filename + ".json")).write_text(
            json.dumps(data), encoding="utf-8"
        )
        (root / "csv" / group / (filename + ".csv")).write_text(
            render(data), encoding="utf-8"
        )
        return root

    def test_graphics_batch_cannot_escape_or_collide_with_export_files(self):
        for identifier in ("../escaped", "approved_translations"):
            with (
                self.subTest(identifier=identifier),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = self.export_fixture(
                    directory,
                    identifier,
                    "graphics",
                    "gin_tama_names" if identifier.startswith("../") else identifier,
                )
                output = Path(directory) / "export"
                escaped = Path(directory) / "escaped.json"
                escaped.write_text("Keep this", encoding="utf-8")
                with self.assertRaises(ValueError):
                    export(root, output)
                self.assertFalse(output.exists())
                self.assertEqual(escaped.read_text(), "Keep this")

    def test_export_cli_checks_the_unresolved_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            linked = Path(directory) / "link"
            output = linked / ".." / "export"
            original = Path.is_symlink
            tool = Path(__file__).resolve().parents[1] / "tools/export_approved.py"
            with (
                patch.object(
                    Path, "is_symlink", lambda path: path == linked or original(path)
                ),
                patch.object(
                    sys, "argv", [str(tool), "--repo", str(root), "--out", str(output)]
                ),
                self.assertRaisesRegex(ValueError, "Symlink export destination"),
            ):
                runpy.run_path(str(tool), run_name="__main__")
            self.assertFalse((Path(directory) / "export").exists())

    def test_exported_builder_starts_without_source_checkout_dependencies(self):
        source = Path(__file__).resolve().parents[1]
        expected = {
            "approved_translations.json", "approved_translations.csv",
            "gin_tama_names.json", "graphics/catalog.json",
            "graphics/pixel_font.json", "graphics/lowercase_font.json",
            "graphics/extended_font.json", "tools/english_font.py",
            "tools/dialogue_writer.py", "tools/cutscene_writer.py",
            "tools/battle_writer.py", "reference/battle.json",
            "reference/opening_scene.json", "tools/text_policy.py",
            "tools/field_markup.py", "reference/record_index.json",
            "graphics/ui_recipes.json", "tools/build_ui.py", "tools/ui_tiles.py",
            "tools/ui_render.py", "tools/rom_patch.py", "requirements.txt",
            "tools/image_workflow.py", "tools/optimal_lz10.py",
            "translations/graphics/gin_tama_names.json",
            "csv/graphics/gin_tama_names.csv", "docs/IMAGE_WORKFLOW.md",
            "docs/APPLY_PATCH.md", "RIGHTS.md", "LICENSE",
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "approved"
            export(source, output)
            self.assertEqual(
                {path.relative_to(output).as_posix()
                 for path in output.rglob("*") if path.is_file()},
                expected,
            )
            environment = {
                name: value for name, value in os.environ.items()
                if name.upper() not in {"PYTHONPATH", "PYTHONHOME"}
            }
            command = [sys.executable, "-E", "-B",
                       str(output / "tools/build_ui.py"), "--help"]

            def launch():
                return subprocess.run(
                    command, cwd=output, env=environment, capture_output=True,
                    text=True, timeout=30,
                )

            result = launch()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage:", result.stdout.lower())
            # A negative control proves the source tree cannot mask an omitted helper.
            (output / "tools/field_markup.py").unlink()
            result = launch()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("field_markup", result.stderr)

    def test_export_refuses_directory_created_after_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.export_fixture(directory)
            output = Path(directory) / "export"
            original = Path.mkdir

            def competing_directory(path, *args, **kwargs):
                if path == output:
                    original(path)
                    (path / "approved_translations.json").write_text(
                        "Keep this", encoding="utf-8"
                    )
                return original(path, *args, **kwargs)

            with (
                patch.object(Path, "mkdir", competing_directory),
                self.assertRaises(FileExistsError),
            ):
                export(root, output)
            self.assertEqual(
                (output / "approved_translations.json").read_text(), "Keep this"
            )

    def test_verifier_rejects_existing_output_before_running_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("verify.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    verify(Path(directory))
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
