#!/usr/bin/env python3
# Unofficial fan translation of this Nintendo DS game; no ownership or endorsement is claimed.
# Use only a legally obtained ROM; piracy is discouraged. See RIGHTS.md.
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from check_public_tree import check as publication_check
from issue_imports import fetch_issue, propose, read_issue_ledger
from validate_pr import inventory

LEDGER = "credits/issue_imports.json"
DOCUMENT = "TRANSLATORS.md"
TRANSLATION = re.compile(
    r"(?:translations/(?:ready|graphics)/[a-z][a-z0-9_]{0,79}\.json|"
    r"csv/(?:ready|graphics)/[a-z][a-z0-9_]{0,79}\.csv|"
    r"reference/(?:opening_scene|battle)\.json)\Z"
)
IMPORT_BRANCH = re.compile(r"codex/issue-([1-9][0-9]*)\Z")


def import_number(branch: str, head_repository: str, base_repository: str):
    if not all(isinstance(value, str) for value in (branch, head_repository, base_repository)):
        return None
    match = IMPORT_BRANCH.fullmatch(branch)
    if match and head_repository.casefold() == base_repository.casefold():
        return int(match[1])
    return None


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Invalid issue update time")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Issue update time needs a timezone")
    return result


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def validate(
    base: Path,
    candidate: Path,
    *,
    fetch=None,
    token=None,
    expected_number=None,
) -> dict:
    issues = publication_check(candidate)
    if issues:
        raise ValueError("Candidate publication audit failed")
    old_files, new_files = inventory(base), inventory(candidate)
    if old_files.keys() != new_files.keys():
        raise ValueError("Issue imports cannot add or delete files")
    for name in old_files:
        if (old_files[name].stat().st_mode ^ new_files[name].stat().st_mode) & 0o111:
            raise ValueError("Issue imports cannot change executable permissions")
    changed = {
        name for name in old_files
        if lf(old_files[name].read_bytes()) != lf(new_files[name].read_bytes())
    }
    if not {LEDGER, DOCUMENT} <= changed or any(
        name not in {LEDGER, DOCUMENT} and not TRANSLATION.fullmatch(name)
        for name in changed
    ):
        raise ValueError("Issue imports may change only their translation, CSV and credits")
    before = read_issue_ledger(base / LEDGER)
    after = read_issue_ledger(candidate / LEDGER)
    previous = {entry["number"]: entry for entry in before["entries"]}
    current = {entry["number"]: entry for entry in after["entries"]}
    if any(current.get(number) != entry for number, entry in previous.items()):
        raise ValueError("Old issue import receipts cannot be altered or removed")
    added = [entry for entry in after["entries"] if entry["number"] not in previous]
    if len(added) != 1 or len(after["entries"]) != len(before["entries"]) + 1:
        raise ValueError("An import PR must append exactly one issue receipt")
    entry = added[0]
    if expected_number is not None and entry["number"] != expected_number:
        raise ValueError("Issue receipt does not match the import branch number")
    fresh = (fetch or fetch_issue)(entry["number"], token=token)
    saved_time = timestamp(entry["updated_at"])
    if saved_time > timestamp(fresh.get("updated_at")) or saved_time > datetime.now(timezone.utc):
        raise ValueError("Issue receipt has an invalid or future update time")
    # Comments may update the issue timestamp without changing its suggestion.
    # Rebuild against the current body and creator while retaining the saved time.
    expected, verified = propose(base, {**fresh, "updated_at": entry["updated_at"]})
    if verified != entry:
        raise ValueError("Issue receipt differs from the current verified suggestion")
    if set(expected) != changed or any(
        name not in {LEDGER, DOCUMENT} and not TRANSLATION.fullmatch(name)
        for name in expected
    ):
        raise ValueError("Import changes do not match the verified issue outputs")
    if any(lf(new_files[name].read_bytes()) != lf(payload) for name, payload in expected.items()):
        raise ValueError("Imported files differ from the verified issue outputs")
    return {
        "english_changes": 1,
        "issue_number": entry["number"],
        "changed_files": len(changed),
        "layout_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verify one issue-import proposal as data, without a ROM or code execution"
    )
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--issue", type=int)
    args = parser.parse_args()
    try:
        result = validate(
            args.base, args.candidate,
            token=os.environ.get("GITHUB_TOKEN"), expected_number=args.issue,
        )
        print("Issue import verified:", result)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ISSUE IMPORT REJECTED ({type(error).__name__}); no game layout was tested.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
