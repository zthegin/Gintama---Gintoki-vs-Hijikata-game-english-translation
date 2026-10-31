# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import review_queue

HEAD = "a" * 40
BASE = "b" * 40
OTHER = "d" * 40


def review(login, *, state="APPROVED", head=HEAD, kind="User"):
    return {"user": {"login": login, "type": kind}, "state": state, "commit_id": head}


class GitHubFixture:
    repository = "owner/project"
    token = "synthetic test credential"

    def __init__(self):
        self.calls = []
        self.pr = {
            "number": 7,
            "state": "open",
            "draft": False,
            "title": "Translation: msb_00000100",
            "body": "A shorter English line.",
            "base": {
                "ref": "staging",
                "sha": BASE,
                "repo": {"full_name": self.repository},
            },
            "head": {"sha": HEAD, "repo": {"full_name": "contributor/fork"}},
            "user": {"login": "author"},
            "labels": [{"name": review_queue.LABEL}],
        }
        self.run = {
            "id": 42,
            "workflow_id": 10,
            "status": "completed",
            "conclusion": "success",
            "event": "pull_request",
            "head_sha": HEAD,
            "repository": {"full_name": self.repository},
            "pull_requests": [{"number": 7}],
        }
        self.base = BASE
        self.reviews = [review("outside_one"), review("outside_two")]

    def __call__(self, path, *, method="GET", data=None):
        self.calls.append((method, path, data))
        if method != "GET":
            if (
                method == "POST"
                and path == "issues/7/labels"
                and data == {"labels": [review_queue.LABEL]}
            ):
                return []
            if method == "DELETE" and path == "issues/7/labels/" + review_queue.LABEL:
                return None
            raise AssertionError(
                "The queue may never merge, change code or dispatch workflows"
            )
        values = {
            "actions/runs/42": self.run,
            "actions/workflows/translation-pr.yml": {"id": 10},
            "actions/workflows/peer-reviews.yml": {"id": 11},
            "pulls/7": self.pr,
            "git/ref/heads/staging": {"object": {"sha": self.base}},
            "pulls/7/reviews?per_page=100&page=1": self.reviews,
            "pulls?state=open&per_page=100&page=1": [self.pr],
        }
        if path not in values:
            raise AssertionError("Unexpected API operation: " + path)
        return copy.deepcopy(values[path])

    def writes(self):
        return [call for call in self.calls if call[0] != "GET"]


