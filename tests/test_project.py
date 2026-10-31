# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_credits import validate as validate_credits
from sync_csv import canonical_json, escape, import_csv, unescape
from sync_csv import render as csv_render
from validate_pr import check_repo, check_text, validate
from validate_promotion import validate as validate_promotion

from credits import (
    FORMAT as CREDITS_FORMAT,
)
from credits import (
    add_merged,
    collect_push_credits,
    measure_records,
    read_ledger,
    render,
)

HASH = "a" * 64
RECORD = {
    "id": "msb_00000100",
    "source_words_sha256": HASH,
    "english": None,
    "translator_note": None,
}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.base = Path(self.work.name) / "base"
        self.candidate = Path(self.work.name) / "candidate"
        for root in (self.base, self.candidate):
            for name in ("translations/ready", "csv/ready", "reference", "credits"):
                (root / name).mkdir(parents=True)
            self.write(
                root,
                "reference/record_index.json",
                {
                    "format": "reference",
                    "records": [
                        {
                            "id": RECORD["id"],
                            "source_words_sha256": HASH,
                            "page_breaks": 0,
                            "line_breaks": 0,
                        }
                    ],
                },
            )
            batch = {
                "format": "gintama-community-translation-v1",
                "batch_id": "batch_0001",
                "records": [RECORD.copy()],
            }
            self.write(root, "translations/ready/batch_0001.json", batch)
            (root / "csv/ready/batch_0001.csv").write_text(
                csv_render(batch), encoding="utf-8"
            )
            ledger = {"format": CREDITS_FORMAT, "entries": []}
            self.write(root, "credits/merged_prs.json", ledger)
            (root / "TRANSLATORS.md").write_text(render(ledger), encoding="utf-8")
            (root / "README.md").write_text("Trusted instructions\n", encoding="utf-8")

    def write(self, root, name, payload):
        (root / name).write_text(canonical_json(payload), encoding="utf-8")

    def edit(self, text, note=None):
        name = "translations/ready/batch_0001.json"
        data = json.loads((self.candidate / name).read_text(encoding="utf-8"))
        data["records"][0]["english"] = text
        data["records"][0]["translator_note"] = note
        self.write(self.candidate, name, data)
        (self.candidate / "csv/ready/batch_0001.csv").write_text(
            csv_render(data), encoding="utf-8"
        )


    def executable_modes(self, modes):
        original = Path.stat

        def changed(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path not in modes:
                return result
            fields = list(result)
            fields[0] = (result.st_mode & ~0o111) | modes[path]
            return os.stat_result(fields)

        return patch.object(Path, "stat", changed)


class ScriptExportTests(Fixture):
    def setUp(self):
        super().setUp()
        self.scene = {"format": "gintama-cutscene-v1", "script": "adventure/script/s01.msb", "scope": "Fixture", "notes": [], "source_msb_sha256": "b" * 64, "source_cdb_sha256": "c" * 64, "messages": [{"offset": 16, "source_words_sha256": HASH, "parts": ["Old line."]}]}
        for root in (self.base, self.candidate):
            (root / "graphics").mkdir()
            self.write(root, "graphics/ui_recipes.json", {"source_rom_sha256": "d" * 64})
            self.write(root, "reference/opening_scene.json", self.scene)
            self.write(root, "reference/opening_index.json", {"format": "gintama-opening-index-v1", "source_rom_sha256": "d" * 64, "script": self.scene["script"], "source_msb_sha256": "b" * 64, "source_cdb_sha256": "c" * 64, "records": [[16, 30, HASH, 1], [32, 48, "e" * 64, 1]]})

    def test_website_opening_export_is_an_ordinary_translation_pr(self):
        self.scene["messages"].append({"offset": 32, "source_words_sha256": "e" * 64, "parts": ["New line!"]})
        self.write(self.candidate, "reference/opening_scene.json", self.scene)
        self.assertEqual(validate(self.base, self.candidate)["english_changes"], 1)
        for name in ("README.md", "reference/opening_index.json"):
            path = self.candidate / name
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "Ordinary PRs"):
                validate(self.base, self.candidate)
            path.write_bytes(original)
        self.scene["messages"][-1]["offset"] = 34
        self.write(self.candidate, "reference/opening_scene.json", self.scene)
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)


