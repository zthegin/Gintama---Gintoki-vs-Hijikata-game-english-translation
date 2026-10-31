#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from check_public_tree import check as publication_check
from validate_pr import inventory

from credits import github, read_ledger, render, verified_entry


def validate(base: Path, candidate: Path, verify_remote=False) -> dict:
    publication_issues = publication_check(candidate)
    if publication_issues:
        raise ValueError(
            "Candidate publication audit failed: " + "; ".join(publication_issues)
        )
    old_files, new_files = inventory(base), inventory(candidate)
    if old_files.keys() != new_files.keys():
        raise ValueError("Credits PR cannot add or delete files")
    for name in old_files:
        if (
            old_files[name].stat().st_mode & 0o111
            != new_files[name].stat().st_mode & 0o111
        ):
            raise ValueError("Credits PR cannot change executable permissions")
    changed = {
        name
        for name in old_files
        if old_files[name].read_bytes() != new_files[name].read_bytes()
    }
    if changed != {"credits/merged_prs.json", "TRANSLATORS.md"}:
        raise ValueError(
            f"Credits PR must update only the ledger and generated document: {sorted(changed)}"
        )
    before = read_ledger(base / "credits/merged_prs.json")
    after = read_ledger(candidate / "credits/merged_prs.json")
    from issue_imports import read_issue_ledger

    old_issues = read_issue_ledger(base / "credits/issue_imports.json")
    issues = read_issue_ledger(candidate / "credits/issue_imports.json")
    if issues != old_issues:
        raise ValueError("Credits PR cannot alter accepted issue attribution")
    if (
        not len(before["entries"])
        < len(after["entries"])
        <= len(before["entries"]) + 100
    ):
        raise ValueError("Credits PR must append one or more merged PRs (at most 100)")
    previous = {row["number"]: row for row in before["entries"]}
    current = {row["number"]: row for row in after["entries"]}
    if any(current.get(number) != row for number, row in previous.items()):
        raise ValueError("Old credits cannot be altered")
    added = [row for row in after["entries"] if row["number"] not in previous]
    if len(added) != len(after["entries"]) - len(before["entries"]):
        raise ValueError("Credits PR has inconsistent added entries")
    if (candidate / "TRANSLATORS.md").read_text(encoding="utf-8") != render(after, issues):
        raise ValueError("TRANSLATORS.md does not match trusted renderer")
    if verify_remote:
        token, repo = os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"]
        for new in added:
            pr = github(f"pulls/{new['number']}", token, repo)
            verified = verified_entry(pr, token, repo)
            if verified != new:
                raise ValueError(
                    "Credits disagree with verified merged-PR English changes"
                )
    return {"new_credits": len(added), "pr_numbers": [row["number"] for row in added]}


def main():
    parser = argparse.ArgumentParser(
        description="Check an automated credit PR, optionally against the GitHub merge API"
    )
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--verify-github", action="store_true")
    args = parser.parse_args()
    try:
        print(
            "Verified credit:", validate(args.base, args.candidate, args.verify_github)
        )
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("CREDIT PR REJECTED:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
