# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import base64
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from credits import (
    FORMAT,
    add_merged,
    measure_reference_records,
    measure_records,
    read_ledger,
    render,
    text_measurement,
    valid_entry,
    verified_entry,
)

BASE, HEAD, MERGE_BASE = "a" * 40, "b" * 40, "c" * 40
PATH = "translations/ready/batch_0001.json"


def batch(*texts):
    return {
        "format": "gintama-community-translation-v1",
        "batch_id": "batch_0001",
        "records": [
            {
                "id": f"msb_{index:08X}",
                "source_words_sha256": "a" * 64,
                "english": text,
                "translator_note": None,
            }
            for index, text in enumerate(texts)
        ],
    }


def pr():
    return {
        "number": 22,
        "merged": True,
        "merged_at": "2026-10-21T12:00:00Z",
        "user": {"login": "translator"},
        "base": {"ref": "staging", "sha": BASE},
        "head": {"sha": HEAD},
    }


def issue_entry(number=7, login="issue-translator", user_id=17):
    return {
        "number": number,
        "login": login,
        "user_id": user_id,
        "updated_at": "2026-10-29T12:00:00Z",
        "body_sha256": "b" * 64,
        "record": {
            "path": PATH, "id": "msb_00000000",
            "source_words_sha256": "a" * 64, "english_sha256": "c" * 64,
            "kind": "new", "words": 3, "characters": 15,
        },
    }


def issue_ledger(*entries):
    return {"format": "gintama-issue-imports-v1", "entries": list(entries)}


def opening(*parts):
    return {
        "format": "gintama-cutscene-v1", "script": "adventure/script/s01.msb",
        "scope": "Opening", "source_msb_sha256": "a" * 64,
        "source_cdb_sha256": "b" * 64, "notes": [],
        "messages": [{"offset": 60, "source_words_sha256": "c" * 64,
                      "parts": list(parts)}],
    }


def battle(*parts):
    return {
        "format": "gintama-battle-v1", "notes": [],
        "scripts": [{
            "script": "battle/script/character/ayame.msb",
            "source_msb_sha256": "a" * 64, "source_cdb_sha256": "b" * 64,
            "record_count": 1,
            "messages": [{"offset": 4, "source_words_sha256": "c" * 64,
                          "parts": list(parts)}],
        }],
    }


