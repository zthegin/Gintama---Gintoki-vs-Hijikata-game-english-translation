# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_web as site
from audit_original_content import compare
from check_public_tree import REVIEWED_SCREENSHOTS, check, source_payload, strict_json
from export_approved import export

ROOT = Path(__file__).resolve().parents[1]


class PublicationTests(unittest.TestCase):

    def test_personal_contacts_and_home_paths_are_not_published(self):
        address = "private.person" + "@" + "outlook.com"
        win_home = "C:" + chr(92) + "Users" + chr(92) + "PrivatePerson" + chr(92) + "work"
        samples = [address, win_home, "/home/" + "PrivatePerson/work"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for value in samples:
                (root / "data.json").write_text(json.dumps({"note": value}), encoding="utf-8")
                self.assertTrue(
                    any("personal contact" in issue for issue in check(root, [Path("data.json")]))
                )
            hidden = "".join("\\u%04x" % ord(c) for c in address)
            (root / "data.json").write_text('{"note":"' + hidden + '"}', encoding="utf-8")
            self.assertTrue(check(root, [Path("data.json")]))

    def test_example_contacts_and_github_noreply_are_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "guide.md").write_text("person@example.invalid maintainer@users.noreply.github.com", encoding="utf-8")
            self.assertEqual(check(root, [Path("guide.md")]), [])


    def test_double_extensions_signatures_and_new_game_media_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            for name in [
                "game.NDS.json",
                "native.nclr.txt",
                "game.sdat",
                "manual.svg",
                "clip.mp4",
                "save.ml9",
                "payload.wasm",
            ]:
                (r / name).write_text("{}")
                self.assertTrue(check(r, [Path(name)]), name)
            for signature in [
                b"BPS1",
                b"NARC",
                b"SDAT",
                b"RIFF",
                b"PK\x03\x04",
                b"GIF89a",
            ]:
                (r / "renamed.md").write_bytes(signature + b"synthetic fixture")
                self.assertTrue(check(r, [Path("renamed.md")]))

    def test_normalized_source_field_aliases_and_byte_arrays(self):
        for key in [
            "Original_Pixels",
            "ROM-Data",
            "sourceBytes",
            "Ｊａｐａｎｅｓｅ",
            "japanese_source",
            "font_bitmap",
        ]:
            self.assertTrue(source_payload({"nested": [{key: "fixture"}]}), key)
        self.assertTrue(source_payload({"innocent": [0] * 128}))
        self.assertFalse(
            source_payload(
                {
                    "source_rom_sha256": "a" * 64,
                    "palette_bytes": 32,
                    "offsets": [2, 4, 6],
                }
            )
        )

    def test_decoded_json_and_csv_source_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            text = chr(0x3042) * 9
            (r / "dump.json").write_text(json.dumps({"note": text}, ensure_ascii=True))
            (r / "dump.csv").write_text("id,note\n1," + text, encoding="utf-8")
            self.assertTrue(check(r, [Path("dump.json")]))
            self.assertTrue(check(r, [Path("dump.csv")]))
            (r / "head.csv").write_text("id,JAPANESE_ORIGINAL\n1,fixture\n")
            self.assertTrue(check(r, [Path("head.csv")]))

    def test_encoded_payloads_are_rejected_even_in_innocent_json_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            payload = b"NARC" + bytes(range(128)) * 3
            for value in [base64.b64encode(payload).decode(), payload.hex()]:
                (r / "readme.json").write_text(json.dumps({"example": value}))
                self.assertTrue(check(r, [Path("readme.json")]))

    def test_known_original_fingerprint_disguised_as_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            (r / "reference").mkdir()
            payload = b"synthetic original data"
            (r / "reference/record_index.json").write_text(
                json.dumps({"source_rom_sha256": hashlib.sha256(payload).hexdigest()})
            )
            (r / "renamed.txt").write_bytes(payload)
            self.assertTrue(check(r, [Path("renamed.txt")]))

    def test_credentials_in_docs_and_escaped_json_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            token = "ghp_" + "A" * 24
            (r / "README.md").write_text("accidental token: " + token)
            self.assertTrue(check(r, [Path("README.md")]))
            escaped = "".join("\\u%04x" % ord(c) for c in token)
            (r / "metadata.json").write_text('{"description":"' + escaped + '"}')
            self.assertTrue(check(r, [Path("metadata.json")]))

    def test_strict_json_rejects_duplicates_and_exponent_overflow(self):
        for value in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}']:
            with self.assertRaises(ValueError):
                strict_json(value)

    def test_hidden_paths_case_collisions_and_private_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            (r / "README.md").write_text("tools")
            self.assertTrue(check(r, [Path("README.md"), Path("README.md")]))
            self.assertTrue(check(r, [Path("../README.md")]))
            (r / "Private").mkdir()
            (r / "Private/notes.md").write_text("private")
            self.assertTrue(check(r, [Path("Private/notes.md")]))
            (r / "hidden.md").write_text(
                "text" + chr(0x2066) + "hidden", encoding="utf-8"
            )
            self.assertTrue(check(r, [Path("hidden.md")]))

    def test_site_png_allowlist_and_markers_are_profile_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            (r / "screenshots").mkdir()
            name = next(iter(REVIEWED_SCREENSHOTS))
            (r / "screenshots" / Path(name).name).write_bytes(
                (ROOT / name).read_bytes()
            )
            (r / ".nojekyll").write_bytes(b"")
            (r / ".gintama-site-build").write_text("Static translation editor build\n")
            self.assertEqual(check(r, profile="site"), [])
            self.assertTrue(check(r, profile="source"))
            (r / ".nojekyll").write_text("unexpected")
            self.assertTrue(check(r, profile="site"))

    def test_force_tracked_ignored_game_data_is_never_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            (r / "README.md").write_text("tools")
            (r / "local").mkdir()
            (r / "local/fixture.nds").write_bytes(b"fixture")
            subprocess.run(["git", "init", str(r)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(r), "add", "-f", "local/fixture.nds"],
                check=True,
                capture_output=True,
            )
            self.assertTrue(check(r))
            self.assertTrue(check(r, profile="site"))
            nested = r / "subproject"
            (nested / "local").mkdir(parents=True)
            (nested / "local/fixture.nds").write_bytes(b"fixture")
            subprocess.run(
                ["git", "-C", str(r), "add", "-f", "subproject/local/fixture.nds"],
                check=True,
                capture_output=True,
            )
            self.assertTrue(check(nested))

    def test_untracked_tooling_is_private_but_force_tracked_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directories = (".ruff_cache", ".venv", "venv", "node_modules")
            (root / ".gitignore").write_text(
                "".join(f"{name}/\n" for name in directories), encoding="utf-8"
            )
            for name in directories:
                (root / name).mkdir()
                (root / name / "private.md").write_text(
                    "Local tooling fixture\n", encoding="utf-8"
                )
            subprocess.run(
                ["git", "init", str(root)], check=True, capture_output=True
            )
            self.assertEqual(check(root), [])
            self.assertTrue(check(root, profile="site"))
            self.assertTrue(check(root, profile="export"))

            paths = [f"{name}/private.md" for name in directories]
            subprocess.run(
                ["git", "-C", str(root), "add", "-f", "--", *paths],
                check=True,
                capture_output=True,
            )
            problems = check(root)
            self.assertEqual(
                set(problems),
                {f"Private output must not be published: {path}" for path in paths},
            )

    def test_hidden_and_compatibility_extension_filenames_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            for name in [
                "fixture.nds" + chr(0x202E) + ".py",
                "fixture." + "".join(chr(ord(c) + 0xFEE0) for c in "nds") + ".py",
            ]:
                (r / name).write_text("fixture")
                self.assertTrue(check(r, [Path(name)]))

    def test_optional_original_audit_detects_exact_encoded_and_text_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            payload = b"synthetic private original fixture" * 20
            text = chr(0x3042) * 8
            (r / "whole.txt").write_bytes(payload)
            (r / "encoded.json").write_text(
                json.dumps({"data": base64.b64encode(payload).decode(), "note": text})
            )
            report = compare(r, {hashlib.sha256(payload).hexdigest()}, {text})
            self.assertEqual(
                {m["kind"] for m in report["matches"]},
                {
                    "exact original asset",
                    "encoded original asset",
                    "source-script text match",
                },
            )

    def test_source_audit_blocks_site_before_output_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp) / "repo"
            r.mkdir()
            (r / "stray.nds").write_bytes(b"fixture")
            out = Path(tmp) / "site"
            with patch.object(site, "ROOT", r), self.assertRaises(ValueError):
                site.build(out)
            self.assertFalse(out.exists())

    def test_nested_private_translation_batch_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp) / "repo"
            r.mkdir()
            (r / "reference").mkdir()
            (r / "translations/private").mkdir(parents=True)
            (r / "reference/record_index.json").write_text('{"records":[]}')
            (r / "translations/private/batch.json").write_text('{"records":[]}')
            out = Path(tmp) / "site"
            with patch.object(site, "ROOT", r), self.assertRaises(ValueError):
                site.build(out)
            self.assertFalse(out.exists())

    def test_source_audit_blocks_export_before_output_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp) / "repo"
            r.mkdir()
            (r / "stray.img").write_bytes(b"fixture")
            out = Path(tmp) / "export"
            with self.assertRaises(ValueError):
                export(r, out)
            self.assertFalse(out.exists())

    def test_export_refuses_inside_existing_and_symlink_destinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp) / "repo"
            r.mkdir()
            out = Path(tmp) / "existing"
            out.mkdir()
            (out / "keep.txt").write_text("keep")
            for path in [r / "export", out]:
                with self.assertRaises(ValueError):
                    export(r, path)
            self.assertEqual((out / "keep.txt").read_text(), "keep")



if __name__ == "__main__":
    unittest.main()
