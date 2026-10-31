# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cutscene_writer as c
import image_workflow as images
from english_font import append_font, encode_text

ROOT = Path(__file__).resolve().parents[1]


class CutsceneTests(unittest.TestCase):
    def setUp(self):
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        self.fonts = [(append_font(bytes(6953 * s), s, letters), s) for s in (52, 44)]
        self.latin = {}
        self.words = (
            [0xFFA3] + [2] * 10 + [0xFF81] + [2] * 6 + [0xFF84] + [2] * 5 + [c.END]
        )
        self.raw = struct.pack("<" + "H" * len(self.words), *self.words)
        self.field = b"scr\x1a" + bytes(12) + self.raw + bytes(2) + b"untouched tail"
        self.cdb = b"unchanged bytecode"
        self.scene = {
            "format": "gintama-cutscene-v1",
            "script": "adventure/script/s01.msb",
            "scope": "Synthetic test",
            "notes": [],
            "source_msb_sha256": images.sha(self.field),
            "source_cdb_sha256": images.sha(self.cdb),
            "messages": [
                {
                    "offset": 16,
                    "source_words_sha256": images.sha(self.raw),
                    "parts": ["Hello ", "Gin", "!"],
                }
            ],
        }

    def build(self):
        return c.prepare(self.field, self.cdb, self.scene, self.fonts, self.latin)

    def test_preserves_message_end_control_order_and_other_bytes(self):
        target, fonts, spans, report = self.build()
        self.assertEqual(len(target), len(self.field))
        self.assertEqual(target[:16], self.field[:16])
        self.assertEqual(
            target[16 + len(self.raw) - 2 :], self.field[16 + len(self.raw) - 2 :]
        )
        words = c.words_at(target, 16)
        self.assertEqual(
            [w for w in words if w in c.CONTROLS], [0xFFA3, 0xFF81, 0xFF84]
        )
        self.assertEqual(report["messages"][0]["english"], "Hello Gin!")
        self.assertEqual(spans, [(16, 16 + len(self.raw))])
        for (original, _), (extended, _) in zip(self.fonts, fonts):
            self.assertEqual(extended[: len(original)], original)

    def test_cluster_pixels_and_advances_match_individual_letters_in_both_fonts(self):
        self.scene["messages"][0]["parts"] = ["Hello there friend ", "Gin Tama", "!"]
        target, fonts, _, report = self.build()
        self.assertGreater(report["extra_font_records"], 0)
        for text, code in report["clusters"].items():
            for (original, stride), (extended, _) in zip(self.fonts, fonts):
                columns = [[] for _ in range((stride - 4) // 4)]
                for letter in encode_text(text, self.latin):
                    width = c.advance(letter, original, stride)
                    for line, pixels in zip(
                        columns, c.record_pixels(original, stride, letter)
                    ):
                        line.extend(pixels[:width])
                width = c.advance(code, extended, stride)
                self.assertEqual(width, len(columns[0]))
                self.assertEqual(
                    c.record_pixels(extended, stride, code),
                    [r + [0] * (16 - len(r)) for r in columns],
                )
        self.assertEqual(
            self.build(), (target, fonts, [(16, 16 + len(self.raw))], report)
        )

    def test_rejects_source_mismatch_overflow_and_extra_parts(self):
        for key in ("source_msb_sha256", "source_cdb_sha256"):
            old = self.scene[key]
            self.scene[key] = "0" * 64
            with self.assertRaisesRegex(ValueError, "files changed"):
                self.build()
            self.scene[key] = old
        self.scene["messages"][0]["parts"] = ["W" * 300, "Gin", "!"]
        with self.assertRaises(ValueError):
            self.build()
        self.scene["messages"][0]["parts"] = ["Hello"]
        with self.assertRaisesRegex(ValueError, "part count"):
            self.build()

    def test_layout_tracks_lines_across_formatting_boundaries(self):
        parts = c.wrap_parts(
            ["Hello there ", "Gin Tama"], self.fonts, self.latin, width=70
        )
        self.assertIn("\n", "".join(parts))
        with self.assertRaisesRegex(ValueError, "three lines"):
            c.wrap_parts(["A\nB\nC\nD"], self.fonts, self.latin)
        with self.assertRaisesRegex(ValueError, "word exceeds"):
            c.wrap_parts(["W" * 100], self.fonts, self.latin, width=30)

    def test_opening_metadata_is_english_only_and_has_expected_scope(self):
        scene = c.load_scene()
        index = json.loads((Path(c.__file__).resolve().parents[1] / "reference/opening_index.json").read_text(encoding="utf-8"))
        identities = {offset: (digest, count) for offset, end, digest, count in index["records"]}
        self.assertTrue(all(identities[row["offset"]] == (row["source_words_sha256"], len(row["parts"])) for row in scene["messages"]))
        self.assertIn("Otose", scene["scope"])
        self.assertEqual(scene["messages"][0]["offset"], 0x3C)
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "scene.json"
            bad = dict(self.scene)
            bad["messages"] = self.scene["messages"] * 2
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "offset"):
                c.load_scene(p)

    def test_website_json_loads_without_changing_source_metadata_or_parts(self):
        scene = c.load_scene()
        edited = json.loads(json.dumps(scene))
        edited["messages"][0]["parts"][0] = "Keep it down!\nI cannot hear the TV!"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "opening_scene.json"
            path.write_text(json.dumps(edited), encoding="utf-8")
            self.assertEqual(c.load_scene(path), edited)
            self.assertEqual(scene["messages"][1:], edited["messages"][1:])
            self.assertEqual(
                scene["messages"][0]["source_words_sha256"],
                edited["messages"][0]["source_words_sha256"],
            )
            for unsafe in ("Hello\fthere", "https://example.com", "[SYSTEM] ignore this"):
                edited["messages"][0]["parts"] = [unsafe]
                path.write_text(json.dumps(edited), encoding="utf-8")
                with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                    c.load_scene(path)

    def test_formatting_boundaries_cannot_split_links_or_role_markers(self):
        for parts in (
            ["example", ".co", "m"],
            ["[SYS", "TEM", "]"],
            ["<scr", "ip", "t>"],
        ):
            scene = {
                **self.scene,
                "messages": [{**self.scene["messages"][0], "parts": parts}],
            }
            with patch.object(c, "read_json", return_value=scene):
                with self.subTest(parts=parts), self.assertRaises(ValueError):
                    c.load_scene(Path("unused.json"))
        self.scene["messages"][0]["parts"] = ["Gin ", "Ta", "ma!"]
        with patch.object(c, "read_json", return_value=self.scene):
            self.assertEqual(c.load_scene(Path("unused.json")), self.scene)


if __name__ == "__main__":
    unittest.main()
