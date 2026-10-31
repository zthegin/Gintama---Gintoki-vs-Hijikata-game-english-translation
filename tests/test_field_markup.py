# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from field_markup import (BLUE, RED, RESET, PAGE, color_controls, color_tokens,
                          strip_colors, strip_color_markers, control_sequence,
                          check_record_controls)
from build_ui import unoccupied_script_labels


class FieldMarkupTests(unittest.TestCase):
    def test_colors_are_explicit_balanced_and_not_visible_text(self):
        text = "Go [blue]Forest Trail[/color], then [red]home[/color]."
        self.assertEqual(strip_colors(text), "Go Forest Trail, then home.")
        self.assertEqual(color_controls(text), (BLUE, RESET, RED, RESET))
        self.assertEqual(color_tokens("[BLUE]Forest[/COLOR]"), [BLUE, "Forest", RESET])
        self.assertEqual(strip_colors("A [colorful note]"), "A [colorful note]")

    def test_malformed_empty_nested_or_unclosed_colors_fail(self):
        for text in ("[blue]", "[/color]", "[blue] [red]x[/color][/color]",
                     "[blue][/color]", "[blue] \n[/color]", "[blue", "[/red]",
                     "[color]", "[FF82]"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                strip_colors(text)

    def test_whole_message_supersedes_only_contained_script_labels(self):
        labels = [{"id": "inside", "script": "field", "offset": 20, "word_capacity": 4},
                  {"id": "outside", "script": "field", "offset": 60, "word_capacity": 3}]
        pending, skipped = unoccupied_script_labels(labels, {"field": [(16, 40)]})
        self.assertEqual(pending, [labels[1]])
        self.assertEqual(skipped, ["inside"])
        for span in ((22, 40), (16, 24)):
            with self.subTest(span=span), self.assertRaisesRegex(ValueError, "partially overlaps"):
                unoccupied_script_labels(labels, {"field": [span]})

    def test_indexed_colors_and_pages_are_required_in_the_original_order(self):
        indexed = {"id": "msb_00000010", "page_breaks": 1,
                   "control_sequence": [BLUE, RESET, PAGE]}
        text = "[blue]Forest Trail[/color].\fGo there."
        self.assertEqual(control_sequence(text), (BLUE, RESET, PAGE))
        check_record_controls(text, indexed)
        for wrong in ("Forest Trail.\fGo there.", "[red]Forest Trail[/color].\fGo there.",
                      "Go there.\f[blue]Forest Trail[/color]."):
            with self.subTest(text=wrong), self.assertRaisesRegex(ValueError, "source color controls"):
                check_record_controls(wrong, indexed)

    def test_plain_records_and_image_labels_keep_their_existing_behavior(self):
        check_record_controls("First.\fSecond.", {"id": "msb_00000010", "page_breaks": 1})
        check_record_controls(None, {"id": "msb_00000010", "page_breaks": 1})
        check_record_controls("NEW LABEL", {"id": "image_label_1"})
        with self.assertRaisesRegex(ValueError, "source color controls"):
            check_record_controls("[blue]New[/color]", {"id": "msb_00000010", "page_breaks": 0})
        with self.assertRaisesRegex(ValueError, "image labels"):
            check_record_controls("[blue]New[/color]", {"id": "image_label_1"})
        self.assertEqual(strip_color_markers("The [blue] marker is described here."),
                         "The  marker is described here.")


if __name__ == "__main__":
    unittest.main()
