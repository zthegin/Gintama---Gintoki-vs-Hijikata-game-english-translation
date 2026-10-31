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
from check_public_tree import check
from pack_patch import package
from rom_patch import (
    _crc,
    _number,
    _read_number,
    _write_new,
    apply,
    create,
    header,
    sha256,
)


class TestBps(unittest.TestCase):
    def test_output_created_during_write_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translated.nds"
            with patch(
                "rom_patch.os.fsync",
                side_effect=lambda _: path.write_bytes(b"other process"),
            ):
                with self.assertRaises(FileExistsError):
                    _write_new(path, b"our build")
            self.assertEqual(path.read_bytes(), b"other process")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_failed_atomic_publish_removes_only_its_reserved_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translated.nds"
            with patch("rom_patch.os.replace", side_effect=OSError("test failure")):
                with self.assertRaises(OSError):
                    _write_new(path, b"our build")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_varint_roundtrip(self):
        for value in (
            0,
            1,
            127,
            128,
            129,
            255,
            256,
            16384,
            1024 * 1024,
            512 * 1024 * 1024,
        ):
            data = _number(value)
            self.assertEqual(_read_number(data, 0, len(data)), (value, len(data)))

    def test_sparse_changes_and_growth(self):
        original = b"SOURCE-PRIVATE-STRING-" + b"a" * 14000 + b"\xff" * 12
        for changed in (
            original[:600] + b"ENGLISH" + original[607:],
            original[:600] + b"EDITED" + original[606:] + b"MORE TEXT",
            original[:-40] + b"!",
        ):
            patch = create(original, changed)
            self.assertEqual(apply(original, patch), changed)
            self.assertLess(len(patch), len(changed) // 10)
            self.assertNotIn(b"SOURCE-PRIVATE-STRING-", patch)
            self.assertEqual(header(patch)["source_size"], len(original))

    def test_bad_source_and_corruption(self):
        source = b"a" * 1000
        target = b"a" * 400 + b"z" * 15 + b"a" * 585
        patch = create(source, target)
        with self.assertRaisesRegex(ValueError, "Wrong source ROM"):
            apply(b"b" + source[1:], patch)
        broken = bytearray(patch)
        broken[12] ^= 1
        with self.assertRaisesRegex(ValueError, "checksum"):
            apply(source, bytes(broken))
        with self.assertRaises(ValueError):
            apply(source, patch[:-2])
        with self.assertRaises(ValueError):
            create(source, source)

    def test_different_lengths(self):
        source = bytes(range(100))
        for target in (source[:42], source + b"expanded", bytes(reversed(source))):
            self.assertEqual(apply(source, create(source, target)), target)

    def test_command_line_and_wrong_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tool = Path(__file__).resolve().parents[1] / "tools/rom_patch.py"
            original = root / "source.nds"
            translated = root / "translated.nds"
            original.write_bytes(b"A" * 15000)
            translated.write_bytes(b"A" * 345 + b"B" * 25 + b"A" * 14630)
            delta = root / "translation.bps"
            cmd = [sys.executable, str(tool)]
            created = subprocess.run(
                cmd
                + [
                    "create",
                    "--source",
                    str(original),
                    "--target",
                    str(translated),
                    "--patch",
                    str(delta),
                    "--scope",
                    "synthetic test",
                ],
                capture_output=True,
            )
            self.assertEqual(created.returncode, 0, created.stderr.decode(errors="replace"))
            installed = root / "installed.nds"
            applied = subprocess.run(
                cmd
                + [
                    "apply",
                    "--source",
                    str(original),
                    "--patch",
                    str(delta),
                    "--manifest",
                    str(delta.with_suffix(".json")),
                    "--output",
                    str(installed),
                ],
                capture_output=True,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr.decode(errors="replace"))
            self.assertEqual(installed.read_bytes(), translated.read_bytes())
            self.assertEqual(original.read_bytes(), b"A" * 15000)
            corrupted = root / "wrong.nds"
            corrupted.write_bytes(b"C" * 15000)
            failed = subprocess.run(
                cmd
                + [
                    "apply",
                    "--source",
                    str(corrupted),
                    "--patch",
                    str(delta),
                    "--manifest",
                    str(delta.with_suffix(".json")),
                    "--output",
                    str(root / "bad.nds"),
                ],
                capture_output=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse((root / "bad.nds").exists())
            self.assertNotEqual(
                subprocess.run(
                    cmd
                    + [
                        "apply",
                        "--source",
                        str(original),
                        "--patch",
                        str(delta),
                        "--output",
                        str(original),
                    ],
                    capture_output=True,
                ).returncode,
                0,
            )

    def test_public_tree_rejects_game_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("ordinary documentation")
            (root / "game.nds").write_bytes(b"not a real game")
            self.assertTrue(check(root, [Path("README.md"), Path("game.nds")]))
            with zipfile.ZipFile(root / "embedded.zip", "w") as archive:
                archive.writestr("game.nds", b"not a real game")
            self.assertTrue(check(root, [Path("embedded.zip")]))
            self.assertFalse(check(root, [Path("README.md")]))

    def test_release_zip_contains_no_rom(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = b"unmodified" * 100
            dst = src[:10] + b"edit" + src[14:]
            patch = create(src, dst)
            (root / "test.bps").write_bytes(patch)
            manifest = {
                "format": "gintama-bps-release-v1",
                "patch_filename": "test.bps",
                "patch_sha256": sha256(patch),
                "source_sha256": sha256(src),
                "target_sha256": sha256(dst),
                "source_size": len(src),
                "target_size": len(dst),
            }
            (root / "test.json").write_text(json.dumps(manifest))
            (root / "guide.md").write_text("Use your own original ROM")
            (root / "tool.py").write_text("pass")
            output = root / "kit.zip"
            package(
                root / "test.bps",
                root / "test.json",
                root / "guide.md",
                root / "tool.py",
                output,
            )
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {
                        "test.bps",
                        "test.json",
                        "rom_patch.py",
                        "HOW_TO_APPLY.md",
                        "LICENSE",
                        "RIGHTS.md",
                    },
                )
                self.assertNotIn(src, archive.read("test.bps"))


if __name__ == "__main__":
    unittest.main()
