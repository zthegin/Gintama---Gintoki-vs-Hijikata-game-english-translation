# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pack_patch import package
from rom_patch import apply, create, header, sha256

ROOT = Path(__file__).resolve().parents[1]


def read_bps_with_reference_decoder(source: bytes, patch: bytes) -> bytes:
    """Independent SourceRead/TargetRead decoder used to test our encoder."""
    assert patch[:4] == b"BPS1"
    cursor = 4

    def number():
        nonlocal cursor
        result, multiplier = 0, 1
        while True:
            part = patch[cursor]
            cursor += 1
            result += (part & 0x7F) * multiplier
            if part & 0x80:
                return result
            multiplier <<= 7
            result += multiplier

    source_size, target_size, meta_size = number(), number(), number()
    assert source_size == len(source)
    cursor += meta_size
    result = bytearray()
    while len(result) < target_size:
        action = number()
        operation, length = action % 4, (action // 4) + 1
        if operation == 0:
            result.extend(source[len(result) : len(result) + length])
        elif operation == 1:
            result.extend(patch[cursor : cursor + length])
            cursor += length
        else:
            raise AssertionError("Unexpected copy operation in this encoder")
    assert cursor == len(patch) - 12
    return bytes(result)


class PatchIntegrationTests(unittest.TestCase):
    def test_reference_decoder_and_randomized_changes(self):
        rng = random.Random(20310)
        for length in (1, 2, 63, 128, 4096, 65536):
            original = rng.randbytes(length)
            for _ in range(12):
                target = bytearray(original)
                for __ in range(rng.randrange(1, max(2, length // 9))):
                    if target:
                        target[rng.randrange(len(target))] = rng.randrange(256)
                target += rng.randbytes(rng.randrange(0, 30))
                if target == original:
                    target += b"X"
                delta = create(original, bytes(target))
                self.assertEqual(apply(original, delta), bytes(target))
                self.assertEqual(
                    read_bps_with_reference_decoder(original, delta), bytes(target)
                )
                self.assertEqual(header(delta)["source_size"], length)

    def test_packager_rejects_incomplete_and_wrong_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            src, dst = b"A" * 1000, b"A" * 499 + b"B" + b"A" * 500
            delta = create(src, dst)
            patch = base / "translation.bps"
            patch.write_bytes(delta)
            manifest = {
                "format": "gintama-bps-release-v1",
                "patch_filename": patch.name,
                "patch_sha256": sha256(delta),
                "source_sha256": sha256(src),
                "target_sha256": sha256(dst),
                "source_size": len(src),
                "target_size": len(dst),
            }
            guide, tool = ROOT / "docs/APPLY_PATCH.md", ROOT / "tools/rom_patch.py"
            meta = base / "translation.json"
            for key in ("source_sha256", "target_sha256", "patch_sha256"):
                bad = dict(manifest)
                del bad[key]
                meta.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    package(patch, meta, guide, tool, base / "release.zip")
            meta.write_text(json.dumps({**manifest, "target_size": len(dst) + 1}))
            with self.assertRaises(ValueError):
                package(patch, meta, guide, tool, base / "release.zip")
            meta.write_text(json.dumps(manifest))
            package(patch, meta, guide, tool, base / "release.zip")
            with zipfile.ZipFile(base / "release.zip") as bundle:
                self.assertEqual(
                    set(bundle.namelist()),
                    {
                        "translation.bps",
                        "translation.json",
                        "rom_patch.py",
                        "HOW_TO_APPLY.md",
                        "LICENSE",
                        "RIGHTS.md",
                    },
                )
                self.assertEqual(bundle.testzip(), None)



if __name__ == "__main__":
    unittest.main()
