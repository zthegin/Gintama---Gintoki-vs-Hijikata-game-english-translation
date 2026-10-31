import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_issue_import as imports
import validate_promotion as promotion


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def receipt(number=42):
    return {
        "number": number,
        "login": "translator-one",
        "user_id": 123,
        "updated_at": "2026-01-01T10:00:00Z",
        "body_sha256": "a" * 64,
        "record": {
            "path": "translations/ready/batch_0001.json",
            "id": "msb_00000010",
            "source_words_sha256": "b" * 64,
            "english_sha256": hashlib.sha256(b'"Hello."').hexdigest(),
            "kind": "new",
            "words": 1,
            "characters": 6,
        },
    }


def ledger(entries=()):
    return {"format": "gintama-issue-imports-v1", "entries": list(entries)}


class ImportValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name) / "base"
        self.candidate = Path(temporary.name) / "candidate"
        self.entry = receipt()
        self.outputs = {
            self.entry["record"]["path"]: b'{"english":"Hello."}\n',
            "csv/ready/batch_0001.csv": b"english\nHello.\n",
            imports.LEDGER: encoded(ledger([self.entry])),
            imports.DOCUMENT: b"# Translators\nOne verified issue.\n",
        }
        for root in (self.base, self.candidate):
            for name in self.outputs:
                self.write(root, name, b"old data\n")
            self.write(root, imports.LEDGER, encoded(ledger()))
            self.write(root, "README.md", b"Trusted source.\n")
        for name, payload in self.outputs.items():
            self.write(self.candidate, name, payload)
        self.fetch = Mock(return_value={
            "number": 42,
            "updated_at": "2026-01-02T10:00:00Z",
            "body": "Current public suggestion",
        })
        self.propose = self.enterContext(
            patch.object(imports, "propose", return_value=(self.outputs, self.entry))
        )
        self.enterContext(patch.object(imports, "publication_check", return_value=[]))

    def write(self, root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def check(self, **kwargs):
        return imports.validate(self.base, self.candidate, fetch=self.fetch, **kwargs)

    def test_exact_import_uses_fresh_issue_and_keeps_saved_timestamp(self):
        result = self.check(expected_number=42, token="synthetic")
        self.assertEqual(result["english_changes"], 1)
        self.assertEqual(result["issue_number"], 42)
        self.assertFalse(result["layout_verified"])
        self.fetch.assert_called_once_with(42, token="synthetic")
        self.assertEqual(self.propose.call_args.args[0], self.base)
        self.assertEqual(
            self.propose.call_args.args[1]["updated_at"], self.entry["updated_at"]
        )

    def test_crlf_export_matches_canonical_lf_outputs(self):
        for name, payload in self.outputs.items():
            self.write(self.candidate, name, payload.replace(b"\n", b"\r\n"))
        self.assertEqual(self.check()["changed_files"], 4)

    def test_different_branch_number_stops_before_fetch(self):
        with self.assertRaisesRegex(ValueError, "branch number"):
            self.check(expected_number=99)
        self.fetch.assert_not_called()

    def test_edited_body_author_and_forged_counts_are_rejected(self):
        for field, value in (("body_sha256", "c" * 64), ("login", "someone-else"), ("user_id", 999)):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.entry)
                changed[field] = value
                self.propose.return_value = (self.outputs, changed)
                with self.assertRaisesRegex(ValueError, "receipt differs"):
                    self.check()
        changed = copy.deepcopy(self.entry)
        changed["record"]["words"] += 1
        self.propose.return_value = (self.outputs, changed)
        with self.assertRaisesRegex(ValueError, "receipt differs"):
            self.check()

    def test_old_receipt_cannot_be_edited_or_removed(self):
        old = receipt(7)
        old["record"]["id"] = "msb_00000020"
        self.write(self.base, imports.LEDGER, encoded(ledger([old])))
        for retained in ([], [{**old, "login": "different-author"}]):
            with self.subTest(retained=retained):
                self.write(self.candidate, imports.LEDGER, encoded(ledger([*retained, self.entry])))
                with self.assertRaisesRegex(ValueError, "Old issue"):
                    self.check()
        self.fetch.assert_not_called()

    def test_requires_exactly_one_new_receipt(self):
        for entries in ([], [self.entry, receipt(43)]):
            with self.subTest(entries=len(entries)):
                self.write(self.candidate, imports.LEDGER, encoded(ledger(entries)))
                with self.assertRaises(ValueError):
                    self.check()
        self.fetch.assert_not_called()

    def test_future_or_newer_than_remote_timestamps_are_rejected(self):
        for value in ("2999-01-01T10:00:00Z", "2026-01-03T10:00:00Z"):
            with self.subTest(value=value):
                changed = {**self.entry, "updated_at": value}
                self.write(self.candidate, imports.LEDGER, encoded(ledger([changed])))
                with self.assertRaises(ValueError):
                    self.check()
        self.propose.assert_not_called()

    def test_extra_edits_added_deleted_files_and_csv_mismatch_fail(self):
        self.write(self.candidate, "README.md", b"Unrelated edit.\n")
        with self.assertRaises(ValueError):
            self.check()
        self.write(self.candidate, "README.md", b"Trusted source.\n")
        self.write(self.candidate, "extra.py", b"print('not trusted')\n")
        with self.assertRaisesRegex(ValueError, "add or delete"):
            self.check()
        (self.candidate / "extra.py").unlink()
        (self.candidate / "README.md").unlink()
        with self.assertRaisesRegex(ValueError, "add or delete"):
            self.check()
        self.write(self.candidate, "README.md", b"Trusted source.\n")
        self.write(self.candidate, "csv/ready/batch_0001.csv", b"Forged text.\n")
        with self.assertRaisesRegex(ValueError, "files differ"):
            self.check()

    def test_incomplete_or_extra_proposed_outputs_are_rejected(self):
        self.propose.return_value = ({imports.LEDGER: self.outputs[imports.LEDGER]}, self.entry)
        with self.assertRaisesRegex(ValueError, "changes do not match"):
            self.check()

    def test_executable_mode_change_is_rejected(self):
        target = self.candidate / "README.md"
        original = Path.stat

        def changed_mode(path, *args, **kwargs):
            stat = original(path, *args, **kwargs)
            if path == target:
                values = list(stat)
                values[0] ^= 0o111
                return os.stat_result(values)
            return stat

        with patch.object(Path, "stat", changed_mode):
            with self.assertRaisesRegex(ValueError, "executable permissions"):
                self.check()


