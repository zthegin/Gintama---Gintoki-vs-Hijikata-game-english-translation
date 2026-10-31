# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import image_workflow as image
from check_public_tree import REVIEWED_SCREENSHOTS, check
from package_source import package as package_source
from sync_csv import render as csv_render
from validate_pr import validate

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    rows = image.font_rows()
    raw = image.pack_obj(image.render_label("ALPHABET", rows))
    packed = image.compress(raw)
    palette = image.compress(struct.pack("<16H", *range(16)))
    container = bytearray(1024)
    container[: len(palette)] = palette
    container[128 : 128 + len(packed)] = packed
    b = bytearray(4096)
    b[12:16] = b"TEST"
    struct.pack_into("<4I", b, 0x40, 0x200, 64, 0x300, 8)
    struct.pack_into("<IHH", b, 0x200, 16, 0, 2)
    struct.pack_into("<IHH", b, 0x208, 27, 0, 0xF000)
    b[0x210:0x21B] = b"\x87gintama\x01\xf0\0"
    b[0x21B:0x226] = b"\x09image.img\0"
    struct.pack_into("<II", b, 0x300, 0x400, 0x800)
    b[0x400:0x800] = container
    e = {
        "id": "gfx_test",
        "source_words_sha256": image.sha(raw),
        "offset": 128,
        "compressed_capacity": len(packed),
        "decoded_bytes": 512,
        "width": 64,
        "height": 16,
        "cell_width": 32,
        "cell_height": 16,
        "background": "original_transparent",
        "canonical_english": "Test",
    }
    catalog = {
        "source_rom_sha256": image.sha(b),
        "source_container": "gintama/image.img",
        "source_container_sha256": image.sha(container),
        "palette_offset": 0,
        "entries": [e],
    }
    batch = {
        "format": "gintama-community-translation-v1",
        "batch_id": "gin_tama_names",
        "records": [
            {
                "id": e["id"],
                "source_words_sha256": e["source_words_sha256"],
                "english": "COIN",
                "translator_note": None,
            }
        ],
    }
    return bytes(b), catalog, batch, rows