class CreditMeasurementTests(unittest.TestCase):
    def test_new_and_revised_text_have_separate_counts(self):
        rows = measure_records(
            batch(None, "Old line."), batch("Don't panic!\fGin-san?", "A revised line.")
        )
        self.assertEqual(
            rows,
            [
                {"id": "msb_00000000", "kind": "new", "words": 4, "characters": 19},
                {
                    "id": "msb_00000001",
                    "kind": "revision",
                    "words": 3,
                    "characters": 13,
                },
            ],
        )

    def test_notes_layout_unchanged_text_and_deletions_do_not_count(self):
        before = batch("Same line.", "Old line.", None, "Hello\fworld")
        after = batch("Same line.", None, None, " Hello\n world ")
        after["records"][0]["translator_note"] = "I checked this line."
        self.assertEqual(measure_records(before, after), [])

    def test_blank_strings_cannot_bypass_translation_validation(self):
        with self.assertRaises(ValueError):
            measure_records(batch(" \n\f"), batch("A line."))

    def test_punctuation_counts_characters_without_inventing_words(self):
        result = measure_records(batch(None), batch("..."))
        self.assertEqual((result[0]["words"], result[0]["characters"]), (0, 3))

    def test_color_markers_do_not_inflate_word_or_character_credit(self):
        result = text_measurement(None, "Take [blue]Forest Trail[/color].", "msb_00000000")
        self.assertEqual((result["words"], result["characters"]), (3, 16))
        self.assertIsNone(text_measurement("Forest Trail", "[blue]Forest Trail[/color]",
                                          "msb_00000000"))

    def test_ids_hashes_record_order_and_schema_cannot_change(self):
        for mutate in (
            lambda data: data["records"][0].update(id="msb_wrong"),
            lambda data: data["records"][0].update(source_words_sha256="b" * 64),
            lambda data: data["records"].append(data["records"][0].copy()),
            lambda data: data["records"][0].update(credit_words=999),
            lambda data: data.update(batch_id="other"),
        ):
            with self.subTest(mutate=mutate):
                before, after = batch(None), batch("A line.")
                mutate(after)
                with self.assertRaises(ValueError):
                    measure_records(before, after)

    def test_duplicate_ids_rejected_even_when_text_unchanged(self):
        data = batch("One.", "Two.")
        data["records"][1]["id"] = data["records"][0]["id"]
        with self.assertRaises(ValueError):
            measure_records(data, copy.deepcopy(data))

    def test_credit_table_distinguishes_revision_from_new_translation(self):
        ledger = {"format": FORMAT, "entries": []}
        records = measure_records(
            batch(None, "Old line."), batch("A new line.", "An edited line.")
        )
        self.assertTrue(add_merged(ledger, pr(), records, MERGE_BASE))
        another = pr()
        another["number"] = 23
        another["user"]["login"] = "TRANSLATOR"
        self.assertTrue(add_merged(ledger, another, records, MERGE_BASE))
        self.assertFalse(add_merged(ledger, another, records, MERGE_BASE))
        text = render(ledger)
        self.assertIn("**Contributors: 1 · Merged translation PRs: 2 · Accepted issues: 0**", text)
        self.assertIn("| @translator | 2 | 0 | 1 | 1 | 6 / 6 |", text)
        self.assertIn("not newly translated words", text)
        self.assertIn("not a claim of sole authorship", text)

    def test_part_measurement_uses_word_boundaries_and_ignores_layout(self):
        self.assertEqual(text_measurement(None, ["Another ", "Gin Tama", " incident", ". Same old quarrel."], "s01_0000003c")["words"], 7)
        with self.assertRaisesRegex(ValueError, "links"):
            text_measurement(None, ["example", ".com"], "s01_0000003c")
        self.assertEqual(text_measurement(None, ["Don't panic!", "Gin-san?"], "s01_0000003c"),
                         {"id": "s01_0000003c", "kind": "new", "words": 4, "characters": 19})
        self.assertIsNone(text_measurement(["Hello\nworld", "Again."],
                                          ["Hello world", " Again. "], "s01_0000003c"))
        self.assertIsNone(text_measurement("Old text.", None, "msb_00000000"))
        with self.assertRaises(ValueError):
            text_measurement(None, ["Hello", 1], "s01_0000003c")
        with self.assertRaisesRegex(ValueError, "reserved instruction/role marker"):
            text_measurement(None, ["<|im_", "start|>"], "s01_0000003c")

    def test_reference_measurement_uses_namespaced_ids_and_preserves_inventory(self):
        for path, factory, identifier in (
            ("reference/opening_scene.json", opening, "s01_0000003c"),
            ("reference/battle.json", battle,
             "battle:battle/script/character/ayame.msb:00000004"),
        ):
            with self.subTest(path=path):
                self.assertEqual(measure_reference_records(path, factory("Old line."),
                                                          factory("A real change.")),
                                 [{"id": identifier, "kind": "revision", "words": 3,
                                   "characters": 12}])
                self.assertEqual(measure_reference_records(path, factory("Hello\nworld"),
                                                          factory(" Hello world ")), [])
                altered = factory("A new line.")
                messages = (altered["messages"] if path.endswith("opening_scene.json")
                            else altered["scripts"][0]["messages"])
                messages[0]["source_words_sha256"] = "d" * 64
                with self.assertRaisesRegex(ValueError, "Immutable"):
                    measure_reference_records(path, factory("Old line."), altered)

    def test_battle_measurement_counts_append_only_new_messages(self):
        before = battle("Old line.")
        before["scripts"][0]["record_count"] = 2
        after = copy.deepcopy(before)
        after["scripts"][0]["messages"].append({
            "offset": 40, "source_words_sha256": "d" * 64, "parts": ["A new line."],
        })
        self.assertEqual(measure_reference_records("reference/battle.json", before, after), [{
            "id": "battle:battle/script/character/ayame.msb:00000028",
            "kind": "new", "words": 3, "characters": 9,
        }])
        removed = copy.deepcopy(after)
        removed["scripts"][0]["messages"].pop(0)
        with self.assertRaisesRegex(ValueError, "Immutable"):
            measure_reference_records("reference/battle.json", before, removed)

    def test_issue_creator_is_credited_with_record_provenance(self):
        text = render({"format": FORMAT, "entries": []}, issue_ledger(issue_entry()))
        self.assertIn("Contributors: 1 · Merged translation PRs: 0 · Accepted issues: 1", text)
        self.assertIn("| @issue-translator (ID 17) | 0 | 1 | 1 | 0 | 3 / 0 | 15 / 0 |", text)
        self.assertIn("[Issue #7]", text)
        self.assertIn("/issues/7)", text)
        self.assertIn("`msb_00000000` | new | 3 | 15 |", text)
        self.assertNotIn("@maintainer", text)

    def test_issue_account_ids_survive_renames_and_separate_reused_handles(self):
        renamed = issue_entry(8, "new-handle", 17)
        renamed["record"].update(kind="revision", english_sha256="d" * 64)
        text = render({"format": FORMAT, "entries": []},
                      issue_ledger(issue_entry(), renamed))
        self.assertIn("**Contributors: 1", text)
        self.assertIn("| 0 | 2 | 1 | 1 | 3 / 3 | 15 / 15 |", text)
        text = render({"format": FORMAT, "entries": []},
                      issue_ledger(issue_entry(), issue_entry(8, "issue-translator", 99)))
        self.assertIn("**Contributors: 2", text)
        self.assertIn("@issue-translator (ID 17)", text)
        self.assertIn("@issue-translator (ID 99)", text)

    def test_duplicate_issue_receipts_rejected_and_empty_issues_are_compatible(self):
        ledger = {"format": FORMAT, "entries": []}
        self.assertEqual(render(ledger), render(ledger, issue_ledger()))
        with self.assertRaisesRegex(ValueError, "Duplicate credited issue"):
            render(ledger, issue_ledger(issue_entry(), issue_entry()))

    def test_verified_pr_account_id_can_share_issue_totals_but_legacy_handles_do_not(self):
        ledger = {"format": FORMAT, "entries": []}
        proposal = pr()
        proposal["user"].update(login="issue-translator", id=17)
        add_merged(ledger, proposal, measure_records(batch(None), batch("A line.")))
        self.assertEqual(ledger["entries"][0]["user_id"], 17)
        text = render(ledger, issue_ledger(issue_entry()))
        self.assertIn("**Contributors: 1 · Merged translation PRs: 1 · Accepted issues: 1", text)
        self.assertIn("| @issue-translator (ID 17) | 1 | 1 | 1 | 0 |", text)
        ledger["entries"][0].pop("user_id")
        self.assertIn("**Contributors: 2", render(ledger, issue_ledger(issue_entry())))

    def test_strict_ledger_and_empty_legacy_migration(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.json"
            path.write_text(
                '{"format":"gintama-translation-credits-v1","entries":[]}',
                encoding="utf-8",
            )
            self.assertEqual(read_ledger(path), {"format": FORMAT, "entries": []})
            for payload in (
                '{"format":"gintama-translation-credits-v1","entries":[{}]}',
                '{"format":"gintama-translation-credits-v2","entries":[],"entries":[]}',
            ):
                path.write_text(payload, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_ledger(path)

    def test_ledger_rejects_forged_counts_duplicates_and_unknown_fields(self):
        ledger = {"format": FORMAT, "entries": []}
        add_merged(ledger, pr(), measure_records(batch(None), batch("A line.")))
        entry = ledger["entries"][0]
        for mutate in (
            lambda row: row.update(extra="untrusted"),
            lambda row: row.update(head_sha="main"),
            lambda row: row.update(merged_at="2026-10-21T12:00:00"),
            lambda row: row.update(user_id=True),
            lambda row: row["records"][0].update(words=True),
            lambda row: row["records"][0].update(characters=0),
            lambda row: row["records"].append(row["records"][0].copy()),
        ):
            with self.subTest(mutate=mutate):
                altered = copy.deepcopy(entry)
                mutate(altered)
                with self.assertRaises(ValueError):
                    valid_entry(altered)

    def test_append_only_ledger_rejects_rewriting_or_removing_an_old_credit(self):
        from check_credits import validate
        import test_project

        fixture = test_project.Fixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        ledger = {"format": FORMAT, "entries": []}
        records = measure_records(batch(None), batch("A line."))
        add_merged(ledger, pr(), records)
        fixture.write(fixture.base, "credits/merged_prs.json", ledger)
        (fixture.base / "TRANSLATORS.md").write_text(render(ledger), encoding="utf-8")
        later = pr()
        later["number"] = 23
        add_merged(ledger, later, records)
        for mutate in (
            lambda data: data["entries"][0].update(login="someone-else"),
            lambda data: data["entries"].pop(0),
        ):
            candidate = copy.deepcopy(ledger)
            mutate(candidate)
            fixture.write(fixture.candidate, "credits/merged_prs.json", candidate)
            (fixture.candidate / "TRANSLATORS.md").write_text(
                render(candidate), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                validate(fixture.base, fixture.candidate)

    def test_credits_pr_cannot_smuggle_an_executable_flag_change(self):
        from check_credits import validate
        import os
        import test_project

        fixture = test_project.Fixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        ledger = {"format": FORMAT, "entries": []}
        add_merged(ledger, pr(), measure_records(batch(None), batch("A line.")))
        fixture.write(fixture.candidate, "credits/merged_prs.json", ledger)
        (fixture.candidate / "TRANSLATORS.md").write_text(
            render(ledger), encoding="utf-8"
        )
        target = fixture.candidate / "README.md"
        original = Path.stat

        def executable(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == target:
                values = list(result)
                values[0] |= 0o111
                return os.stat_result(values)
            return result

        with (
            patch.object(Path, "stat", executable),
            self.assertRaisesRegex(ValueError, "executable permissions"),
        ):
            validate(fixture.base, fixture.candidate)

    def test_credits_pr_preserves_issue_credits_and_requires_combined_rendering(self):
        from check_credits import validate
        import test_project

        fixture = test_project.Fixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        issues = issue_ledger(issue_entry())
        before = {"format": FORMAT, "entries": []}
        after = copy.deepcopy(before)
        add_merged(after, pr(), measure_records(batch(None), batch("A line.")))
        for root, ledger in ((fixture.base, before), (fixture.candidate, after)):
            fixture.write(root, "credits/merged_prs.json", ledger)
            fixture.write(root, "credits/issue_imports.json", issues)
            (root / "TRANSLATORS.md").write_text(render(ledger, issues), encoding="utf-8")
        self.assertEqual(validate(fixture.base, fixture.candidate)["new_credits"], 1)
        (fixture.candidate / "TRANSLATORS.md").write_text(render(after), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "trusted renderer"):
            validate(fixture.base, fixture.candidate)

    def test_credits_pr_cannot_reassign_an_accepted_issue(self):
        from check_credits import validate
        import test_project

        fixture = test_project.Fixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        before = {"format": FORMAT, "entries": []}
        after = copy.deepcopy(before)
        add_merged(after, pr(), measure_records(batch(None), batch("A line.")))
        for root, ledger in ((fixture.base, before), (fixture.candidate, after)):
            issues = issue_ledger(issue_entry())
            if root == fixture.candidate:
                issues["entries"][0]["login"] = "maintainer"
            fixture.write(root, "credits/merged_prs.json", ledger)
            fixture.write(root, "credits/issue_imports.json", issues)
            (root / "TRANSLATORS.md").write_text(render(ledger, issues), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must update only"):
            validate(fixture.base, fixture.candidate)

    def test_staging_promotion_accepts_append_only_new_credit_metrics(self):
        from validate_promotion import validate
        import test_project

        fixture = test_project.Fixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        ledger = {"format": FORMAT, "entries": []}
        add_merged(ledger, pr(), measure_records(batch(None), batch("A line.")))
        fixture.write(fixture.candidate, "credits/merged_prs.json", ledger)
        (fixture.candidate / "TRANSLATORS.md").write_text(
            render(ledger), encoding="utf-8"
        )
        self.assertEqual(validate(fixture.base, fixture.candidate)["staged_credits"], 1)


class RemoteCreditTests(unittest.TestCase):
    def response(self, path, token, repo):
        self.calls.append(path)
        self.assertEqual(repo, "owner/repo")
        if path == "pulls/22/files?per_page=100&page=1":
            return self.files
        if path == f"compare/{BASE}...{HEAD}":
            return {"merge_base_commit": {"sha": MERGE_BASE}}
        for sha, data in ((MERGE_BASE, self.before), (HEAD, self.after)):
            if path == f"contents/{self.path}?ref={sha}":
                raw = json.dumps(data).encode()
                return {
                    "type": "file",
                    "path": self.path,
                    "encoding": "base64",
                    "size": len(raw),
                    "content": base64.b64encode(raw).decode(),
                }
        raise AssertionError("Unexpected API request: " + path)

    def setUp(self):
        self.calls = []
        self.path = PATH
        self.before, self.after = batch(None), batch("A real change.")
        self.files = [
            {"filename": PATH, "status": "modified"},
            {"filename": "csv/ready/batch_0001.csv", "status": "modified"},
        ]

    def verified(self, proposal=None):
        with patch("credits.github", side_effect=self.response):
            return verified_entry(
                pr() if proposal is None else proposal, "test", "owner/repo"
            )

    def test_remote_counts_use_merge_base_and_head_content(self):
        entry = self.verified()
        self.assertEqual((entry["base_sha"], entry["head_sha"]), (MERGE_BASE, HEAD))
        self.assertEqual(entry["records"][0]["words"], 3)
        self.assertEqual(entry["records"][0]["characters"], 12)
        self.assertIn(f"contents/{PATH}?ref={MERGE_BASE}", self.calls)
        self.assertIn(f"contents/{PATH}?ref={HEAD}", self.calls)

    def test_new_pr_credits_keep_the_verified_numeric_account_id(self):
        proposal = pr()
        proposal["user"]["id"] = 123
        self.assertEqual(self.verified(proposal)["user_id"], 123)
        proposal["user"]["id"] = True
        with self.assertRaisesRegex(ValueError, "account ID"):
            self.verified(proposal)

    def test_note_only_pr_has_no_text_credit(self):
        self.after = copy.deepcopy(self.before)
        self.after["records"][0]["translator_note"] = "Checked against the scene."
        self.assertIsNone(self.verified())

    def test_issue_import_pr_does_not_credit_the_maintainer_again(self):
        self.files.append({"filename": "credits/issue_imports.json", "status": "modified"})
        proposal = pr()
        proposal["user"]["login"] = "maintainer"
        self.assertIsNone(self.verified(proposal))
        self.assertFalse(any(path.startswith("contents/") for path in self.calls))
        self.assertFalse(any(path.startswith("compare/") for path in self.calls))

    def test_opening_and_battle_prs_measure_verified_parts(self):
        for path, factory, identifier in (
            ("reference/opening_scene.json", opening, "s01_0000003c"),
            ("reference/battle.json", battle,
             "battle:battle/script/character/ayame.msb:00000004"),
        ):
            with self.subTest(path=path):
                self.path = path
                self.before, self.after = factory("Old line."), factory("A real change.")
                self.files = [{"filename": path, "status": "modified"}]
                entry = self.verified()
                self.assertEqual(entry["records"], [{"id": identifier, "kind": "revision",
                                                    "words": 3, "characters": 12}])
                valid_entry(entry)

    def test_new_battle_pr_credit_requires_the_trusted_rom_index(self):
        self.path = "reference/battle.json"
        self.files = [{"filename": self.path, "status": "modified"}]
        self.before = battle("Old line.")
        self.before["scripts"][0]["record_count"] = 2
        self.after = copy.deepcopy(self.before)
        self.after["scripts"][0]["messages"].append({
            "offset": 40, "source_words_sha256": "d" * 64, "parts": ["A new line."],
        })
        index = {
            "format": "gintama-battle-index-v1", "source_rom_sha256": "e" * 64,
            "scripts": [{"script": "battle/script/character/ayame.msb",
                         "source_msb_sha256": "a" * 64,
                         "records": [[4, 38, "c" * 64, 1], [40, 78, "d" * 64, 1]]}],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reference").mkdir()
            (root / "graphics").mkdir()
            (root / "graphics/ui_recipes.json").write_text(
                json.dumps({"source_rom_sha256": "e" * 64}), encoding="utf-8"
            )
            (root / "reference/battle_index.json").write_text(json.dumps(index), encoding="utf-8")
            with patch("credits.ROOT", root):
                entry = self.verified()
                self.assertEqual(entry["records"], [{
                    "id": "battle:battle/script/character/ayame.msb:00000028",
                    "kind": "new", "words": 3, "characters": 9,
                }])
                self.after["scripts"][0]["messages"][-1]["source_words_sha256"] = "f" * 64
                with self.assertRaisesRegex(ValueError, "trusted index"):
                    self.verified()

    def test_code_mixed_pr_and_renames_additions_deletions_not_credited(self):
        for status in ("added", "removed", "renamed"):
            self.files[0]["status"] = status
            self.assertIsNone(self.verified())
        self.files[0]["status"] = "modified"
        self.files.append({"filename": "tools/credits.py", "status": "modified"})
        self.assertIsNone(self.verified())
        self.assertFalse(any(path.startswith("contents/") for path in self.calls))

    def test_unmerged_and_main_prs_not_credited(self):
        for proposal in (dict(pr(), merged=False), dict(pr(), merged_at=None)):
            self.assertIsNone(self.verified(proposal))
        proposal = pr()
        proposal["base"]["ref"] = "main"
        self.assertIsNone(self.verified(proposal))
        self.assertEqual(self.calls, [])

    def test_duplicate_pr_file_path_rejected(self):
        self.files.append(self.files[0].copy())
        with self.assertRaises(ValueError):
            self.verified()

    def test_untrusted_contents_path_or_oversized_size_rejected(self):
        original = self.response
        for mutation in (
            {"path": "README.md"},
            {"size": 2_000_001},
            {"size": 1},
            {"encoding": "none"},
        ):

            def response(path, token, repo):
                data = original(path, token, repo)
                if path.startswith("contents/"):
                    data.update(mutation)
                return data

            with (
                self.subTest(mutation=mutation),
                patch("credits.github", side_effect=response),
            ):
                with self.assertRaises(ValueError):
                    verified_entry(pr(), "test", "owner/repo")

    def test_remote_credit_validator_recomputes_counts(self):
        from check_credits import validate
        import test_project

        fixture = test_project.Fixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        ledger = {"format": FORMAT, "entries": [self.verified()]}
        fixture.write(fixture.candidate, "credits/merged_prs.json", ledger)
        (fixture.candidate / "TRANSLATORS.md").write_text(
            render(ledger), encoding="utf-8"
        )
        with (
            patch.dict(
                "os.environ",
                {"GITHUB_TOKEN": "test", "GITHUB_REPOSITORY": "owner/repo"},
            ),
            patch("check_credits.github", return_value=pr()),
            patch("credits.github", side_effect=self.response),
        ):
            self.assertEqual(
                validate(fixture.base, fixture.candidate, True)["new_credits"], 1
            )
            ledger["entries"][0]["records"][0]["words"] += 1
            fixture.write(fixture.candidate, "credits/merged_prs.json", ledger)
            (fixture.candidate / "TRANSLATORS.md").write_text(
                render(ledger), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ValueError, "verified merged-PR English changes"
            ):
                validate(fixture.base, fixture.candidate, True)


if __name__ == "__main__":
    unittest.main()