class TranslationTests(Fixture):
    def test_static_field_checks_require_the_indexed_color_and_page_sequence(self):
        for root in (self.base, self.candidate):
            path = root / "reference/record_index.json"
            index = json.loads(path.read_text(encoding="utf-8"))
            index["records"][0].update(page_breaks=1, control_sequence=[0xFF82, 0xFF84, 0xFF72])
            self.write(root, "reference/record_index.json", index)
        self.edit("[blue]Forest Trail[/color].\fGo there.")
        check_repo(self.candidate)
        self.assertEqual(validate(self.base, self.candidate)["english_changes"], 1)
        for text in ("Forest Trail.\fGo there.", "[red]Forest Trail[/color].\fGo there.",
                     "Go there.\f[blue]Forest Trail[/color]."):
            self.edit(text)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "source color controls"):
                check_repo(self.candidate)
            with self.subTest(validation=text), self.assertRaisesRegex(ValueError, "source color controls"):
                validate(self.base, self.candidate)

    def test_baseline_valid(self):
        self.assertEqual(validate(self.base, self.candidate)["english_changes"], 0)

    def test_valid_translation(self):
        self.edit("A natural line.\nAnother line.")
        self.assertEqual(validate(self.base, self.candidate)["english_changes"], 1)

    def test_bare_domain_with_long_suffix_is_rejected_in_translation_and_note(self):
        for english, note in (
            ("Visit example.technology", None),
            ("A natural line.", "Read example.museum"),
        ):
            with self.subTest(english=english, note=note):
                self.edit(english, note)
                with self.assertRaisesRegex(ValueError, "links/active markup"):
                    validate(self.base, self.candidate)

    def test_translation_cannot_add_or_remove_executable_flags(self):
        self.edit("Gintoki, are you ready?")
        for name in (
            "tools/helper.py",
            "README.md",
            "translations/ready/batch_0001.json",
        ):
            for root in (self.base, self.candidate):
                path = root / name
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# trusted\n", encoding="utf-8")
            for before, after in ((0, 0o111), (0o111, 0)):
                with self.subTest(name=name, before=before, after=after):
                    with (
                        self.executable_modes(
                            {self.base / name: before, self.candidate / name: after}
                        ),
                        self.assertRaisesRegex(
                            ValueError, "Executable permissions changed"
                        ),
                    ):
                        validate(self.base, self.candidate)

    def test_translation_preserves_existing_executable_flags(self):
        self.edit("A natural line.")
        for root in (self.base, self.candidate):
            (root / "helper.py").write_text("# trusted\n", encoding="utf-8")
        with self.executable_modes(
            {self.base / "helper.py": 0o111, self.candidate / "helper.py": 0o111}
        ):
            self.assertEqual(validate(self.base, self.candidate)["english_changes"], 1)

    def test_batch_identifier_is_a_safe_filename_matching_the_batch(self):
        path = self.candidate / "translations/ready/batch_0001.json"
        for identifier in (
            "../escaped",
            "/absolute",
            "C:\\escape",
            "batch_0001/extra",
            "con",
            "nul",
            "lpt1",
            "batch_0002",
            "batch_0001.json",
            None,
            3,
        ):
            with self.subTest(identifier=identifier):
                data = json.loads(path.read_text(encoding="utf-8"))
                data["batch_id"] = identifier
                self.write(self.candidate, "translations/ready/batch_0001.json", data)
                with self.assertRaisesRegex(ValueError, "Invalid batch identifier"):
                    check_repo(self.candidate)

    def test_csv_only_fails(self):
        path = self.candidate / "csv/ready/batch_0001.csv"
        path.write_text(path.read_text().replace(",,", ",Hello,"), encoding="utf-8")
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_json_only_fails(self):
        self.edit("English")
        (self.candidate / "csv/ready/batch_0001.csv").write_text(
            (self.base / "csv/ready/batch_0001.csv").read_text(), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_changed_hash_rejected(self):
        self.edit("English")
        path = self.candidate / "translations/ready/batch_0001.json"
        data = json.loads(path.read_text())
        data["records"][0]["source_words_sha256"] = "b" * 64
        self.write(self.candidate, "translations/ready/batch_0001.json", data)
        (self.candidate / "csv/ready/batch_0001.csv").write_text(
            csv_render(data), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_unexpected_file_rejected(self):
        self.edit("English")
        (self.candidate / "evil.py").write_text("print(123)")
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_valid_translation_cannot_include_code_workflows_or_reference_changes(self):
        for name in (
            "tools/helper.py",
            ".github/workflows/check.yml",
            "graphics/ui_recipes.json",
            "reference/extra.json",
            "README.md",
        ):
            with self.subTest(name=name):
                for root in (self.base, self.candidate):
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        "{}" if path.suffix == ".json" else "# trusted\n",
                        encoding="utf-8",
                    )
                self.edit("Gintoki, are you ready?")
                path = self.candidate / name
                path.write_text(
                    '{"changed":true}'
                    if path.suffix == ".json"
                    else "# proposed change\n",
                    encoding="utf-8",
                )
                with self.assertRaises(ValueError):
                    validate(self.base, self.candidate)
                path.write_bytes((self.base / name).read_bytes())

    def test_note_only_not_translation(self):
        self.edit(None, "Checked the original.")
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_page_count_rejected(self):
        self.edit("More\ftext")
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_link_rejected(self):
        self.edit("https://bad.example")
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_html_rejected(self):
        with self.assertRaises(ValueError):
            check_text("<script>alert(1)</script>", "english")

    def test_secret_rejected(self):
        with self.assertRaises(ValueError):
            check_text("ghp_" + "A" * 20, "english")

    def test_hidden_text_rejected(self):
        with self.assertRaises(ValueError):
            check_text("Hello\u202e", "english")

    def test_duplicate_keys_rejected(self):
        self.edit("English")
        path = self.candidate / "translations/ready/batch_0001.json"
        path.write_text(
            path.read_text().replace('"batch_id":', '"batch_id": "fake", "batch_id":'),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_csv_escape_roundtrip(self):
        sample = 'Hello, "world"\\again\nNext page\fAnd more'
        self.assertEqual(unescape(escape(sample)), sample)
        batch = json.loads(
            (self.base / "translations/ready/batch_0001.json").read_text()
        )
        batch["records"][0]["english"] = sample
        self.assertEqual(import_csv(csv_render(batch), batch), batch)

    def test_csv_id_immutable(self):
        batch = json.loads(
            (self.base / "translations/ready/batch_0001.json").read_text()
        )
        csv_text = csv_render(batch).replace(RECORD["id"], "msb_99999999")
        with self.assertRaises(ValueError):
            import_csv(csv_text, batch)

    def test_deprecated_term_warning(self):
        self.assertTrue(check_text("silver orb", "english"))

    def test_protected_credit_file(self):
        self.edit("Hello")
        (self.candidate / "TRANSLATORS.md").write_text("Added myself!")
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_copied_source_prose_is_rejected_before_merging(self):
        self.edit(chr(0x3042) * 9)
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)

    def test_symlink_rejected(self):
        self.edit("Hello")
        try:
            (self.candidate / "outside").symlink_to(self.base, target_is_directory=True)
        except (OSError, NotImplementedError):
            # Windows may deny creating a real link. Still exercise the guard
            # against the filesystem's symlink indication instead of skipping.
            from unittest.mock import patch

            directory = self.candidate / "outside"
            directory.mkdir()
            original = Path.is_symlink

            def simulated_link(path):
                return path == directory or original(path)

            with (
                patch.object(Path, "is_symlink", simulated_link),
                self.assertRaises(ValueError),
            ):
                validate(self.base, self.candidate)
            return
        with self.assertRaises(ValueError):
            validate(self.base, self.candidate)


class PromotionTests(Fixture):
    def test_promotion_cannot_add_or_remove_executable_flags(self):
        self.edit("Gintoki, are you ready?")
        for root in (self.base, self.candidate):
            (root / "helper.py").write_text("# trusted\n", encoding="utf-8")
        for name in (
            "README.md",
            "helper.py",
            "translations/ready/batch_0001.json",
            "csv/ready/batch_0001.csv",
        ):
            for before, after in ((0, 0o111), (0o111, 0)):
                with self.subTest(name=name, before=before, after=after):
                    with (
                        self.executable_modes(
                            {self.base / name: before, self.candidate / name: after}
                        ),
                        self.assertRaisesRegex(
                            ValueError, "Executable permissions changed"
                        ),
                    ):
                        validate_promotion(self.base, self.candidate)

    def test_promotion_preserves_existing_executable_flags(self):
        self.edit("A natural line.")
        for root in (self.base, self.candidate):
            (root / "helper.py").write_text("# trusted\n", encoding="utf-8")
        with self.executable_modes(
            {self.base / "helper.py": 0o111, self.candidate / "helper.py": 0o111}
        ):
            self.assertEqual(
                validate_promotion(self.base, self.candidate)["changed_files"], 2
            )


class CreditTests(Fixture):
    def event(self, login="translator-one", number=22):
        return {
            "merged": True,
            "base": {"ref": "staging", "sha": "a" * 40},
            "head": {"sha": "b" * 40},
            "number": number,
            "user": {"login": login},
            "merged_at": "2026-10-15T12:00:00Z",
        }

    def counts(self):
        before = {
            "format": "gintama-community-translation-v1",
            "batch_id": "batch_0001",
            "records": [RECORD.copy()],
        }
        after = json.loads(json.dumps(before))
        after["records"][0]["english"] = "A translated line."
        return measure_records(before, after)

    def credit(self):
        ledger = read_ledger(self.candidate / "credits/merged_prs.json")
        self.assertTrue(add_merged(ledger, self.event(), self.counts()))
        self.write(self.candidate, "credits/merged_prs.json", ledger)
        (self.candidate / "TRANSLATORS.md").write_text(render(ledger), encoding="utf-8")
        return ledger

    def test_valid_credit(self):
        self.credit()
        self.assertEqual(
            validate_credits(self.base, self.candidate)["pr_numbers"], [22]
        )

    def test_no_credit_for_non_translation(self):
        ledger = read_ledger(self.base / "credits/merged_prs.json")
        self.assertFalse(add_merged(ledger, self.event(), []))

    def test_non_merged_no_credit(self):
        ledger = read_ledger(self.base / "credits/merged_prs.json")
        event = self.event()
        event["merged"] = False
        self.assertFalse(add_merged(ledger, event, self.counts()))

    def test_duplicate_pr_no_double_credit(self):
        ledger = self.credit()
        self.assertFalse(add_merged(ledger, self.event(), self.counts()))

    def test_credit_document_tamper(self):
        self.credit()
        (self.candidate / "TRANSLATORS.md").write_text("# A fake name\n")
        with self.assertRaises(ValueError):
            validate_credits(self.base, self.candidate)

    def test_two_new_credits_need_remote_verification(self):
        from unittest.mock import patch

        ledger = self.credit()
        ledger["entries"].append(
            {
                "number": 23,
                "login": "other",
                "merged_at": "2026-10-15T13:00:00Z",
                "base_sha": "a" * 40,
                "head_sha": "b" * 40,
                "records": self.counts(),
            }
        )
        self.write(self.candidate, "credits/merged_prs.json", ledger)
        (self.candidate / "TRANSLATORS.md").write_text(render(ledger), encoding="utf-8")
        self.assertEqual(validate_credits(self.base, self.candidate)["new_credits"], 2)
        with (
            patch.dict(
                "os.environ",
                {"GITHUB_TOKEN": "test", "GITHUB_REPOSITORY": "owner/repo"},
            ),
            patch(
                "check_credits.github",
                side_effect=ValueError("GitHub rejected forged PR"),
            ),
            self.assertRaises(ValueError),
        ):
            validate_credits(self.base, self.candidate, verify_remote=True)

    def test_staging_push_collects_merged_translation(self):
        from unittest.mock import patch

        sha = "b" * 40
        event = {"ref": "refs/heads/staging", "after": sha, "commits": [{"id": sha}]}
        ledger = read_ledger(self.base / "credits/merged_prs.json")

        def fake_get(path, token, repo):
            if path.endswith("/pulls"):
                return [{"number": 22}]
            if path == "pulls/22":
                return self.event()
            raise ValueError("Unexpected API call: " + path)

        with (
            patch("credits.github", side_effect=fake_get),
            patch(
                "credits.verified_entry",
                side_effect=lambda pr, token, repo: {
                    "number": pr["number"],
                    "login": pr["user"]["login"],
                    "merged_at": pr["merged_at"],
                    "base_sha": pr["base"]["sha"],
                    "head_sha": pr["head"]["sha"],
                    "records": self.counts(),
                },
            ),
        ):
            self.assertEqual(
                collect_push_credits(event, ledger, "test", "owner/repo"), 1
            )
            self.assertEqual(
                collect_push_credits(event, ledger, "test", "owner/repo"), 0
            )
        self.assertEqual(len(ledger["entries"]), 1)

    def test_untrusted_push_branch_rejected(self):
        ledger = read_ledger(self.base / "credits/merged_prs.json")
        with self.assertRaises(ValueError):
            collect_push_credits(
                {"ref": "refs/heads/attacker"}, ledger, "test", "owner/repo"
            )

    def test_non_translation_files_not_counted(self):
        ledger = read_ledger(self.base / "credits/merged_prs.json")
        self.assertFalse(add_merged(ledger, self.event(), []))

    def test_invalid_login_rejected(self):
        ledger = read_ledger(self.base / "credits/merged_prs.json")
        with self.assertRaises(ValueError):
            add_merged(
                ledger,
                self.event("bad](http://evil)"),
                self.counts(),
            )


class PeerReviewTests(unittest.TestCase):
    SHA = "a" * 40

    def review(self, login, state="APPROVED", sha=None, kind="User"):
        return {
            "user": {"login": login, "type": kind},
            "state": state,
            "commit_id": self.SHA if sha is None else sha,
        }

    def check(self, entries, author="author"):
        from check_peer_reviews import eligible_reviews

        calls = []

        def fetch(path, token, repo):
            calls.append(path)
            if not path.startswith("pulls/1/reviews?"):
                raise AssertionError("Reviewer permission lookup should not happen")
            return entries

        names = eligible_reviews(1, self.SHA, author, "token", "owner/repo", fetch)
        return names, calls

    def test_two_unlisted_public_accounts_count(self):
        names, paths = self.check(
            [self.review("reader_one"), self.review("reader_two")]
        )
        self.assertEqual(names, ["reader_one", "reader_two"])
        self.assertEqual(len(paths), 1)

    def test_admins_count_but_author_and_bots_do_not(self):
        names, _ = self.check(
            [
                self.review("admin"),
                self.review("outside"),
                self.review("author"),
                self.review("some-app[bot]", kind="Bot"),
                self.review("service", kind="Bot"),
            ]
        )
        self.assertEqual(names, ["admin", "outside"])

    def test_approval_must_be_on_current_head(self):
        names, _ = self.check(
            [self.review("stale", sha="b" * 40), self.review("fresh")]
        )
        self.assertEqual(names, ["fresh"])

    def test_latest_review_wins(self):
        names, _ = self.check(
            [
                self.review("one"),
                self.review("one", state="DISMISSED"),
                self.review("two", state="COMMENTED"),
                self.review("three"),
            ]
        )
        self.assertEqual(names, ["three"])

    def test_account_names_deduplicate_case_insensitively(self):
        names, _ = self.check(
            [self.review("Alice"), self.review("ALICE"), self.review("Bob")]
        )
        self.assertEqual(names, ["ALICE", "Bob"])

    def test_pending_review_does_not_replace_submitted_approval(self):
        names, _ = self.check(
            [self.review("first"), self.review("first", state="PENDING")]
        )
        self.assertEqual(names, ["first"])

    def test_missing_reviewer_identity_ignored(self):
        names, _ = self.check(
            [
                {"user": None, "state": "APPROVED", "commit_id": self.SHA},
                self.review("real"),
            ]
        )
        self.assertEqual(names, ["real"])

    def test_review_pagination_and_api_cap(self):
        from check_peer_reviews import eligible_reviews

        page = [self.review(f"user{i}") for i in range(100)]
        paths = []

        def fetch(path, token, repo):
            paths.append(path)
            return page if path.endswith("&page=1") else [self.review("next")]

        names = eligible_reviews(1, self.SHA, "author", "token", "owner/repo", fetch)
        self.assertEqual(len(names), 101)
        self.assertEqual(len(paths), 2)


if __name__ == "__main__":
    unittest.main()
