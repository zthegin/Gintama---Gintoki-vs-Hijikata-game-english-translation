# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cutscene_writer as cutscene
import dialogue_writer as dialogue
import image_workflow as images
from english_font import GLYPH_CODES, append_font, encode_text

ROOT = Path(__file__).resolve().parents[1]


class FontLayoutTests(unittest.TestCase):
    def setUp(self):
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        self.fonts = [(append_font(bytes(6953 * stride), stride, letters), stride)
                      for stride in (52, 44)]

    def test_punctuation_uses_appended_records_and_n_stem_has_room(self):
        self.assertEqual(encode_text(",!", {}), [7009, 7010])
        for font, stride in self.fonts:
            for char in ",!":
                width = dialogue.advance(GLYPH_CODES[char], font, stride)
                self.assertLessEqual(width, 5)
                rows = cutscene.record_pixels(font, stride, GLYPH_CODES[char])
                self.assertTrue(any(any(row) for row in rows))
            code = GLYPH_CODES["n"]
            width = dialogue.advance(code, font, stride)
            self.assertEqual(width, 6)
            rows = cutscene.record_pixels(font, stride, code)
            for row in rows[5:9]:
                self.assertTrue(row[0])
                self.assertTrue(row[width - 3])
                self.assertFalse(row[width - 2])
                self.assertFalse(row[width - 1])

    def test_packed_field_preserves_pixels_pages_end_and_native_records(self):
        text = "Running, Gin!\fNo, run!"
        original = [2] * 8 + [dialogue.PAGE] + [2] * 8 + [dialogue.END]
        raw = struct.pack("<" + "H" * len(original), *original)
        field = b"scr\x1a" + bytes(12) + raw + bytes(2) + b"tail"
        cdb = b"read-only CDB"
        reference = {"source_msb_sha256": images.sha(field),
                     "source_cdb_sha256": images.sha(cdb),
                     "records": [{"id": "sample", "offset_hex": "0x10",
                                  "source_words_sha256": images.sha(raw)}]}
        row = {"id": "sample", "source_words_sha256": images.sha(raw),
               "english": text, "translator_note": None}
        bank = cutscene.DialogueClusters(self.fonts)
        patched, spans, report = dialogue.patch(
            field, cdb, [row], reference, bank.fonts, {}, packer=bank)
        self.assertEqual(len(patched), len(field))
        self.assertEqual(patched[16 + len(raw) - 2:], field[16 + len(raw) - 2:])
        self.assertEqual(spans, [(16, 16 + len(raw))])
        self.assertEqual(report[0]["padding_words"], 0)
        encoded = dialogue.words_at(patched, 16)
        self.assertEqual(encoded.count(dialogue.PAGE), 1)
        for (before, stride), (after, _) in zip(self.fonts, bank.fonts):
            self.assertEqual(after[:len(before)], before)
            def render(codes, font):
                pages = [[]]
                for code in codes:
                    if code == dialogue.END:
                        break
                    if code in (dialogue.PAGE, dialogue.LINE):
                        pages.append([])
                    else:
                        width = dialogue.advance(code, font, stride)
                        pixels = cutscene.record_pixels(font, stride, code)
                        pages[-1].extend(tuple(row[x] for row in pixels)
                                         for x in range(width))
                return pages
            expected = encode_text(text.replace("\f", "\n"), {})
            self.assertEqual(render(encoded, after), render(expected, before))

    def test_script_labels_preserve_boundaries_and_reject_bad_spans(self):
        raw = struct.pack("<8H", *([2] * 8))
        data = b"scr\x1a" + bytes(12) + raw + bytes(2)
        path = "adventure/script/s01.msb"
        row = {"id": "choice", "script": path, "offset": 16,
               "word_capacity": 8, "source_sha256": images.sha(raw),
               "english": "No, explain!"}
        patches, fonts = cutscene.prepare_labels(
            {path: data}, [row], self.fonts, {}, {})
        self.assertEqual(len(patches), 1)
        name, left, right, payload = patches[0]
        self.assertEqual((name, left, right), (path, 16, 32))
        result = data[:left] + payload + data[right:]
        self.assertEqual(result[:16], data[:16])
        self.assertEqual(result[32:], data[32:])
        self.assertEqual(len(result), len(data))
        for before, after in zip(self.fonts, fonts):
            self.assertEqual(after[0][:len(before[0])], before[0])
        for change in ({"offset": 15}, {"word_capacity": -1},
                       {"source_sha256": "0" * 64}, {"english": "A" * 500}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                cutscene.prepare_labels({path: data}, [{**row, **change}], self.fonts, {}, {})
        with self.assertRaisesRegex(ValueError, "overlaps"):
            cutscene.prepare_labels({path: data}, [row], self.fonts, {}, {path: [(16, 32)]})
        controls = struct.pack("<8H", 0xFF81, *([2] * 7))
        bad = {**row, "source_sha256": images.sha(controls)}
        with self.assertRaisesRegex(ValueError, "controls"):
            cutscene.prepare_labels({path: data[:16] + controls + data[32:]}, [bad], self.fonts, {}, {})
