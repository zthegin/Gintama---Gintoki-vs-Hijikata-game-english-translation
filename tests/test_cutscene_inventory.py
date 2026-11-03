# Unofficial fan tools. Use your legally obtained ROM. See RIGHTS.md.
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from index_cutscenes import inventory


class CutsceneInventoryTests(unittest.TestCase):
    def test_inventory_includes_main_scripts_and_read_only_subroutine(self):
        data = json.loads((ROOT / "reference/cutscene_index.json").read_text(encoding="utf-8"))
        scripts = {row["script"]: row for row in data["scripts"]}
        self.assertEqual(set(scripts), {f"adventure/script/s0{n}.msb" for n in range(1, 6)} | {"adventure/script/sub.msb"})
        self.assertTrue(all(row[3] == 0 for row in scripts["adventure/script/sub.msb"]["records"]))
        self.assertEqual(sum(r[3] > 0 for s in scripts.values() for r in s["records"]), 4064)
        for script in scripts.values():
            self.assertEqual(set(script), {"script", "source_msb_sha256", "source_cdb_sha256", "records"})
            for offset, end, digest, parts in script["records"]:
                self.assertGreater(end, offset)
                self.assertRegex(digest, r"^[a-f0-9]{64}$")
                self.assertGreaterEqual(parts, 0)

    @unittest.skipUnless(os.environ.get("GINTAMA_TEST_ROM"), "Requires your private original ROM")
    def test_index_reproduces_exactly_from_original_rom(self):
        source = Path(os.environ["GINTAMA_TEST_ROM"]).read_bytes()
        expected = json.loads((ROOT / "reference/cutscene_index.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory(source), expected)