class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.api = GitHubFixture()
        self.validator = Mock(return_value={"english_changes": 1})

    def run_queue(self, event=None):
        return review_queue.update_queue(
            self.api,
            {"workflow_run": {"id": 42}} if event is None else event,
            self.validator,
        )

    def added(self):
        return any(method == "POST" for method, _, _ in self.api.calls)

    def test_two_public_approvals_only_add_label_never_merge(self):
        self.assertIn("never merged", self.run_queue()[7])
        self.validator.assert_called_once_with(self.api, 7, BASE, HEAD)
        self.assertEqual(
            self.api.writes(),
            [
                ("DELETE", "issues/7/labels/" + review_queue.LABEL, None),
                ("POST", "issues/7/labels", {"labels": [review_queue.LABEL]}),
            ],
        )

    def test_main_community_draft_closed_and_foreign_prs_lose_label(self):
        for change in ("main", "community", "draft", "closed", "foreign"):
            with self.subTest(change=change):
                self.api = GitHubFixture()
                if change in {"main", "community"}:
                    self.api.pr["base"]["ref"] = change
                elif change == "draft":
                    self.api.pr["draft"] = True
                elif change == "closed":
                    self.api.pr["state"] = "closed"
                else:
                    self.api.pr["base"]["repo"]["full_name"] = "other/repo"
                self.run_queue()
                self.assertFalse(self.added())
                self.assertEqual(len(self.api.writes()), 1)
        self.validator.assert_not_called()

    def test_zero_one_stale_bot_author_or_duplicate_approvals_do_not_label(self):
        for reviews in (
            [],
            [review("one")],
            [
                review("author"),
                review("bot[bot]", kind="Bot"),
                review("old", head=OTHER),
            ],
            [review("one"), review("ONE")],
            [review("one"), review("two"), review("two", state="DISMISSED")],
            [review("one"), review("two"), review("two", state="CHANGES_REQUESTED")],
        ):
            with self.subTest(reviews=reviews):
                self.api = GitHubFixture()
                self.api.reviews = reviews
                self.run_queue()
                self.assertFalse(self.added())
        self.validator.assert_not_called()

    def test_failed_or_cancelled_runs_remove_stale_label(self):
        for conclusion in ("failure", "cancelled", "skipped"):
            self.api = GitHubFixture()
            self.api.run["conclusion"] = conclusion
            self.validator.side_effect = ValueError(
                "Untrusted code or invalid translation"
            )
            self.run_queue()
            self.assertFalse(self.added())
            self.assertEqual(len(self.api.writes()), 1)

    def test_validation_rejection_does_not_echo_untrusted_payload(self):
        self.validator.side_effect = ValueError("::warning::untrusted filename")
        result = self.run_queue()
        self.assertNotIn("::warning::", json.dumps(result))
        self.assertFalse(self.added())

    def test_head_base_text_reviews_or_branch_changes_prevent_label(self):
        for change in ("head", "base", "body", "reviews", "branch"):
            with self.subTest(change=change):
                self.api = GitHubFixture()

                def changed(*_, change=change):
                    if change == "head":
                        self.api.pr["head"]["sha"] = OTHER
                    elif change == "base":
                        self.api.base = OTHER
                    elif change == "body":
                        self.api.pr["body"] = "Changed description"
                    elif change == "reviews":
                        self.api.reviews[-1]["state"] = "DISMISSED"
                    else:
                        self.api.pr["base"]["ref"] = "main"
                    return {"english_changes": 1}

                self.validator.side_effect = changed
                self.run_queue()
                self.assertFalse(self.added())

    def test_bad_pr_metadata_never_reaches_checkout(self):
        self.api.pr["body"] = "Read https://example.org first."
        self.run_queue()
        self.validator.assert_not_called()
        self.assertFalse(self.added())

    def test_manual_scan_and_fork_payload_without_prs_reconcile_open_prs(self):
        self.api.run["pull_requests"] = []
        self.run_queue()
        self.assertTrue(self.added())
        self.api = GitHubFixture()
        self.run_queue({})
        self.assertTrue(self.added())

    def test_unrelated_run_is_ignored_without_writes(self):
        for field, value in (
            ("workflow_id", 99),
            ("status", "in_progress"),
            ("event", "push"),
        ):
            self.api = GitHubFixture()
            self.api.run[field] = value
            self.assertIn("skipped", self.run_queue())
            self.assertEqual(self.api.writes(), [])

    def test_http_client_cannot_call_any_merge_or_code_mutation_endpoint(self):
        api = review_queue.GitHub("owner/repo", "synthetic")
        for path, method, data in (
            ("pulls/7/merge", "PUT", {"sha": HEAD}),
            ("contents/README.md", "PUT", {}),
            (
                "actions/workflows/repository-health.yml/dispatches",
                "POST",
                {"ref": "main"},
            ),
            ("issues/7/labels", "POST", {"labels": ["another-label"]}),
        ):
            with (
                self.subTest(path=path),
                patch.object(review_queue.urllib.request, "urlopen") as request,
            ):
                with self.assertRaisesRegex(ValueError, "advisory label"):
                    api(path, method=method, data=data)
                request.assert_not_called()


