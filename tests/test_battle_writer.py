# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import copy
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import battle_writer as battle
import cutscene_writer as cutscene
import dialogue_writer as dialogue
import image_workflow as images
from english_font import append_font

ROOT = Path(__file__).resolve().parents[1]


class BattleTests(unittest.TestCase):
    def setUp(self):
        self.raw = struct.pack("<12H", *([2] * 11 + [0xFF71]))
        self.data = b"scr\x1a" + self.raw + b"\0\0SS" + self.raw + b"\0\0"
        self.cdb = b"keep the battle bytecode"
        self.path = "battle/script/character/gintoki.msb"
        self.script = {"script": self.path, "source_msb_sha256": images.sha(self.data),
                       "source_cdb_sha256": images.sha(self.cdb), "record_count": 2,
                       "messages": [{"offset": 4, "source_words_sha256": images.sha(self.raw),
                                     "parts": ["Time to fight!"]}]}
        self.pack = {"format": "gintama-battle-v1", "notes": [], "scripts": [self.script]}
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        self.fonts = [(append_font(bytes(6953 * stride), stride, letters), stride) for stride in (52, 44)]

    def prepare(self):
        return battle.prepare({self.path: self.data, self.path[:-3] + "cdb": self.cdb},
                              self.pack, self.fonts, {"'": 1})

    def test_four_byte_header_keeps_first_record_and_optional_separators(self):
        rows = battle.scan(self.data)
        self.assertEqual([row["offset"] for row in rows], [4, 32])
        self.assertEqual(rows[0]["source_words_sha256"], images.sha(self.raw))
        with self.assertRaisesRegex(ValueError, "offset"):
            dialogue.words_at(self.data, 4)
        self.assertEqual(len(dialogue.words_at(self.data, 4, minimum_offset=4)), 12)

    def test_patching_first_record_preserves_header_end_later_records_and_fonts(self):
        patches, fonts, report = self.prepare()
        data, spans = patches[self.path]
        self.assertEqual(spans, [(4, 28)])
        self.assertEqual(data[:4], self.data[:4])
        self.assertEqual(data[26:], self.data[26:])
        self.assertNotEqual(data[4:26], self.data[4:26])
        self.assertEqual(report[0]["messages"][0]["english"], "Time to fight!")
        for (before, _), (after, _) in zip(self.fonts, fonts):
            self.assertEqual(after[:len(before)], before)

    def test_tables_and_page_controls_are_never_offered_as_editable_text(self):
        for word in (0, 0x5353, 0xFF72, 0xFFFF):
            raw = struct.pack("<3H", 2, word, 0xFF71)
            rows = battle.scan(b"scr\x1a" + raw + b"\0\0")
            self.assertEqual(rows[0]["runs"], [])
        for data in (b"bad!", b"scr\x1a" + self.raw + b"XX", b"scr\x1aX"):
            with self.assertRaises(ValueError):
                battle.scan(data)

    def test_rejects_inside_record_offsets_changed_hashes_and_unsafe_english(self):
        for change in (
            lambda s: s.update(source_msb_sha256="0" * 64),
            lambda s: s.update(source_cdb_sha256="0" * 64),
            lambda s: s["messages"][0].update(offset=6),
            lambda s: s["messages"][0].update(source_words_sha256="0" * 64),
            lambda s: s["messages"][0].update(parts=["https://example.com"]),
            lambda s: s["messages"][0].update(parts=["A", "B"]),
        ):
            with self.subTest(change=change):
                original = copy.deepcopy(self.pack)
                change(self.script)
                with self.assertRaises(ValueError):
                    self.prepare()
                self.pack = original
                self.script = self.pack["scripts"][0]

    def test_pack_schema_rejects_paths_duplicates_nonascii_and_source_fields(self):
        for change in (
            lambda p: p["scripts"][0].update(script="battle/script/character/../secret.msb"),
            lambda p: p["scripts"].append(copy.deepcopy(p["scripts"][0])),
            lambda p: p["scripts"][0]["messages"].append(copy.deepcopy(p["scripts"][0]["messages"][0])),
            lambda p: p["scripts"][0]["messages"][0].update(parts=["Hello\fthere"]),
            lambda p: p["scripts"][0]["messages"][0].update(parts=["\u3042"]),
            lambda p: p["scripts"][0]["messages"][0].update(source_text="not permitted"),
            lambda p: p["scripts"][0].update(record_count=True),
        ):
            value = copy.deepcopy(self.pack)
            change(value)
            with self.assertRaises(ValueError):
                battle.validate_pack(value)

    def test_override_keeps_other_translations_and_rejects_catalog_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "reference").mkdir()
            (root / "reference/battle.json").write_text(json.dumps(self.pack), encoding="utf-8")
            edited = copy.deepcopy(self.pack)
            edited["scripts"][0]["messages"] = [{"offset": 32, "source_words_sha256": images.sha(self.raw), "parts": ["Hi!"]}]
            path = root / "edited.json"; path.write_text(json.dumps(edited), encoding="utf-8")
            result = battle.load_pack(path, root=root)
            self.assertEqual([r["offset"] for r in result["scripts"][0]["messages"]], [4, 32])
            edited["scripts"][0]["record_count"] += 1
            path.write_text(json.dumps(edited), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "metadata differs"):
                battle.load_pack(path, root=root)

    def test_published_pack_covers_requested_gintoki_and_otose_lines(self):
        pack = battle.load_pack()
        self.assertEqual(len(pack["scripts"]), 90)
        self.assertGreaterEqual(sum(len(s["messages"]) for s in pack["scripts"]), 319)
        gintoki = next(s for s in pack["scripts"] if s["script"] == self.path)
        self.assertEqual(gintoki["messages"][0]["offset"], 4)
        self.assertIn("get started", gintoki["messages"][0]["parts"][0])
        self.assertEqual(gintoki["messages"][1]["parts"], ["I'll make this quick!"])

    def test_all_actual_battle_hashes_counts_and_new_fonts_verify_locally(self):
        path = os.environ.get("GINTAMA_TEST_ROM")
        if not path:
            self.skipTest("Set GINTAMA_TEST_ROM for private source verification")
        source = Path(path).read_bytes(); files = images.nds_files(source)
        scripts = {name: source[slice(*span)] for name, span in files.items() if name.startswith("battle/script/")}
        pack = battle.load_pack()
        for script in pack["scripts"]:
            self.assertEqual(images.sha(scripts[script["script"]]), script["source_msb_sha256"])
            self.assertEqual(images.sha(scripts[script["script"][:-3] + "cdb"]), script["source_cdb_sha256"])
            self.assertEqual(len(battle.scan(scripts[script["script"]])), script["record_count"])
        recipe = images.read_json(ROOT / "graphics/ui_recipes.json")
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        fonts = [(append_font(source[slice(*files[f"font/dfgb{n}.bin"] )], stride, letters), stride) for n, stride in ((12, 52), (10, 44))]
        patches, extended, report = battle.prepare(scripts, pack, fonts, recipe["latin_glyphs"])
        self.assertEqual(
            sum(len(row["messages"]) for row in report),
            sum(len(script["messages"]) for script in pack["scripts"]),
        )
        for name, (patched, spans) in patches.items():
            original = scripts[name]
            cursor = 0
            for left, right in spans:
                self.assertEqual(original[cursor:left], patched[cursor:left])
                self.assertEqual(original[right-2:right], patched[right-2:right])
                cursor = right
            self.assertEqual(original[cursor:], patched[cursor:])
        for (before, _), (after, _) in zip(fonts, extended):
            self.assertEqual(before, after[:len(before)])
