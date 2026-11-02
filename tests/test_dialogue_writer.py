# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import dialogue_writer as writer
import image_workflow as images
from english_font import GLYPH_CODES, append_font
from field_markup import BLUE, RED, RESET, COLOR_CONTROLS, strip_colors
from ui_render import name_mask, outlined_name

ROOT = Path(__file__).resolve().parents[1]


class DialogueWriterTests(unittest.TestCase):
    def setUp(self):
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        self.fonts = [
            (append_font(bytes(6953 * stride), stride, letters), stride)
            for stride in (52, 44)
        ]
        self.cdb = b"synthetic CDB remains untouched"
        self.setup_slot([2] * 30 + [writer.PAGE] + [2] * 30 + [writer.END])

    def setup_slot(self, words):
        raw = struct.pack("<" + "H" * len(words), *words)
        self.field = b"scr\x1a" + bytes(12) + raw + bytes(2) + b"private trailer"
        self.row = {
            "id": "msb_00000010",
            "source_words_sha256": images.sha(raw),
            "english": "Hello?\fBye.",
            "translator_note": None,
        }
        self.reference = {
            "source_msb_sha256": images.sha(self.field),
            "source_cdb_sha256": images.sha(self.cdb),
            "records": [
                {
                    "id": self.row["id"],
                    "source_words_sha256": self.row["source_words_sha256"],
                    "offset_hex": "0x10",
                }
            ],
        }

    def patch(self, rows=None):
        return writer.patch(
            self.field,
            self.cdb,
            [self.row] if rows is None else rows,
            self.reference,
            self.fonts,
            {},
        )

    def test_fixed_slot_preserves_end_separator_suffix_and_page_count(self):
        target, spans, report = self.patch()
        self.assertEqual(len(target), len(self.field))
        left, end = spans[0]
        self.assertEqual(target[:left], self.field[:left])
        self.assertEqual(target[end - 2 :], self.field[end - 2 :])
        words = writer.words_at(target, left)
        self.assertEqual(words.count(writer.PAGE), 1)
        self.assertEqual(words[0], GLYPH_CODES["H"])
        self.assertEqual(words[-1], writer.END)
        self.assertEqual(report[0]["pages"], 2)
        self.assertGreater(report[0]["padding_words"], 0)

    def test_unknown_id_hash_mismatch_and_duplicate_rows_fail(self):
        for key, value in [("id", "unknown"), ("source_words_sha256", "0" * 64)]:
            with self.subTest(key=key):
                row = {**self.row, key: value}
                with self.assertRaises(ValueError):
                    self.patch([row])
        with self.assertRaises(ValueError):
            self.patch([self.row, self.row])

    def test_inline_controls_and_changed_page_count_fail(self):
        self.row["english"] = "Hello."
        with self.assertRaisesRegex(ValueError, "page count"):
            self.patch()
        self.setup_slot([2, 0xFF50, writer.END])
        with self.assertRaisesRegex(ValueError, "Complex"):
            self.patch()

    def test_overflow_is_rejected_without_truncation(self):
        self.setup_slot([2] * 5 + [writer.END])
        self.row["english"] = "Hello there."
        with self.assertRaisesRegex(ValueError, "never truncated"):
            self.patch()
        self.setup_slot([2] * 200 + [writer.END])
        self.row["english"] = "H"
        with self.assertRaisesRegex(ValueError, "padding"):
            self.patch()

    def test_wrap_checks_both_fonts_and_explicit_lines(self):
        text, codes = writer.layout("Hello there Hello there", self.fonts, {}, width=65)
        self.assertIn("\n", text)
        writer.check_layout(codes + [writer.END], self.fonts, width=65)
        for text in ["A\nB\nC\nD", "A\f\fB", "x" * 100]:
            with self.assertRaises(ValueError):
                writer.layout(text, self.fonts, {})

    def test_color_markers_wrap_without_width_and_preserve_native_controls(self):
        self.setup_slot([2] * 25 + [BLUE] + [2] * 20 + [RESET] + [2] * 15 + [writer.END])
        self.row["english"] = "Go [blue]Forest Trail[/color]."
        target, spans, report = self.patch()
        words = writer.words_at(target, 16)
        self.assertEqual([word for word in words if word in COLOR_CONTROLS], [BLUE, RESET])
        self.assertEqual(target[spans[0][1] - 2 :], self.field[spans[0][1] - 2 :])
        self.assertIn("[blue]Forest Trail[/color]", report[0]["laid_out_english"])
        plain, plain_codes = writer.layout("Go Forest Trail.", self.fonts, {}, width=65)
        marked, marked_codes = writer.layout(self.row["english"], self.fonts, {}, width=65)
        self.assertEqual(strip_colors(marked), plain)
        self.assertEqual([word for word in marked_codes if word not in COLOR_CONTROLS], plain_codes)

    def test_source_colors_cannot_be_lost_added_changed_or_moved_to_another_page(self):
        self.setup_slot([BLUE] + [2] * 20 + [RESET, writer.PAGE] + [2] * 20 + [writer.END])
        for text in ("Hello.\fBye.", "[red]Hello.[/color]\fBye.",
                     "Hello.\f[blue]Bye.[/color]"):
            self.row["english"] = text
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "color controls"):
                self.patch()
        self.row["english"] = "[blue]Hello.[/color]\fBye."
        self.patch()
        self.setup_slot([2] * 40 + [writer.END])
        self.row["english"] = "[blue]Hello.[/color]"
        with self.assertRaisesRegex(ValueError, "color controls"):
            self.patch()

    def test_cluster_packing_keeps_color_boundaries_and_end_offset(self):
        from cutscene_writer import DialogueClusters
        self.setup_slot([2] * 4 + [BLUE] + [2] * 4 + [RESET] + [2] * 4 + [writer.END])
        self.row["english"] = "Go [blue]Forest Trail[/color]."
        packer = DialogueClusters(self.fonts)
        target, spans, _ = writer.patch(
            self.field, self.cdb, [self.row], self.reference, packer.fonts, {}, packer=packer
        )
        words = writer.words_at(target, 16)
        self.assertTrue(packer.codes)
        self.assertEqual([word for word in words if word in COLOR_CONTROLS], [BLUE, RESET])
        self.assertTrue(all(all(code < 0xFF00 for code in cluster) for cluster in packer.codes))
        self.assertEqual(spans[0][1], 16 + len(words) * 2)
        self.assertEqual(target[spans[0][1] - 2 :], self.field[spans[0][1] - 2 :])

    def test_strict_batch_load_and_export_use_same_english_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / "approved_translations.json"
            data = {
                "format": "gintama-approved-translation-export-v2",
                "translations": [self.row],
            }
            file.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(writer.load_records(root), [self.row])
            file.write_text('{"format":1,"format":2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                writer.load_records(root)

    def test_default_build_keeps_bundled_field_dialogue(self):
        data = images.read_json(ROOT / "translations/ready/field_dialogue.json")
        self.assertEqual(data["batch_id"], "field_dialogue")
        self.assertGreaterEqual(len(data["records"]), 162)
        expected_ids = {
            "msb_00004EA8",
            "msb_00014284",
            "msb_000142B4",
            "msb_000142EC",
            "msb_00014330",
            "msb_00014348",
            "msb_0001446C",
            "msb_00014494",
            "msb_000144B4",
            "msb_000144F8",
            "msb_0001451C",
        }
        translated = {row["id"]: row for row in data["records"] if row["english"]}
        self.assertTrue(expected_ids <= translated.keys())
        loaded = {row["id"]: row for row in writer.load_records(ROOT)}
        expected = {
            row["id"]: row
            for path in (ROOT / "translations/ready").glob("*.json")
            for row in images.read_json(path)["records"]
            if row["english"] is not None
        }
        self.assertEqual(loaded, expected)
        self.assertTrue(translated.keys() <= loaded.keys())
        self.assertEqual({key: loaded[key] for key in translated}, translated)

    def test_all_names_fit_without_resampling_or_clipping(self):
        recipe = images.read_json(ROOT / "graphics/ui_recipes.json")
        names = [row for row in recipe["graphics"] if row["kind"] == "packed-nameplate"]
        self.assertEqual(len(names), 128)
        for row in names:
            with self.subTest(name=row["English_UI"]):
                mask = name_mask(row["English_UI"], *row["dimensions"])
                self.assertEqual(mask.shape, (16, 64))
                self.assertEqual(set(np.unique(mask)), {0, 255})
                self.assertFalse(mask[:, [0, -1]].any())
                self.assertFalse(mask[[0, -1], :].any())

    def test_english_spaces_do_not_change_padding_or_original_records(self):
        from english_font import encode_text

        self.assertEqual(encode_text("A B", {})[1], 7008)
        for font, stride in self.fonts:
            self.assertEqual(writer.advance(7008, font, stride), 3)
            self.assertEqual(writer.advance(1, font, stride), 1)
            at = (7008 - 1) * stride
            self.assertFalse(any(font[at + 4 : at + stride]))

    def test_native_palette_black_outline_is_opaque_not_transparent(self):
        mask = np.zeros((7, 7), np.uint8)
        mask[3, 3] = 255
        colors = [
            (0, 0, 0),
            (0, 0, 0),
            (90, 90, 90),
            (123, 123, 123),
            (156, 156, 156),
            (205, 205, 205),
            (255, 255, 255),
        ]
        result = outlined_name(mask, colors)
        self.assertEqual(result[3, 3], 6)
        self.assertEqual(
            [result[y, x] for y, x in [(2, 3), (3, 2), (3, 4), (4, 3)]], [1, 1, 1, 1]
        )
        self.assertEqual(result[2, 2], 0)
        self.assertEqual(result[0, 0], 0)
        self.assertEqual(set(np.unique(result)), {0, 1, 6})

    def test_verified_inline_controls_are_single_words_and_keep_order(self):
        self.setup_slot([0xFFA1] + [2] * 16 + [0xFF83] + [2] * 8 +
                        [RESET, writer.PAGE, 0xFFB1] + [2] * 20 + [0xFFB2, writer.END])
        self.row['english'] = '[ctrl:FFA1]Hello [ctrl:FF83]there[/color].\f[ctrl:FFB1]Bye.[ctrl:FFB2]'
        target, spans, _ = self.patch()
        words = writer.words_at(target, 16)
        kept = [word for word in words if word in writer.FIELD_CONTROLS]
        self.assertEqual(kept, [0xFFA1, 0xFF83, RESET, writer.PAGE, 0xFFB1, 0xFFB2, writer.END])
        self.assertEqual(target[spans[0][1]-2:], self.field[spans[0][1]-2:])
        for english in ('Hello [ctrl:FF83]there[/color].\f[ctrl:FFB1]Bye.[ctrl:FFB2]',
                        '[ctrl:FFA1]Hello [ctrl:FF83]there[/color].\f[ctrl:FFB2]Bye.[ctrl:FFB1]'):
            self.row['english'] = english
            with self.assertRaisesRegex(ValueError, 'controls'):
                self.patch()

    def test_unknown_or_malformed_inline_controls_are_rejected(self):
        for text in ('[ctrl:FF91]x', '[ctrl:FF00]x', '[ctrl:FFA1', '[ctrl FFA1]x',
                     '[ctrl:FF83]x', '[ctrl:FF83][/color]', '[blue][ctrl:FF83]x[/color][/color]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                strip_colors(text)

    def test_inline_markers_have_no_display_width(self):
        text = '[ctrl:FFA1]Hello.[ctrl:FFB1]'
        laid_out, codes = writer.layout(text, self.fonts, {})
        self.assertEqual(laid_out, text)
        self.assertEqual(codes[0], 0xFFA1)
        self.assertEqual(codes[-1], 0xFFB1)
        self.assertEqual(strip_colors(text), 'Hello.')

    def test_nul_prefix_preserves_neighboring_choice_bytes_and_protected_tail(self):
        for suffix in ([], [RED]):
            self.setup_slot([2] * 30 + suffix + [0])
            self.reference['records'][0].update(termination='nul', trailing_controls=suffix)
            self.row['english'] = 'Hello.'
            target, spans, _ = self.patch()
            end = spans[0][1]
            self.assertEqual(len(target), len(self.field))
            self.assertEqual(target[end:], self.field[end:])
            self.assertEqual(target[end-2*(len(suffix)+1):end], self.field[end-2*(len(suffix)+1):end])
            words = writer.words_at(target, 16, terminator=0)
            self.assertEqual(words[-1], 0)
            self.assertEqual(words[-len(suffix)-1:-1] if suffix else [], suffix)

    def test_nul_prefix_rejects_empty_missing_wrong_hash_and_invalid_termination(self):
        self.setup_slot([0])
        self.reference['records'][0]['termination'] = 'nul'
        with self.assertRaisesRegex(ValueError, 'Empty'):
            self.patch()
        with self.assertRaisesRegex(ValueError, 'Unterminated'):
            writer.words_at(b'X' * 16 + b'xx' * 5, 16, terminator=0)
        self.setup_slot([2]*10 + [0] + [2]*10 + [writer.END])
        self.reference['records'][0]['termination'] = 'nul'
        with self.assertRaisesRegex(ValueError, 'source span'):
            self.patch()
        self.setup_slot([2]*10 + [writer.END, 0])
        self.reference['records'][0]['termination'] = 'nul'
        with self.assertRaisesRegex(ValueError, 'Unexpected END'):
            writer.words_at(self.field, 16, terminator=0)
        with self.assertRaisesRegex(ValueError, 'Unexpected END'):
            self.patch()
        for termination in ('unknown', 0, None):
            self.reference['records'][0]['termination'] = termination
            with self.assertRaisesRegex(ValueError, 'termination'):
                self.patch()

    def test_protected_suffix_requires_exact_known_tail_and_nul_mode(self):
        self.setup_slot([2] * 20 + [RED, 0])
        source = self.reference['records'][0]
        source.update(termination='nul', trailing_controls=[BLUE])
        self.row['english'] = 'Hello.'
        with self.assertRaisesRegex(ValueError, 'suffix'):
            self.patch()
        source['trailing_controls'] = [RED, BLUE]
        with self.assertRaisesRegex(ValueError, 'suffix'):
            self.patch()
        source['trailing_controls'] = [RED]
        self.field = self.field[:16+20*2] + struct.pack('<H', BLUE) + self.field[16+21*2:]
        self.reference['source_msb_sha256'] = images.sha(self.field)
        with self.assertRaisesRegex(ValueError, 'suffix'):
            self.patch()

    def test_verified_raw_color_transitions_preserve_each_native_word(self):
        self.setup_slot([0xFFA3, writer.LINE, RED, BLUE] + [2] * 12 +
                        [RESET] + [2] * 12 + [RESET, writer.END])
        self.reference['records'][0]['raw_color_controls'] = True
        self.row['english'] = '[ctrl:FFA3]\n[ctrl:FF81][ctrl:FF82]Hi[ctrl:FF84] there.[ctrl:FF84]'
        target, _, _ = self.patch()
        words = writer.words_at(target, 16)
        self.assertEqual([w for w in words if w in writer.FIELD_CONTROLS and w != writer.LINE],
                         [0xFFA3, RED, BLUE, RESET, RESET, writer.END])
        self.row['english'] = self.row['english'].replace('[ctrl:FF81]', '')
        with self.assertRaisesRegex(ValueError, 'controls'):
            self.patch()
        self.reference['records'][0]['raw_color_controls'] = 'yes'
        with self.assertRaisesRegex(ValueError, 'flag'):
            self.patch()
        with self.assertRaisesRegex(ValueError, 'nested'):
            strip_colors('[red][blue]Hi[/color][/color]')

    def test_nul_menu_rejects_explicit_or_automatically_wrapped_extra_lines(self):
        self.setup_slot([2] * 100 + [0])
        self.reference['records'][0]['termination'] = 'nul'
        for text in ('First.\nSecond.',
                     'This is a long menu option that should wrap onto a second line.'):
            self.row['english'] = text
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'Menu text exceeds'):
                self.patch()
        self.setup_slot([2] * 30 + [writer.LINE] + [2] * 30 + [0])
        self.reference['records'][0]['termination'] = 'nul'
        self.row['english'] = 'First.\nSecond.'
        self.patch()
        self.setup_slot([2] * 80 + [writer.END])
        self.row['english'] = 'One.\nTwo.\nThree.'
        self.patch()


if __name__ == "__main__":
    unittest.main()
