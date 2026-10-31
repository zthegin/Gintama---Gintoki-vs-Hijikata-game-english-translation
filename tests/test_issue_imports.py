# Unofficial fan translation; no game ownership is claimed. See RIGHTS.md.
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_issue as cli
import issue_imports as issues
from credits import FORMAT, render
from sync_csv import render as csv_render

HASH = "a" * 64


def field_body(text="New text!", note="(none)"):
    return f'Translation suggestion\n\nID: msb_00000010\nSource SHA-256: {HASH}\nEnglish (JSON escaped):\n{json.dumps(text)}\nNote: {note}\n\nNo source game text is included.'


def issue(body=None, number=7):
    return {"number": number, "repository_url": f"https://api.github.com/repos/{issues.REPOSITORY}", "html_url": f"https://github.com/{issues.REPOSITORY}/issues/{number}", "user": {"login": "example-translator", "id": 42, "type": "User"}, "updated_at": "2026-10-29T01:00:00Z", "body": body or field_body()}


class IssueImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "example", "GIT_AUTHOR_EMAIL": "example@users.noreply.github.com", "GIT_COMMITTER_NAME": "example", "GIT_COMMITTER_EMAIL": "example@users.noreply.github.com"}
        self.batch = {"format": "gintama-community-translation-v1", "batch_id": "batch_0001", "records": [{"id": "msb_00000010", "source_words_sha256": HASH, "english": "Old text.", "translator_note": None}]}
        self.write("README.md", b"Example fixture\n")
        self.write("translations/ready/batch_0001.json", issues.encoded(self.batch))
        self.write("csv/ready/batch_0001.csv", csv_render(self.batch).encode())
        self.write("reference/record_index.json", issues.encoded({"records": [{"id": "msb_00000010", "source_words_sha256": HASH, "page_breaks": 0}]}))
        self.write("credits/merged_prs.json", issues.encoded({"format": FORMAT, "entries": []}))
        self.write(issues.LEDGER, issues.encoded({"format": issues.ISSUE_FORMAT, "entries": []}))
        self.write("TRANSLATORS.md", render({"entries": []}).encode())
        self.git("init", "-b", "codex/issue-7")
        self.commit()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=" + os.devnull, *args], cwd=self.root, env=self.env, stderr=subprocess.DEVNULL)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-m", "Fixture")

    def fake_fetch(self, number, token=None):
        return issue(number=number)

    def fit(self, *args):
        return {"record_fit_checked": True, "rom_written": False}

    def test_preview_does_not_write_and_credits_api_user(self):
        result = cli.import_one(self.root, 7, fetch=self.fake_fetch)
        self.assertFalse(result["applied"])
        self.assertEqual(result["contributor"], "@example-translator")
        self.assertEqual(result["english"], "New text!")
        self.assertEqual(self.git("status", "--porcelain"), b"")

    def test_apply_updates_text_csv_receipt_and_contributor_counts(self):
        result = cli.import_one(self.root, 7, apply=True, rom=Path("original.nds"), fetch=self.fake_fetch, fit=self.fit)
        self.assertTrue(result["applied"])
        data = json.loads((self.root / "translations/ready/batch_0001.json").read_text())
        self.assertEqual(data["records"][0]["english"], "New text!")
        self.assertEqual((self.root / "csv/ready/batch_0001.csv").read_text(), csv_render(data))
        receipt = issues.read_issue_ledger(self.root / issues.LEDGER)["entries"][0]
        self.assertEqual(receipt["login"], "example-translator")
        self.assertEqual((receipt["record"]["kind"], receipt["record"]["words"], receipt["record"]["characters"]), ("revision", 2, 8))
        self.assertIn("@example-translator", (self.root / "TRANSLATORS.md").read_text())
        self.assertFalse(list(self.root.rglob(".issue-import-*")))

    def test_apply_requires_clean_review_branch_and_rom(self):
        self.write("untracked.txt", b"keep")
        with self.assertRaises(ValueError):
            cli.import_one(self.root, 7, apply=True, rom=Path("original.nds"), fetch=self.fake_fetch, fit=self.fit)
        (self.root / "untracked.txt").unlink()
        with self.assertRaises(ValueError):
            cli.import_one(self.root, 7, apply=True, fetch=self.fake_fetch)
        with self.assertRaises(ValueError):
            cli.import_one(self.root, 8, apply=True, rom=Path("original.nds"), fetch=self.fake_fetch, fit=self.fit)
        self.git("switch", "-c", "main")
        with self.assertRaises(ValueError):
            cli.import_one(self.root, 7, apply=True, rom=Path("original.nds"), fetch=self.fake_fetch, fit=self.fit)

    def test_layout_failure_and_issue_edit_leave_files_unchanged(self):
        with self.assertRaises(ValueError):
            cli.import_one(self.root, 7, apply=True, rom=Path("original.nds"), fetch=self.fake_fetch, fit=lambda *a: (_ for _ in ()).throw(ValueError("Does not fit")))
        calls = []
        def edited(number, token=None):
            calls.append(number)
            return issue(field_body("Different.")) if len(calls) == 2 else issue()
        with self.assertRaises(ValueError):
            cli.import_one(self.root, 7, apply=True, rom=Path("original.nds"), fetch=edited, fit=self.fit)
        self.assertEqual(self.git("status", "--porcelain"), b"")

    def test_failed_replace_rolls_back_every_published_file(self):
        real = os.replace
        calls = []
        def fail_second(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError("Synthetic failure")
            return real(source, target)
        with patch.object(cli.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                cli.import_one(self.root, 7, apply=True, rom=Path("original.nds"), fetch=self.fake_fetch, fit=self.fit)
        self.assertEqual(self.git("status", "--porcelain"), b"")
        self.assertFalse(list(self.root.rglob(".issue-import-*")))

    def test_changed_checkout_during_fit_is_not_overwritten(self):
        def change(*args):
            self.write("translations/ready/batch_0001.json", b"user edit")
            return {}
        with self.assertRaises(ValueError):
            cli.import_one(self.root, 7, apply=True, rom=Path("original.nds"), fetch=self.fake_fetch, fit=change)
        self.assertEqual((self.root / "translations/ready/batch_0001.json").read_bytes(), b"user edit")

    def test_failed_rollback_keeps_the_original_backup_for_recovery(self):
        original_csv = (self.root / "csv/ready/batch_0001.csv").read_bytes()
        real, calls = os.replace, []
        def failed_write_and_restore(source, target):
            calls.append(target)
            if len(calls) in {2, 3}:
                raise OSError("Synthetic persistent failure")
            return real(source, target)
        with patch.object(cli.os, "replace", side_effect=failed_write_and_restore):
            with self.assertRaisesRegex(ValueError, "backups were retained"):
                cli.import_one(self.root, 7, apply=True, rom=Path("original.nds"), fetch=self.fake_fetch, fit=self.fit)
        backups = list(self.root.rglob(".issue-import-*.tmp"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original_csv)

    def test_out_of_order_issues_work_but_replay_and_duplicate_wording_do_not(self):
        first, _ = issues.propose(self.root, issue(field_body("First."), 10))
        for name, data in first.items():
            self.write(name, data)
        second, _ = issues.propose(self.root, issue(field_body("Second."), 7))
        self.assertEqual([e["number"] for e in json.loads(second[issues.LEDGER])["entries"]], [7, 10])
        for name, data in second.items():
            self.write(name, data)
        with self.assertRaises(ValueError):
            issues.propose(self.root, issue(field_body("Third."), 7))
        with self.assertRaises(ValueError):
            issues.propose(self.root, issue(field_body("First."), 11))

    def test_bad_account_hash_pages_and_unsafe_text_are_rejected(self):
        variants = [issue(field_body().replace(HASH, "b" * 64)), issue(field_body("New\fpage")), issue(field_body("https://example.invalid")), issue(field_body("Old text.", "Only notes changed")), issue(field_body() + "\nAuthor: someone-else")]
        bot = issue(); bot["user"]["type"] = "Bot"; variants.append(bot)
        other = issue(); other["repository_url"] += "-other"; variants.append(other)
        pull = issue(); pull["pull_request"] = {}; variants.append(pull)
        for value in variants:
            with self.subTest(value=value["number"]):
                with self.assertRaises(ValueError):
                    issues.propose(self.root, value)

    def test_image_label_uses_the_same_issue_credit_route(self):
        image = copy.deepcopy(self.batch)
        image["batch_id"] = "gin_tama_names"
        image["records"][0].update(id="image_label_1", english="OLD")
        self.write("translations/graphics/gin_tama_names.json", issues.encoded(image))
        self.write("csv/graphics/gin_tama_names.csv", csv_render(image).encode())
        index = json.loads((self.root / "reference/record_index.json").read_text())
        index["records"].append({"id": "image_label_1", "source_words_sha256": HASH, "page_breaks": 0})
        self.write("reference/record_index.json", issues.encoded(index))
        body = field_body("NEW").replace("msb_00000010", "image_label_1")
        outputs, entry = issues.propose(self.root, issue(body))
        self.assertEqual(entry["record"]["path"], "translations/graphics/gin_tama_names.json")
        self.assertIn("csv/graphics/gin_tama_names.csv", outputs)
        colored = field_body("[blue]NEW[/color]").replace("msb_00000010", "image_label_1")
        with self.assertRaisesRegex(ValueError, "image labels"):
            issues.propose(self.root, issue(colored))

    def test_field_issue_requires_indexed_colors_and_original_page_order(self):
        index = json.loads((self.root / "reference/record_index.json").read_text())
        index["records"][0].update(page_breaks=1, control_sequence=[0xFF82, 0xFF84, 0xFF72])
        self.write("reference/record_index.json", issues.encoded(index))
        valid = "[blue]Forest Trail[/color].\fGo there."
        outputs, entry = issues.propose(self.root, issue(field_body(valid)))
        self.assertIn("translations/ready/batch_0001.json", outputs)
        self.assertEqual(entry["record"]["id"], "msb_00000010")
        for text in ("Forest Trail.\fGo there.", "[red]Forest Trail[/color].\fGo there.",
                     "Go there.\f[blue]Forest Trail[/color]."):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "source color controls"):
                issues.propose(self.root, issue(field_body(text)))

    def test_ordered_parts_hash_and_linked_paths_cannot_be_substituted(self):
        self.assertNotEqual(issues.english_hash(["ab", "c"]), issues.english_hash(["a", "bc"]))
        original = Path.is_symlink
        def linked(path):
            return path == self.root / issues.LEDGER or original(path)
        with patch.object(Path, "is_symlink", linked):
            with self.assertRaises(ValueError):
                issues.propose(self.root, issue())
        with self.assertRaises(ValueError):
            issues.NoRedirects().redirect_request(None, None, 302, "", {}, "https://example.invalid/")

    def test_field_suggestions_keep_supported_typographic_punctuation(self):
        parsed = issues.parse_suggestion(field_body("I\u2019ll go.", "Gintoki\u2019s reply."))
        self.assertEqual(parsed["value"], "I\u2019ll go.")

    def test_private_rom_fit_accepts_field_text_that_requires_packing(self):
        rom = os.environ.get("GINTAMA_TEST_ROM")
        if not rom:
            self.skipTest("Set GINTAMA_TEST_ROM for packed-field issue fit validation")
        root = Path(__file__).resolve().parents[1]
        indexed = json.loads((root / "reference/record_index.json").read_text())["records"]
        row = next(r for r in indexed if r["id"] == "msb_00014BE4")
        text = "Hey, Gin! Kagura! What brings you here today?"
        body = field_body(text).replace("msb_00000010", row["id"]).replace(HASH, row["source_words_sha256"])
        outputs, entry = issues.propose(root, issue(body, 991001))
        proof = cli.validate_fit(root, outputs, entry, Path(rom))
        self.assertTrue(proof["record_fit_checked"])
        self.assertFalse(proof["rom_written"])

    def test_opening_parts_are_imported_without_reordering(self):
        scene = {"format": "gintama-cutscene-v1", "script": "adventure/script/s01.msb", "scope": "Example", "source_msb_sha256": "c" * 64, "source_cdb_sha256": "d" * 64, "notes": [], "messages": [{"offset": 16, "source_words_sha256": HASH, "parts": ["Old."]}]}
        self.write("reference/opening_scene.json", issues.encoded(scene))
        body = f'Opening cutscene translation suggestion\n\nID: s01_00000010\nScript: adventure/script/s01.msb\nSource SHA-256: {HASH}\nEnglish parts (JSON):\n["New."]\n\nKeep the parts in this order. No source game text is included.\nThis suggestion needs maintainer review and a local ROM build.'
        outputs, entry = issues.propose(self.root, issue(body))
        self.assertEqual(json.loads(outputs["reference/opening_scene.json"])["messages"][0]["parts"], ["New."])
        self.assertEqual(entry["record"]["id"], "s01_00000010")
        bad = copy.deepcopy(scene); bad["messages"][0]["parts"] = [""]
        with self.assertRaises(ValueError):
            issues.validate_script_changes("reference/opening_scene.json", scene, bad, root=self.root)

    def test_new_opening_record_requires_trusted_index_and_keeps_existing_rows(self):
        from credits import measure_reference_records
        scene = {"format": "gintama-cutscene-v1", "script": "adventure/script/s01.msb", "scope": "Example", "source_msb_sha256": "c" * 64, "source_cdb_sha256": "d" * 64, "notes": [], "messages": [{"offset": 16, "source_words_sha256": HASH, "parts": ["Old."]}]}
        after = copy.deepcopy(scene)
        after["messages"].append({"offset": 32, "source_words_sha256": "b" * 64, "parts": ["New line!"]})
        validate = lambda value: issues.validate_script_changes("reference/opening_scene.json", scene, value, root=self.root)
        with self.assertRaises(ValueError):
            validate(after)
        self.write("graphics/ui_recipes.json", issues.encoded({"source_rom_sha256": "e" * 64}))
        self.write("reference/opening_index.json", issues.encoded({"format": "gintama-opening-index-v1", "source_rom_sha256": "e" * 64, "script": scene["script"], "source_msb_sha256": "c" * 64, "source_cdb_sha256": "d" * 64, "records": [[16, 30, HASH, 1], [32, 48, "b" * 64, 1]]}))
        validate(after)
        measured = measure_reference_records("reference/opening_scene.json", scene, after)
        self.assertEqual((measured[0]["id"], measured[0]["kind"]), ("s01_00000020", "new"))
        for change in (
            lambda rows: rows.pop(0),
            lambda rows: rows.reverse(),
            lambda rows: rows[-1].update(offset=34),
            lambda rows: rows[-1].update(source_words_sha256=HASH),
            lambda rows: rows[-1]["parts"].append("Extra"),
            lambda rows: rows[-1].update(parts=[""]),
        ):
            bad = copy.deepcopy(after)
            change(bad["messages"])
            with self.assertRaises(ValueError):
                validate(bad)

    def test_new_battle_record_must_match_trusted_index(self):
        script = "battle/script/message/example.msb"
        pack = {"format": "gintama-battle-v1", "notes": [], "scripts": [{"script": script, "source_msb_sha256": "c" * 64, "source_cdb_sha256": "d" * 64, "record_count": 1, "messages": []}]}
        self.write("reference/battle.json", issues.encoded(pack))
        self.write("graphics/ui_recipes.json", issues.encoded({"source_rom_sha256": "e" * 64}))
        self.write("reference/battle_index.json", issues.encoded({"format": "gintama-battle-index-v1", "source_rom_sha256": "e" * 64, "scripts": [{"script": script, "source_msb_sha256": "c" * 64, "records": [[4, 20, HASH, 1]]}]}))
        body = f'Battle translation suggestion\n\nID: message_example_00000004\nScript: {script}\nOffset: 4\nSource SHA-256: {HASH}\nEnglish parts (JSON):\n["Try me!"]\n\nKeep the parts in order. No source game text is included.\nA maintainer must review the English and test a local build.'
        outputs, entry = issues.propose(self.root, issue(body))
        self.assertEqual(entry["record"]["kind"], "new")
        self.assertEqual(json.loads(outputs["reference/battle.json"])["scripts"][0]["messages"][0]["parts"], ["Try me!"])
        with self.assertRaises(ValueError):
            issues.propose(self.root, issue(body.replace(HASH, "f" * 64)))


if __name__ == "__main__":
    unittest.main()