class ImportRouteTests(unittest.TestCase):
    def test_import_route_requires_exact_branch_and_same_repository(self):
        self.assertEqual(imports.import_number("codex/issue-42", "Owner/Repo", "owner/repo"), 42)
        for branch, head in (
            ("codex/issue-42", "contributor/fork"),
            ("codex/issue-0", "owner/repo"),
            ("codex/issue-42-extra", "owner/repo"),
            ("main", "owner/repo"),
        ):
            self.assertIsNone(imports.import_number(branch, head, "owner/repo"))


class PromotionImportTests(unittest.TestCase):
    def setUp(self):
        import test_project

        self.fixture = test_project.Fixture()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base, self.candidate = self.fixture.base, self.fixture.candidate
        for root in (self.base, self.candidate):
            self.fixture.write(root, imports.LEDGER, ledger())

    def document(self, root, issues):
        from credits import render, read_ledger

        (root / imports.DOCUMENT).write_text(
            render(read_ledger(root / "credits/merged_prs.json"), issues),
            encoding="utf-8",
        )

    def test_append_only_issue_receipts_promote_with_combined_credits(self):
        issues = ledger([receipt()])
        self.fixture.write(self.candidate, imports.LEDGER, issues)
        self.document(self.candidate, issues)
        self.assertEqual(promotion.validate(self.base, self.candidate)["staged_issues"], 1)

    def test_published_issue_receipts_cannot_be_rewritten(self):
        old = ledger([receipt()])
        for root in (self.base, self.candidate):
            self.fixture.write(root, imports.LEDGER, old)
            self.document(root, old)
        changed = ledger([{**receipt(), "login": "different-translator"}])
        self.fixture.write(self.candidate, imports.LEDGER, changed)
        self.document(self.candidate, changed)
        with self.assertRaisesRegex(ValueError, "published issue receipts"):
            promotion.validate(self.base, self.candidate)

    def test_opening_edits_use_trusted_script_validator(self):
        name = "reference/opening_scene.json"
        old = {"format": "gintama-cutscene-v1", "script": "adventure/script/s01.msb", "scope": "Fixture", "notes": [], "source_msb_sha256": "a" * 64, "source_cdb_sha256": "b" * 64, "messages": [{"offset": 16, "source_words_sha256": "c" * 64, "parts": ["Old text."]}]}
        new = copy.deepcopy(old)
        new["messages"][0]["parts"] = ["New text."]
        self.fixture.write(self.base, name, old)
        self.fixture.write(self.candidate, name, new)
        with patch.object(promotion, "validate_script_changes") as validate_script:
            promotion.validate(self.base, self.candidate)
        validate_script.assert_called_once_with(name, old, new, root=self.base)
        with patch.object(
            promotion, "validate_script_changes", side_effect=ValueError("Source metadata changed")
        ):
            with self.assertRaisesRegex(ValueError, "Source metadata changed"):
                promotion.validate(self.base, self.candidate)

    def test_source_battle_index_changes_are_not_promotable(self):
        name = "reference/battle_index.json"
        self.fixture.write(self.base, name, {"records": []})
        self.fixture.write(self.candidate, name, {"records": [1]})
        with self.assertRaisesRegex(ValueError, "Only staged translations"):
            promotion.validate(self.base, self.candidate)