class CheckoutSafetyTests(unittest.TestCase):
    def setUp(self):
        self.api = GitHubFixture()
        self.commands = []
        self.tree = f"100644 blob {HEAD} 5\tREADME.md\0".encode()

    def git(self, command, **options):
        self.commands.append((command, options))
        if "rev-parse" in command:
            result = BASE if options["cwd"].name == "base" else HEAD
            return subprocess.CompletedProcess(command, 0, (result + "\n").encode())
        return subprocess.CompletedProcess(
            command, 0, self.tree if "ls-tree" in command else b""
        )

    def test_checkouts_disable_external_execution_and_remove_token_environment(self):
        with (
            patch.dict(
                os.environ, {"GITHUB_TOKEN": "not for git", "GIT_CONFIG_COUNT": "99"}
            ),
            patch.object(review_queue.subprocess, "run", side_effect=self.git),
            patch.object(
                review_queue, "validate", return_value={"english_changes": 1}
            ) as validate,
        ):
            review_queue.validate_checkout(self.api, 7, BASE, HEAD)
        validate.assert_called_once()
        self.assertNotEqual(validate.call_args.args[0], validate.call_args.args[1])
        for command, options in self.commands:
            self.assertNotIn("GITHUB_TOKEN", options["env"])
            self.assertNotIn("GIT_CONFIG_COUNT", options["env"])
            self.assertEqual(options["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertIn("credential.helper=", command)
            self.assertIn("filter.lfs.process=", command)
            self.assertIn("submodule.recurse=false", command)
            self.assertTrue(
                any(value.startswith("core.hooksPath=") for value in command)
            )
            self.assertNotIn("contributor/fork", " ".join(command))
        fetches = [command for command, _ in self.commands if "fetch" in command]
        self.assertIn(BASE, fetches[0])
        self.assertIn("refs/pull/7/head", fetches[1])
        self.assertTrue(all("--depth=1" in command for command in fetches))

    def test_symlinks_submodules_and_large_blobs_stop_before_checkout(self):
        for mode, kind, size in (
            ("120000", "blob", 5),
            ("160000", "commit", "-"),
            ("100644", "blob", review_queue.MAX_TRACKED_FILE + 1),
        ):
            with self.subTest(mode=mode, size=size):
                self.commands = []
                self.tree = f"{mode} {kind} {HEAD} {size}\tREADME.md\0".encode()
                with (
                    patch.object(review_queue.subprocess, "run", side_effect=self.git),
                    patch.object(review_queue, "validate") as validate,
                    self.assertRaises(ValueError),
                ):
                    review_queue.validate_checkout(self.api, 7, BASE, HEAD)
                self.assertFalse(
                    any("checkout" in command for command, _ in self.commands)
                )
                validate.assert_not_called()

    def test_executable_flag_changes_stop_before_candidate_checkout(self):
        original_git = self.git

        def changed_mode(command, **options):
            result = original_git(command, **options)
            if "ls-tree" in command and options["cwd"].name == "candidate":
                result.stdout = self.tree.replace(b"100644", b"100755", 1)
            return result

        with (
            patch.object(review_queue.subprocess, "run", side_effect=changed_mode),
            patch.object(review_queue, "validate") as validate,
            self.assertRaisesRegex(ValueError, "executable modes"),
        ):
            review_queue.validate_checkout(self.api, 7, BASE, HEAD)
        validate.assert_not_called()
        self.assertEqual(
            [
                options["cwd"].name
                for command, options in self.commands
                if "checkout" in command
            ],
            ["base"],
        )

    def test_fetch_revision_race_is_rejected(self):
        with (
            patch.object(review_queue.subprocess, "run", side_effect=self.git),
            patch.object(review_queue, "validate") as validate,
            self.assertRaisesRegex(ValueError, "changed during fetch"),
        ):
            review_queue.validate_checkout(self.api, 7, OTHER, HEAD)
        validate.assert_not_called()

    def test_same_repository_issue_branch_uses_trusted_import_validator(self):
        self.api.pr["head"].update(
            ref="codex/issue-42", repo={"full_name": self.api.repository}
        )
        with (
            patch.object(review_queue.subprocess, "run", side_effect=self.git),
            patch.object(review_queue, "validate") as ordinary,
            patch.object(
                review_queue, "validate_issue_import",
                return_value={"english_changes": 1},
            ) as imported,
        ):
            review_queue.validate_checkout(self.api, 7, BASE, HEAD)
        ordinary.assert_not_called()
        imported.assert_called_once()
        self.assertEqual(imported.call_args.kwargs["expected_number"], 42)
        self.assertEqual(imported.call_args.kwargs["token"], self.api.token)

    def test_fork_and_similarly_named_branches_keep_ordinary_validation(self):
        for branch, repository in (
            ("codex/issue-42", "contributor/fork"),
            ("codex/issue-42-extra", self.api.repository),
            ("codex/issue-0", self.api.repository),
        ):
            with self.subTest(branch=branch, repository=repository):
                self.api.pr["head"].update(
                    ref=branch, repo={"full_name": repository}
                )
                with (
                    patch.object(review_queue.subprocess, "run", side_effect=self.git),
                    patch.object(
                        review_queue, "validate", return_value={"english_changes": 1}
                    ) as ordinary,
                    patch.object(review_queue, "validate_issue_import") as imported,
                ):
                    review_queue.validate_checkout(self.api, 7, BASE, HEAD)
                ordinary.assert_called_once()
                imported.assert_not_called()


if __name__ == "__main__":
    unittest.main()
