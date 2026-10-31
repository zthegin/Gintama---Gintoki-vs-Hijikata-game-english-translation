# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from extract_text import decode_map, extract, get_tables

ROOT = Path(__file__).resolve().parents[1]


class ExtractorTests(unittest.TestCase):
    def test_record_separator_and_optional_marker_are_not_text(self):
        data = b"scr\x1a" + bytes(12)
        data += struct.pack("<4H", 1, 0xFF71, 0, 0x5353)
        data += struct.pack("<3H", 2, 0xFF71, 0)
        records, tail, _ = extract(data)
        self.assertEqual([r["offset"] for r in records], [16, 24])
        self.assertEqual([r["words"] for r in records], [[1, 0xFF71], [2, 0xFF71]])
        self.assertEqual(tail, b"")
        with self.assertRaises(ValueError):
            extract(data[:-2])

    def test_context_inference_cannot_override_bitmap_evidence(self):
        tables = {"names": [{"name": {"text": "X", "raw_words": [1, 0]}}]}
        guessed = {
            "origin_batch": "v" + str(100) + "_ladies4_context",
            "japanese_recovered": "Y",
            "_verified_source_words": [1, 0xFF71],
        }
        mapping, _, conflicts, _ = decode_map(tables, [guessed])
        self.assertEqual(mapping, {1: "X"})
        self.assertEqual(conflicts, [])
        verified = dict(guessed, origin_batch="bitmap_transcription")
        mapping, _, conflicts, _ = decode_map(tables, [verified])
        self.assertEqual(mapping, {})
        self.assertEqual(len(conflicts), 1)

    def test_renamed_cli_writes_private_export_without_changing_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            msb = base / "sample.msb"
            source = b"scr\x1a" + bytes(12) + struct.pack("<3H", 1, 0xFF71, 0)
            msb.write_bytes(source)
            tables = base / "source_tables.zip"
            with zipfile.ZipFile(tables, "w") as archive:
                archive.writestr(
                    "tables/source_name_tables.json",
                    json.dumps(
                        {"names": [{"name": {"text": "X", "raw_words": [1, 0]}}]}
                    ),
                )
                archive.writestr("tables/glossary.json", '{"version": 1}')
            self.assertEqual(get_tables(tables)[1], {"version": 1})
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "extract_text.py"),
                    "--msb",
                    str(msb),
                    "--tables",
                    str(tables),
                    "--out",
                    str(base / "output"),
                    "--no-zip",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            records = json.loads(
                (base / "output/all_records.json").read_text(encoding="utf-8")
            )
            self.assertEqual(records["records"][0]["japanese"], "X")
            self.assertTrue((base / "output/glossary.json").is_file())
            self.assertEqual(msb.read_bytes(), source)

    def test_existing_exports_are_not_overwritten_or_mixed_into_a_new_export(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            msb = base / "sample.msb"
            source = b"scr\x1a" + bytes(12) + struct.pack("<3H", 1, 0xFF71, 0)
            msb.write_bytes(source)
            tables = base / "source_name_tables.json"
            tables.write_text(
                json.dumps({"names": [{"name": {"text": "X", "raw_words": [1, 0]}}]})
            )
            (base / "glossary.json").write_text('{"version": 1}')
            command = [
                sys.executable, "-B", str(ROOT / "extract_text.py"),
                "--msb", str(msb), "--tables", str(tables),
            ]

            previous = base / "previous-export"
            previous.mkdir()
            stale = previous / "batch_0099.json"
            stale.write_text('{"english": "previous translation"}')
            existing_zip = base / "fresh-export.zip"
            existing_zip.write_bytes(b"keep this archive")
            for output, error in [
                (previous, "output already exists"),
                (base / "fresh-export", "ZIP already exists"),
            ]:
                with self.subTest(output=output.name):
                    result = subprocess.run(
                        command + ["--out", str(output)],
                        cwd=ROOT, capture_output=True, text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(error, result.stderr)
            self.assertEqual(stale.read_text(), '{"english": "previous translation"}')
            self.assertEqual(list(previous.iterdir()), [stale])
            self.assertEqual(existing_zip.read_bytes(), b"keep this archive")
            self.assertFalse((base / "fresh-export").exists())
            self.assertFalse((base / "previous-export.zip").exists())
            self.assertEqual(msb.read_bytes(), source)

            result = subprocess.run(
                command + ["--out", str(base / "new-export")],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(base / "new-export.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertNotIn(stale.name, archive.namelist())
                self.assertIn(
                    "ready_to_translate_batches/batch_0001.json", archive.namelist()
                )


if __name__ == "__main__":
    unittest.main()
