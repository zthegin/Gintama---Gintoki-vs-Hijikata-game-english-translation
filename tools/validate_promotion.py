#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from check_public_tree import check as publication_check
from validate_pr import check_repo, inventory, load

from credits import read_ledger, render
from issue_imports import read_issue_ledger, validate_script_changes

REFERENCE_PATHS = {"reference/opening_scene.json", "reference/battle.json"}
ALLOWED = {
    "TRANSLATORS.md", "credits/merged_prs.json", "credits/issue_imports.json",
} | REFERENCE_PATHS


def validate(base: Path, staged: Path) -> dict:
    publication_issues = publication_check(staged)
    if publication_issues:
        raise ValueError(
            "Candidate publication audit failed: " + "; ".join(publication_issues)
        )
    a, b = inventory(base), inventory(staged)
    if a.keys() != b.keys():
        raise ValueError("Promotion may not add or remove files")
    for name in a:
        if (a[name].stat().st_mode ^ b[name].stat().st_mode) & 0o111:
            raise ValueError(f"Executable permissions changed: {name}")
    old_idx, _ = check_repo(base)
    new_idx, _ = check_repo(staged)
    if old_idx != new_idx:
        raise ValueError("Reference index was modified")
    changed = {name for name in a if a[name].read_bytes() != b[name].read_bytes()}
    if any(
        not (name.startswith(("translations/", "csv/")) or name in ALLOWED)
        for name in changed
    ):
        raise ValueError(
            "Only staged translations, reference English, CSV views and credits can be promoted"
        )
    for name in changed:
        if not name.startswith("translations/"):
            continue
        old = load(a[name])
        new = load(b[name])
        if (
            old["format"] != new["format"]
            or old["batch_id"] != new["batch_id"]
            or len(old["records"]) != len(new["records"])
        ):
            raise ValueError(f"Batch changed shape: {name}")
        for before, after in zip(old["records"], new["records"]):
            if (
                before["id"] != after["id"]
                or before["source_words_sha256"] != after["source_words_sha256"]
            ):
                raise ValueError(f"Immutable translation metadata changed: {name}")
            if before["english"] is not None and after["english"] is None:
                raise ValueError(f"Promotion would erase translation: {after['id']}")
    old = read_ledger(base / "credits/merged_prs.json")["entries"]
    new = read_ledger(staged / "credits/merged_prs.json")["entries"]
    by_number = {entry["number"]: entry for entry in new}
    if any(by_number.get(entry["number"]) != entry for entry in old):
        raise ValueError("Promotion would alter/remove previously published credits")
    old_issues = read_issue_ledger(base / "credits/issue_imports.json")["entries"]
    new_issues = read_issue_ledger(staged / "credits/issue_imports.json")
    by_issue = {entry["number"]: entry for entry in new_issues["entries"]}
    if any(by_issue.get(entry["number"]) != entry for entry in old_issues):
        raise ValueError("Promotion would alter/remove published issue receipts")
    for name in REFERENCE_PATHS & changed:
        validate_script_changes(name, load(a[name]), load(b[name]), root=base)
    if (staged / "TRANSLATORS.md").read_text(encoding="utf-8") != render(
        {"entries": new}, new_issues
    ):
        raise ValueError("Generated credits file is stale")
    return {"changed_files": len(changed), "staged_credits": len(new), "staged_issues": len(new_issues["entries"])}


def main():
    p = argparse.ArgumentParser(
        description="Read-only check for promoting staging translations/credits to main"
    )
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--candidate", required=True, type=Path)
    args = p.parse_args()
    try:
        print("Promotion valid:", validate(args.base, args.candidate))
    except (ValueError, KeyError, OSError, TypeError) as error:
        print("PROMOTION REJECTED:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