class ImageTests(unittest.TestCase):
    def test_obj_cell_order_and_roundtrip(self):
        pixels = [0] * 1024
        pixels[0] = 1
        pixels[31] = 2
        pixels[32] = 3
        pixels[1023] = 4
        data = image.pack_obj(pixels)
        self.assertEqual(data[0] & 15, 1)
        self.assertEqual(data[256] & 15, 3)
        self.assertEqual(image.unpack_obj(data), pixels)

    def test_lz_rejects_pending_vram_read(self):
        unsafe = b"\x10\x04\0\0\x40A\0\0"
        self.assertEqual(image.lz10(unsafe)[0], b"AAAA")
        with self.assertRaises(ValueError):
            image.lz10(unsafe, vram=True)

    def test_all_public_labels_fit_and_roundtrip(self):
        catalog, batch, rows = image.validate_graphic_translations(ROOT)
        self.assertEqual(len(batch["records"]), 193)
        for e, r in zip(catalog["entries"], batch["records"]):
            raw, packed, _ = image.encode_label(r["english"], e, rows)
            self.assertLessEqual(len(packed), e["compressed_capacity"])
            self.assertEqual(image.lz10(packed, vram=True)[0], raw)

    def test_label_rejects_overflow_and_unsupported_symbols(self):
        rows = image.font_rows()
        for text in ["WAY TOO MANY LETTERS ON ONE LINE", "a\nb\nc", "test\t", "☃"]:
            with self.assertRaises(ValueError):
                image.render_label(text, rows)

    def test_wide_label_search_stays_inside_the_image(self):
        rows = image.font_rows()
        entry = {
            "id": "wide_label",
            "background": "original_transparent",
            "compressed_capacity": 145,
        }
        raw, packed, shift = image.encode_label("MMMMMMMMMII", entry, rows)
        self.assertEqual(shift, (0, 2))
        self.assertEqual(
            image.sha(packed),
            "45f04caf22bb42f39718ddf58518aa87ee4b261ffec2a0733d5d3592d15f6ec7",
        )
        self.assertEqual(image.lz10(packed, vram=True)[0], raw)
        entry["compressed_capacity"] = 144
        with self.assertRaisesRegex(ValueError, "needs 145 compressed bytes"):
            image.encode_label("MMMMMMMMMII", entry, rows)

    def test_patch_preserves_source_and_other_base_bytes(self):
        source, catalog, batch, rows = fixture()
        base = bytearray(source)
        base[0x100] = 27
        out, _, _, report = image.prepare(source, catalog, batch, rows, bytes(base))
        self.assertNotEqual(out, source)
        self.assertEqual(out[:0x400], base[:0x400])
        self.assertEqual(out[0x800:], base[0x800:])
        self.assertEqual(out[0x100], 27)
        self.assertTrue(report["byte_and_vram_roundtrips"])
        self.assertEqual(image.sha(source), catalog["source_rom_sha256"])

    def test_wrong_source_and_protected_base_art_rejected(self):
        source, catalog, batch, rows = fixture()
        with self.assertRaises(ValueError):
            image.prepare(source + b"x", catalog, batch, rows)
        base = bytearray(source)
        base[0x400 + 900] = 1
        with self.assertRaises(ValueError):
            image.prepare(source, catalog, batch, rows, bytes(base))

    def test_private_outputs_cannot_land_in_public_tree(self):
        with self.assertRaises(ValueError):
            image.private_output(ROOT / "web/source.png")
        self.assertEqual(
            image.private_output(ROOT / "local/source.png"), ROOT / "local/source.png"
        )

    def test_build_report_cannot_overwrite_an_input_or_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "translated.nds"
            report = out.with_suffix(".report.private.json")
            with self.assertRaises(ValueError):
                image.build_destinations(out, [report])
            report.write_text("Previous report")
            with self.assertRaises(ValueError):
                image.build_destinations(out, [Path(temp) / "original.nds"])
            self.assertFalse(out.exists())
            self.assertEqual(report.read_text(), "Previous report")

    def test_public_guard_rejects_source_text_and_disguised_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "source.json").write_text(
                json.dumps({"original_description_Japanese": "copied prose"})
            )
            (root / "renamed.md").write_bytes(b"\0" * 64)
            self.assertTrue(check(root / "missing"))
            self.assertTrue(check(root, [Path("source.json")]))
            self.assertTrue(check(root, [Path("renamed.md")]))
            (root / "art.png").write_bytes(b"not an actual image")
            self.assertTrue(check(root, [Path("art.png")]))

    def test_only_exact_reviewed_screenshots_are_allowed(self):
        names = [Path(name) for name in REVIEWED_SCREENSHOTS]
        self.assertEqual(
            set(REVIEWED_SCREENSHOTS),
            {
                "docs/screenshots/image-label.png",
                "docs/screenshots/two-line-label.png",
                "docs/screenshots/dialogue-editor.png",
            },
        )
        self.assertEqual(check(ROOT, names), [])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = names[0]
            dest = root / name
            dest.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / name, dest)
            self.assertEqual(check(root, [name]), [])
            dest.write_bytes(dest.read_bytes() + b"changed")
            self.assertTrue(check(root, [name]))
            renamed = name.with_name("game-capture.png")
            shutil.copyfile(ROOT / name, root / renamed)
            self.assertTrue(check(root, [renamed]))
            removed = name.with_name("gameplay.png")
            shutil.copyfile(ROOT / name, root / removed)
            self.assertTrue(check(root, [removed]))

    def test_unpacked_source_audit_ignores_local_builds_but_never_publishes_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("Project tools")
            (root / "local").mkdir()
            (root / "local/game.nds").write_bytes(b"private fixture")
            self.assertEqual(check(root), [])
            self.assertTrue(check(root, [Path("local/game.nds")]))
            (root / "stray.nds").write_bytes(b"private fixture")
            self.assertTrue(check(root))

    def test_source_archive_excludes_local_material_and_rejects_stray_assets(self):
        import zipfile

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            root.mkdir()
            (root / "README.md").write_text("Project tools")
            (root / "PUBLIC_PACKAGE_AUDIT.json").write_text('{"old":true}')
            (root / "local").mkdir()
            (root / "local/source.nds").write_bytes(b"private fixture")
            report = package_source(root, base / "source.zip")
            self.assertEqual(report["files"], 2)
            with zipfile.ZipFile(base / "source.zip") as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {
                        "gintama-community-translation/README.md",
                        "gintama-community-translation/PUBLIC_PACKAGE_AUDIT.json",
                    },
                )
            (root / "stray.nbfc").write_bytes(b"private fixture")
            with self.assertRaises(ValueError):
                package_source(root, base / "bad.zip")

    def test_graphic_pr_pair_accepted_but_geometry_protected(self):
        _, catalog, batch, _ = fixture()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "base"
            candidate = Path(temp) / "candidate"
            for root in [base, candidate]:
                for sub in [
                    "graphics",
                    "reference",
                    "translations/graphics",
                    "csv/graphics",
                ]:
                    (root / sub).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(
                    ROOT / "graphics/pixel_font.json", root / "graphics/pixel_font.json"
                )
                catalog["translation_batch"] = "graphics/gin_tama_names.json"
                (root / "graphics/catalog.json").write_text(json.dumps(catalog))
                (root / "reference/record_index.json").write_text(
                    json.dumps(
                        {
                            "records": [
                                {
                                    "id": "gfx_test",
                                    "source_words_sha256": catalog["entries"][0][
                                        "source_words_sha256"
                                    ],
                                    "page_breaks": 0,
                                }
                            ]
                        }
                    )
                )
                (root / "translations/graphics/gin_tama_names.json").write_text(
                    json.dumps(batch)
                )
                (root / "csv/graphics/gin_tama_names.csv").write_text(csv_render(batch))
            batch["records"][0]["english"] = "TEST"
            (candidate / "translations/graphics/gin_tama_names.json").write_text(
                json.dumps(batch)
            )
            (candidate / "csv/graphics/gin_tama_names.csv").write_text(
                csv_render(batch)
            )
            self.assertEqual(validate(base, candidate)["english_changes"], 1)
            catalog["entries"][0]["width"] = 128
            (candidate / "graphics/catalog.json").write_text(json.dumps(catalog))
            with self.assertRaises(ValueError):
                validate(base, candidate)


if __name__ == "__main__":
    unittest.main()
