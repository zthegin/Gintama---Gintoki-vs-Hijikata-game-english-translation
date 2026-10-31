# Unofficial fan translation. No original game assets are included in these tests.
import copy
import os
import struct
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import battle_writer as battle
import cutscene_writer as cutscene
import dialogue_writer as dialogue
from english_font import GLYPH_CODES, append_font, encode_text
from image_workflow import read_json, sha


def encode_record(header, rows):
    result = bytearray(header)
    for row in rows:
        packed = [sum(row[x + i] << (6 - 2 * i) for i in range(4))
                  for x in range(0, 16, 4)]
        result.extend((packed[1], packed[0], packed[3], packed[2]))
    return bytes(result)


def previous_alignment(font, stride):
    """Recreate the former English alignment in memory for regression comparisons."""
    result = bytearray(font)
    for code in GLYPH_CODES.values():
        at = (code - 1) * stride
        rows = cutscene.record_pixels(font, stride, code)
        if any(row[15] for row in rows):
            raise AssertionError("Reconstructing the previous alignment would lose ink")
        result[at:at + stride] = encode_record(
            font[at:at + 4], [[0] + row[:-1] for row in rows])
    return bytes(result)


class ClusterClippingTests(unittest.TestCase):
    def setUp(self):
        self.lowercase = read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        self.fonts = [(append_font(bytes(6953 * stride), stride, self.lowercase), stride)
                      for stride in (52, 44)]

    def test_appended_glyphs_preserve_native_records_metrics_and_palette_counts(self):
        letters = {**self.lowercase,
                   **read_json(ROOT / "graphics/extended_font.json")["letters"]}
        self.assertEqual(len(letters), 57)
        for font, stride in self.fonts:
            self.assertEqual(font[:6953 * stride], bytes(6953 * stride))
            legacy = previous_alignment(font, stride)
            self.assertEqual(len(font), len(legacy))
            for char, code in GLYPH_CODES.items():
                at = (code - 1) * stride
                self.assertEqual(struct.unpack_from("<I", font, at)[0],
                                 letters[char]["advance"] - 1)
                self.assertEqual(font[at:at + 4], legacy[at:at + 4])
                rows = cutscene.record_pixels(font, stride, code)
                old_rows = cutscene.record_pixels(legacy, stride, code)
                self.assertEqual(Counter(v for row in rows for v in row),
                                 Counter(v for row in old_rows for v in row))
                self.assertTrue(all(not any(row[letters[char]["advance"] - 1:])
                                    for row in rows))

    def test_last_column_crop_preserves_all_strokes_in_screenshot_clusters(self):
        for font, stride in self.fonts:
            legacy = previous_alignment(font, stride)
            for text in ("lea", "ive", " me", "ing", "rry"):
                with self.subTest(stride=stride, text=text):
                    codes = encode_text(text, {})
                    record = cutscene.cluster_codes(codes, font, stride)
                    old_record = cutscene.cluster_codes(codes, legacy, stride)
                    rows = cutscene.record_pixels(record, stride, 1)
                    old_rows = cutscene.record_pixels(old_record, stride, 1)
                    self.assertEqual(dialogue.advance(1, record, stride), 16)
                    self.assertEqual(record[:4], old_record[:4])
                    self.assertTrue(any(row[15] for row in old_rows))
                    self.assertTrue(all(row[15] == 0 for row in rows))
                    self.assertEqual(Counter(v for row in rows for v in row if v),
                                     Counter(v for row in old_rows for v in row if v))
                    self.assertEqual(sum(bool(v) for row in rows for v in row[:15]),
                                     sum(bool(v) for row in old_rows for v in row))

    def test_packed_letters_keep_a_blank_between_adjacent_records(self):
        bank = cutscene.DialogueClusters(self.fonts)
        codes = bank.pack(encode_text("Sorry", {}), 2)
        self.assertEqual(len(codes), 2)
        for font, stride in bank.fonts:
            for code in codes:
                width = dialogue.advance(code, font, stride)
                rows = cutscene.record_pixels(font, stride, code)
                self.assertTrue(all(row[width - 1] == 0 for row in rows))

    def test_rejects_last_advance_column_ink_and_retains_overhang_guard(self):
        for shift, message in ((-1, "trailing blank column"), (0, "exceeds advance")):
            letters = copy.deepcopy(self.lowercase)
            entry = letters["a"]
            row = list(entry["rows"][4])
            row[entry["advance"] + shift] = "3"
            entry["rows"][4] = "".join(row)
            with self.subTest(column=entry["advance"] + shift):
                with self.assertRaisesRegex(ValueError, message):
                    append_font(bytes(6953 * 52), 52, letters)

    @unittest.skipUnless(os.environ.get("GINTAMA_ORIGINAL_ROOT"),
                         "Set GINTAMA_ORIGINAL_ROOT to a private, original extracted tree")
    def test_all_local_translations_keep_script_bytes_metrics_and_font_lengths(self):
        original = Path(os.environ["GINTAMA_ORIGINAL_ROOT"])
        recipe = read_json(ROOT / "graphics/ui_recipes.json")
        fonts = [(append_font((original / "font" / name).read_bytes(), stride,
                              self.lowercase), stride)
                 for name, stride in (("dfgb12.bin", 52), ("dfgb10.bin", 44))]
        old_fonts = [(previous_alignment(font, stride), stride) for font, stride in fonts]
        scene = cutscene.load_scene()
        records = dialogue.load_records(ROOT)
        reference = dialogue.read_json(ROOT / "reference/record_index.json")
        pack = battle.load_pack()
        scripts = {path: (original / path).read_bytes()
                   for script in pack["scripts"] if script["messages"]
                   for path in (script["script"], script["script"][:-3] + "cdb")}

        def build(source_fonts):
            opening, extended, _, opening_report = cutscene.prepare(
                (original / scene["script"]).read_bytes(),
                (original / (scene["script"][:-3] + "cdb")).read_bytes(),
                scene, source_fonts, recipe["latin_glyphs"])
            bank = cutscene.DialogueClusters(extended)
            field, _, field_report = dialogue.patch(
                (original / dialogue.FIELD).read_bytes(),
                (original / dialogue.CDB).read_bytes(), records, reference,
                bank.fonts, recipe["latin_glyphs"], packer=bank)
            patches, final_fonts, battle_report = battle.prepare(
                scripts, pack, bank.fonts, recipe["latin_glyphs"])
            hashes = {scene["script"]: sha(opening), dialogue.FIELD: sha(field),
                      **{path: sha(payload) for path, (payload, _) in patches.items()}}
            return hashes, final_fonts, (opening_report, field_report, battle_report)

        old_hashes, old_banks, old_reports = build(old_fonts)
        new_hashes, new_banks, new_reports = build(fonts)
        self.assertEqual(new_hashes, old_hashes)
        self.assertEqual(new_reports, old_reports)
        for (before, stride), (after, _) in zip(old_banks, new_banks):
            self.assertEqual(len(before), len(after))
            self.assertEqual(before[:6953 * stride], after[:6953 * stride])
            for code in range(1, len(after) // stride + 1):
                at = (code - 1) * stride
                self.assertEqual(before[at:at + 4], after[at:at + 4])
                if code <= 6953:
                    continue
                old_rows = cutscene.record_pixels(before, stride, code)
                rows = cutscene.record_pixels(after, stride, code)
                self.assertEqual(Counter(v for row in rows for v in row),
                                 Counter(v for row in old_rows for v in row))
                self.assertTrue(all(row[15] == 0 for row in rows))


if __name__ == "__main__":
    unittest.main()