class ImportRoundTripTests(unittest.TestCase):
    def setUp(self):
        import test_project
        import issue_imports

        self.module = issue_imports
        self.fixture = test_project.Fixture()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base, self.candidate = self.fixture.base, self.fixture.candidate
        for root in (self.base, self.candidate):
            self.fixture.write(root, imports.LEDGER, ledger())
        self.issue = {
            "number": 42,
            "repository_url": f"https://api.github.com/repos/{issue_imports.REPOSITORY}",
            "html_url": f"https://github.com/{issue_imports.REPOSITORY}/issues/42",
            "user": {"type": "User", "login": "translator-one", "id": 123},
            "updated_at": "2026-01-01T10:00:00Z",
            "body": (
                f"Translation suggestion\n\nID: {test_project.RECORD['id']}\n"
                f"Source SHA-256: {test_project.HASH}\nEnglish (JSON escaped):\n"
                '"A natural line."\nNote: (none)\n\nNo source game text is included.'
            ),
        }
        outputs, _entry = issue_imports.propose(self.base, self.issue)
        for name, payload in outputs.items():
            (self.candidate / name).write_bytes(payload)

    def test_real_proposal_reconstructs_translation_csv_and_issue_credit(self):
        result = imports.validate(
            self.base, self.candidate,
            fetch=lambda number, token=None: self.issue,
            expected_number=42,
        )
        self.assertEqual(result["changed_files"], 4)
        document = (self.candidate / imports.DOCUMENT).read_text(encoding="utf-8")
        self.assertIn("@translator-one", document)
        self.assertIn("Issue #42", document)
        self.assertNotIn("@maintainer", document)

    def test_issue_edited_after_import_is_rejected_without_touching_files(self):
        before = {path: path.read_bytes() for path in self.candidate.rglob("*") if path.is_file()}
        changed = {**self.issue, "body": self.issue["body"].replace("A natural line.", "A changed line.")}
        with self.assertRaisesRegex(ValueError, "receipt differs"):
            imports.validate(
                self.base, self.candidate, fetch=lambda number, token=None: changed
            )
        self.assertEqual(before, {path: path.read_bytes() for path in before})


if __name__ == "__main__":
    unittest.main()
