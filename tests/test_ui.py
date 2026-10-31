# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import contextlib
import copy
import io
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_ui as ui
from english_font import CHARACTERS, GLYPH_CODES
import image_workflow as images
import english_font
import ui_render as render
import ui_tiles as tiles
from rom_patch import apply, create

ROOT = Path(__file__).resolve().parents[1]


class UIBuilderTests(unittest.TestCase):
    def test_all_english_records_keep_original_font_and_roundtrip_pixels(self):
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        letters.update(
            images.read_json(ROOT / "graphics/extended_font.json")["letters"]
        )
        lowercase = {ch: letters[ch] for ch in CHARACTERS[:26]}
        for stride in [44, 52]:
            original = bytes(6953 * stride)
            font = ui.append_font(original, stride, lowercase)
            self.assertEqual(font[: len(original)], original)
            self.assertEqual(len(font), (6953 + len(CHARACTERS)) * stride)
            for i, ch in enumerate(CHARACTERS):
                at = (6953 + i) * stride
                pixels = render.decode_glyph(font[at + 4 : at + stride])
                expected = np.array(
                    [
                        [".123".index(p) for p in row]
                        for row in letters[ch]["rows"][: pixels.shape[0]]
                    ]
                )
                np.testing.assert_array_equal(pixels, expected)
                self.assertEqual(
                    int.from_bytes(font[at : at + 4], "little") + 1,
                    letters[ch]["advance"],
                )

    def test_custom_codes_and_line_width_work_in_both_font_sizes(self):
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        self.assertEqual(GLYPH_CODES["a"], 6954)
        self.assertEqual(GLYPH_CODES["z"], 6979)
        self.assertEqual(GLYPH_CODES["A"], 6980)
        self.assertEqual(GLYPH_CODES["?"], 7006)
        self.assertEqual(GLYPH_CODES["."], 7007)
        self.assertEqual(GLYPH_CODES[" "], 7008)
        for stride in (44, 52):
            font = ui.append_font(bytes(6953 * stride), stride, letters)
            codes = ui.encode_text("Gin Tama?\nYes.", {})
            self.assertEqual(codes[0], GLYPH_CODES["G"])
            self.assertEqual(codes[-1], GLYPH_CODES["."])
            self.assertEqual(ui.text_width(codes, font, stride), 50)
        with self.assertRaisesRegex(ValueError, "Unsupported UI character"):
            ui.encode_text("Hello \U0001f642", {})

    def test_inventory_rejects_overwide_words_after_a_line_wrap(self):
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        font = ui.append_font(bytes(6953 * 52), 52, letters)
        width = ui.text_width(ui.encode_text("W", {}), font)
        too_wide = "W" * (224 // width + 1)
        for text in (too_wide, "OK " + too_wide, "OK " + too_wide + " OK"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "word exceeds the text box"):
                    ui.wrap_item(text, font, {})
        text = "A few ordinary words " * 5
        wrapped = ui.wrap_item(text, font, {})
        self.assertEqual(wrapped.split(), text.split())
        for line in wrapped.split("\n"):
            self.assertLessEqual(ui.text_width(ui.encode_text(line, {}), font), 224)

    def test_rejects_glyphs_that_would_be_cropped_or_overlap(self):
        lowercase = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        extra = images.read_json(ROOT / "graphics/extended_font.json")
        for stride in (44, 52):
            with self.subTest(stride=stride, problem="cropped row"):
                bad = copy.deepcopy(extra)
                bad["letters"]["A"]["rows"][10] = ".3.............."
                with patch.object(english_font, "read_json", return_value=bad):
                    with self.assertRaisesRegex(ValueError, "cropped by DFGB10"):
                        ui.append_font(bytes(6953 * stride), stride, lowercase)
            with self.subTest(stride=stride, problem="advance too narrow"):
                bad = copy.deepcopy(extra)
                bad["letters"]["A"]["advance"] = 3
                with patch.object(english_font, "read_json", return_value=bad):
                    with self.assertRaisesRegex(ValueError, "ink exceeds advance"):
                        ui.append_font(bytes(6953 * stride), stride, lowercase)

    def test_obj_cells_roundtrip_across_the_supported_geometries(self):
        rng = np.random.default_rng(6)
        for width, height in [(64, 16), (112, 16), (224, 32), (256, 32), (192, 128)]:
            before = rng.integers(0, 16, size=(height, width), dtype=np.uint8)
            data = tiles.pack_sprite(before)
            header, decoded = tiles.decode(data)
            self.assertEqual(header, b"")
            np.testing.assert_array_equal(tiles.sprite(decoded, width, height), before)

    def test_map_flip_reuse_preserves_banks_and_unused_tiles(self):
        before = np.arange(64, dtype=np.uint8).reshape(8, 8) % 16
        tile_data = np.stack([before, 15 - before, np.zeros((8, 8), np.uint8)])
        header = b""
        map_data = struct.pack("<HH2H", 2, 1, 0x1000, 0x1400)
        after = np.concatenate([before + 16, before[:, ::-1] + 16], axis=1)
        resource = type(
            "Map",
            (),
            {
                "parent": Path("screen"),
                "name": "test.nbfc",
                "with_suffix": lambda self, suffix: "map",
            },
        )()
        changes, report = tiles.pack_map(resource, after, header, tile_data, map_data)
        _, decoded = tiles.decode(changes[resource])
        self.assertEqual(report["English_unique_tiles"], 1)
        np.testing.assert_array_equal(decoded[1:], tile_data[1:])
        words = struct.unpack("<2H", changes["map"][4:])
        self.assertTrue(all(word >> 12 == 1 for word in words))
        self.assertEqual(words[1] & 0x400, 0x400)

    def test_compressed_slots_check_capacity_and_halfword_output(self):
        payload = bytes(range(32)) * 16
        packed = ui.compress_slot(payload, 100, vram=True)
        self.assertEqual(images.lz10(packed, vram=True)[0], payload)
        with self.assertRaisesRegex(ValueError, "slot"):
            ui.compress_slot(payload, 4, vram=True)

    def test_failed_output_write_does_not_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            new = folder / "new.txt"
            existing = folder / "existing.txt"
            existing.write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                images.write_outputs({new: b"temporary", existing: b"replace"})
            self.assertFalse(new.exists())
            self.assertEqual(existing.read_bytes(), b"keep")

    def test_existing_sidecar_is_rejected_before_reading_or_building(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            target = folder / "translated.nds"
            target.with_suffix(".report.private.json").write_text(
                "keep", encoding="utf-8"
            )
            argv = [
                "build_ui.py",
                "--rom",
                str(folder / "original.nds"),
                "--out",
                str(target),
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(images, "read_rom") as read,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    ui.main()
                read.assert_not_called()
            self.assertFalse(target.exists())

    def test_wrong_rom_is_rejected_before_rendering(self):
        with patch.object(render, "translate_sign") as draw:
            with self.assertRaisesRegex(ValueError, "original ROM"):
                ui.build(
                    b"wrong", {"source_rom_sha256": "0" * 64}, None, None, None, None
                )
            draw.assert_not_called()

    def test_actual_rom_build_and_patch_roundtrip(self):
        path = os.environ.get("GINTAMA_TEST_ROM")
        if not path:
            self.skipTest("Set GINTAMA_TEST_ROM for the private full-UI build check")
        source = images.read_rom(Path(path))
        recipe = images.read_json(ROOT / "graphics/ui_recipes.json")
        catalog, batch, alphabet = images.validate_graphic_translations(ROOT)
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        with contextlib.redirect_stdout(io.StringIO()):
            result, report = ui.build(source, recipe, catalog, batch, alphabet, letters)
        self.assertEqual((report["graphics"], report["ui_text"]), (649, 122))
        self.assertEqual(apply(source, create(source, result)), result)
        before = images.nds_files(source)
        after = images.nds_files(result)
        for path in ["field/script/fld_scr.cdb", "adventure/script/s01.cdb"]:
            left, right = before[path]
            a, b = after[path]
            self.assertEqual(source[left:right], result[a:b])
        self.assertEqual(
            report["dialogue_messages"], len(ui.dialogue.load_records(ROOT))
        )
        old_field = source[slice(*before[ui.dialogue.FIELD])]
        new_field = result[slice(*after[ui.dialogue.FIELD])]
        spans = [(row["offset"], row["end_offset"]) for row in report["dialogue"]]
        field_labels = [
            (row["offset"], row["offset"] + row["word_capacity"] * 2)
            for row in recipe["script_labels"] if row["script"] == ui.dialogue.FIELD
        ]
        ui.unchanged_outside(old_field, new_field, spans + field_labels)
        for left, right in spans:
            self.assertEqual(old_field[right - 2 : right], new_field[right - 2 : right])
        scene = images.read_json(ROOT / "reference/opening_scene.json")
        self.assertEqual(report["cutscene_messages"], len(scene["messages"]))
        self.assertCountEqual(
            [row["offset"] for row in report["cutscene"]["messages"]],
            [row["offset"] for row in scene["messages"]],
        )
        self.assertGreater(report["cutscene_font_records"], 0)
        old_scene = source[slice(*before["adventure/script/s01.msb"])]
        new_scene = result[slice(*after["adventure/script/s01.msb"])]
        scene_spans = [
            (r["offset"], r["end_offset"]) for r in report["cutscene"]["messages"]
        ]
        choice_labels = [
            (row["offset"], row["offset"] + row["word_capacity"] * 2)
            for row in recipe["script_labels"] if row["script"] == "adventure/script/s01.msb"
        ]
        ui.unchanged_outside(old_scene, new_scene, scene_spans + choice_labels)
        self.assertEqual(len(recipe["script_labels"]), 13)
        self.assertEqual(report["script_labels"]
                         + len(report["script_labels_covered_by_messages"]), 13)
        occupied = {ui.dialogue.FIELD: spans, "adventure/script/s01.msb": scene_spans}
        expected_covered = {
            row["id"] for row in recipe["script_labels"]
            if any(left <= row["offset"] and row["offset"] + row["word_capacity"] * 2 <= right
                   for left, right in occupied[row["script"]])
        }
        self.assertEqual(set(report["script_labels_covered_by_messages"]), expected_covered)
        for offset in (0x141BC, 0x14218):
            original_words = ui.dialogue.words_at(old_field, offset)
            new_words = ui.dialogue.words_at(new_field, offset)
            self.assertEqual([w for w in original_words if w >= 0xFF00],
                             [w for w in new_words if w >= 0xFF00])
            for size, stride in ((12, 52), (10, 44)):
                font = result[slice(*after[f"font/dfgb{size}.bin"])]
                width = 0
                for word in new_words:
                    if word in (0xFF70, 0xFF71, 0xFF72):
                        self.assertLessEqual(width, 176)
                        width = 0
                    elif word not in ui.cutscene.CONTROLS:
                        width += ui.dialogue.advance(word, font, stride)
        for left, right in scene_spans:
            self.assertEqual(old_scene[right - 2 : right], new_scene[right - 2 : right])
        for row in report["cutscene"]["messages"]:
            self.assertEqual(
                new_scene[row["offset"] : row["end_offset"]],
                struct.pack("<" + "H" * len(row["encoded_words"]), *row["encoded_words"]),
            )
        battle = images.read_json(ROOT / "reference/battle.json")
        expected_battle = [
            (script["script"], row["offset"])
            for script in battle["scripts"] for row in script["messages"]
        ]
        self.assertEqual(report["battle_messages"], len(expected_battle))
        self.assertCountEqual(
            [(script["script"], row["offset"])
             for script in report["battle"] for row in script["messages"]],
            expected_battle,
        )
        for row in report["battle"]:
            name = row["script"]
            new_battle = result[slice(*after[name])]
            for message in row["messages"]:
                self.assertEqual(
                    new_battle[message["offset"] : message["end_offset"]],
                    struct.pack("<" + "H" * len(message["encoded_words"]),
                                *message["encoded_words"]),
                )
            ui.unchanged_outside(source[slice(*before[name])], result[slice(*after[name])],
                                 [(m["offset"], m["end_offset"]) for m in row["messages"]])
            cdb = name[:-3] + "cdb"
            self.assertEqual(source[slice(*before[cdb])], result[slice(*after[cdb])])
        self.assertTrue(report["cdb_unchanged"])
        self.assertTrue(report["dialogue_end_offsets_unchanged"])
        for path in ["font/dfgb12.bin", "font/dfgb10.bin"]:
            left, right = before[path]
            a, b = after[path]
            self.assertEqual(source[left:right], result[a : a + right - left])
        self.assertEqual(
            ui.crc16(result[:0x15E]), struct.unpack_from("<H", result, 0x15E)[0]
        )
        self.assertFalse(report["runtime_verified"])


if __name__ == "__main__":
    unittest.main()
