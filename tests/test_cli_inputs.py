# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import image_workflow as images
import local_view
import verify


class PrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.programs = {"git": "/test/git", "node": "/test/node"}
        self.which = self.enterContext(
            patch.object(verify.shutil, "which", side_effect=self.programs.get)
        )
        self.version = self.enterContext(
            patch.object(
                verify.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "v22.12.0\n", ""),
            )
        )
        self.find_spec = self.enterContext(
            patch.object(verify.importlib.util, "find_spec", return_value=object())
        )

    def test_git_is_required_even_when_python_and_node_are_installed(self):
        self.programs["git"] = None
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "checks"
            with self.assertRaisesRegex(ValueError, "Install Git, reopen"):
                verify.verify(output)
            self.assertFalse(output.exists())
        self.version.assert_not_called()

    def test_missing_node_lists_the_required_version(self):
        self.programs["node"] = None
        with self.assertRaisesRegex(ValueError, r"Install Node.js 22\+"):
            verify.prerequisites()
        self.version.assert_not_called()

    def test_old_broken_or_unrecognised_node_is_rejected(self):
        for code, version in ((0, "v20.19.0"), (0, "unknown"), (1, "v22.12.0")):
            with self.subTest(code=code, version=version):
                self.version.return_value = subprocess.CompletedProcess(
                    [], code, version, ""
                )
                with self.assertRaisesRegex(ValueError, "Node.js 22 or newer"):
                    verify.prerequisites()

    def test_missing_modules_name_the_active_python_and_requirements(self):
        self.find_spec.side_effect = (
            lambda name: object() if name == "numpy" else None
        )
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "checks"
            with self.assertRaisesRegex(ValueError, "Missing Pillow, SciPy") as raised:
                verify.verify(output)
            self.assertFalse(output.exists())
        message = str(raised.exception)
        self.assertIn(f'"{sys.executable}" -m pip install', message)
        self.assertIn(str(verify.ROOT / "requirements.txt"), message)

    def test_supported_node_returns_its_resolved_executable(self):
        for version in ("v22.12.0", "v24.1.0"):
            with self.subTest(version=version):
                self.version.return_value.stdout = version
                self.assertEqual(verify.prerequisites(), "/test/node")
        self.version.assert_called_with(
            ["/test/node", "--version"], capture_output=True, text=True, timeout=10
        )


class ROMInputTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def test_missing_rom_points_to_the_requested_file(self):
        path = self.root / "my original.nds"
        with self.assertRaisesRegex(ValueError, "ROM file not found") as raised:
            images.read_rom(path)
        self.assertIn(str(path), str(raised.exception))
        self.assertIn("quotes", str(raised.exception))

    def test_folder_is_distinguished_from_missing_file(self):
        with self.assertRaisesRegex(ValueError, "not a file.*extracted .nds"):
            images.read_rom(self.root)

    def test_archive_prompts_extraction_instead_of_a_rom_hash_error(self):
        path = self.root / "my original.ZIP"
        path.write_bytes(b"PK archive")
        with self.assertRaisesRegex(ValueError, "Extract the archive first"):
            images.read_rom(path)
        self.assertEqual(path.read_bytes(), b"PK archive")

    def test_empty_and_oversized_roms_remain_rejected(self):
        path = self.root / "original.nds"
        path.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "ROM file is empty"):
            images.read_rom(path)
        path.write_bytes(b"12345")
        with patch.object(images, "MAX_ROM", 4):
            with self.assertRaisesRegex(ValueError, "size limit"):
                images.read_rom(path)

    def test_regular_input_bytes_are_preserved(self):
        path = self.root / "original.nds"
        path.write_bytes(b"unchanged input")
        self.assertEqual(images.read_rom(path), b"unchanged input")
        self.assertEqual(path.read_bytes(), b"unchanged input")


class PrivatePreviewTests(unittest.TestCase):
    def test_preview_cli_cannot_replace_its_inputs_or_an_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            extraction = root / "extraction.zip"
            batch = root / "batch.json"
            record = {
                "id": "sample", "source_words_sha256": "a" * 64,
                "japanese": "source text", "decode_status": "mapped",
            }
            with zipfile.ZipFile(extraction, "x") as archive:
                archive.writestr("all_records.json", json.dumps({"records": [record]}))
            batch.write_text(json.dumps({"records": [{
                "id": "sample", "source_words_sha256": "a" * 64,
                "english": "English text", "translator_note": None,
            }]}))
            existing = root / "existing.html"
            existing.write_text("keep this file")
            before = {path: path.read_bytes() for path in (extraction, batch, existing)}
            script = Path(local_view.__file__)
            command = [sys.executable, "-B", str(script),
                       "--extraction", str(extraction), "--batch", str(batch)]
            for output in (extraction, batch, existing):
                with self.subTest(output=output.name):
                    result = subprocess.run(
                        command + ["--out", str(output)], capture_output=True, text=True
                    )
                    self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            output = root / "preview.html"
            result = subprocess.run(
                command + ["--out", str(output)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("English text", output.read_text(encoding="utf-8"))

    def test_preview_formats_preserve_existing_outputs_and_escape_html(self):
        rows = [{"id": "sample", "japanese": "<script>bad</script>",
                 "english": "English text", "translator_note": "", "decode_status": "mapped"}]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for fmt in ("csv", "md", "html"):
                with self.subTest(format=fmt):
                    output = root / ("preview." + fmt)
                    local_view.save(rows, fmt, output)
                    before = output.read_bytes()
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        local_view.save(rows, fmt, output)
                    self.assertEqual(output.read_bytes(), before)
            html = (root / "preview.html").read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;bad&lt;/script&gt;", html)
            self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
