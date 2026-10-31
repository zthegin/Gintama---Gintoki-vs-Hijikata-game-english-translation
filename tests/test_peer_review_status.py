# Unofficial fan translation; no game ownership is claimed. See RIGHTS.md.
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_peer_reviews as peers


class AdvisoryReviewTests(unittest.TestCase):
    def test_fewer_than_two_reviews_does_not_block_owner_merges(self):
        for accounts in ([], ["example-reviewer"]):
            with self.subTest(accounts=accounts), patch.object(peers, "eligible_reviews", return_value=accounts), patch.object(sys, "argv", ["check_peer_reviews.py", "--pr", "7", "--sha", "a" * 40, "--author", "example-author"]), patch.dict(os.environ, {"GITHUB_TOKEN": "test-value", "GITHUB_REPOSITORY": "example/project"}), contextlib.redirect_stdout(io.StringIO()) as output:
                peers.main()
                self.assertIn("owner may still review and merge", output.getvalue())

    def test_two_reviews_are_reported_without_merging(self):
        with patch.object(peers, "eligible_reviews", return_value=["example-one", "example-two"]) as fetch, patch.object(sys, "argv", ["check_peer_reviews.py", "--pr", "7", "--sha", "a" * 40, "--author", "example-author"]), patch.dict(os.environ, {"GITHUB_TOKEN": "test-value", "GITHUB_REPOSITORY": "example/project"}), contextlib.redirect_stdout(io.StringIO()) as output:
            peers.main()
            fetch.assert_called_once()
            self.assertIn("2/2", output.getvalue())


if __name__ == "__main__":
    unittest.main()
