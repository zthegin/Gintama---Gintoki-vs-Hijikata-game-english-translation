#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

from check_public_tree import check as publication_check
from sync_csv import csv_path, render
from text_policy import check_safe_text, normalized
from field_markup import check_record_controls

FORMAT = "gintama-community-translation-v1"
REFERENCE_PATHS = {"reference/opening_scene.json", "reference/battle.json"}
BATCH_ID = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")
RESERVED_BATCH_ID = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])\Z")
TERM_WARN = re.compile(r"\b(?:silver orbs?|silver balls?)\b", re.I)
INJECTION_WARN = re.compile(
    r"(?im)(?:(?:ignore|disregard|forget)\s+(?:all\s+|the\s+)?(?:previous|prior|system|developer)\s+(?:instructions|prompts|rules)|override\s+(?:the\s+)?(?:rules|checks)|skip\s+(?:the\s+)?review|run this command|execute this code|^\s*(?:system|developer|assistant|tool)\s*:|(?:reveal|exfiltrate|print|send)\s+(?:the\s+|your\s+)?(?:system prompt|api key|token|credentials))"
)


class DuplicateKeyError(ValueError):
    pass


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load(path: Path, max_bytes=2_000_000):
    if path.stat().st_size > max_bytes:
        raise ValueError(f"Oversized file: {path}")

    def nonfinite(token):
        raise ValueError(f"Non-finite JSON number: {token}")

    def finite_float(token):
        value = float(token)
        if not math.isfinite(value):
            raise ValueError("Non-finite JSON number")
        return value

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_keys,
        parse_constant=nonfinite,
        parse_float=finite_float,
    )


def inventory(root: Path) -> dict[str, Path]:
    found = {}
    for parent, directories, names in os.walk(root, followlinks=False):
        for dirname in directories:
            if (Path(parent) / dirname).is_symlink():
                raise ValueError(
                    f"Symlink directory forbidden: {Path(parent) / dirname}"
                )
        directories[:] = [name for name in directories if name != ".git"]
        for name in names:
            path = Path(parent, name)
            if path.is_symlink():
                raise ValueError(f"Symlink forbidden: {path}")
            rel = path.relative_to(root).as_posix()
            if "__pycache__" in path.parts or rel.startswith(".pytest_cache/"):
                continue
            found[rel] = path
    return found


def check_text(value, label, limit=2500) -> list[str]:
    check_safe_text(value, label, limit)
    if value is None:
        return []
    warnings = []
    if TERM_WARN.search(value):
        warnings.append(f"{label}: use Gin Tama terminology")
    if INJECTION_WARN.search(normalized(value)):
        warnings.append(f"{label}: possible instruction-like text; review manually")
    return warnings


def check_repo(root: Path) -> tuple[dict, dict]:
    """Validate every committed batch and its CSV view, not only changed files."""
    index = load(root / "reference/record_index.json", 20_000_000)
    reference = {record["id"]: record for record in index["records"]}
    if len(reference) != len(index["records"]):
        raise ValueError("Reference index contains duplicate IDs")
    locations = {}
    batches = sorted((root / "translations").glob("**/*.json"))
    if not batches:
        raise ValueError("No translation batches")
    for path in batches:
        relative = path.relative_to(root / "translations")
        if len(relative.parts) != 2 or relative.parts[0] not in {
            "ready",
            "graphics",
        }:
            raise ValueError(f"Unexpected translation batch directory: {relative}")
    for path in batches:
        data = load(path)
        if set(data) != {"format", "batch_id", "records"} or data["format"] != FORMAT:
            raise ValueError(f"Invalid batch header: {path}")
        identifier = data["batch_id"]
        if (
            not isinstance(identifier, str)
            or not BATCH_ID.fullmatch(identifier)
            or RESERVED_BATCH_ID.fullmatch(identifier)
            or identifier != path.stem
        ):
            raise ValueError(f"Invalid batch identifier: {path}")
        if not isinstance(data["records"], list):
            raise ValueError(f"Invalid records: {path}")
        expected_view = csv_path(path, root)
        if not expected_view.is_file() or expected_view.read_text(
            encoding="utf-8-sig"
        ) != render(data):
            raise ValueError(
                f"Stale CSV view: {expected_view}; run tools/sync_csv.py --from json"
            )
        for record in data["records"]:
            if not isinstance(record, dict) or set(record) != {
                "id",
                "source_words_sha256",
                "english",
                "translator_note",
            }:
                raise ValueError(f"Unexpected entry fields in {path}")
            entry_id = record["id"]
            if entry_id in locations:
                raise ValueError(f"Duplicate translation ID: {entry_id}")
            locations[entry_id] = path
            indexed = reference.get(entry_id)
            if (
                not indexed
                or record["source_words_sha256"] != indexed["source_words_sha256"]
            ):
                raise ValueError(f"Unknown/altered source hash: {entry_id}")
            if record["english"] is not None:
                check_text(record["english"], f"{entry_id}.english")
                if record["english"].count("\f") != indexed["page_breaks"]:
                    raise ValueError(
                        f"{entry_id}: page-break count differs from source"
                    )
                check_record_controls(record["english"], indexed)
            check_text(record["translator_note"], f"{entry_id}.translator_note", 500)
    actual = {
        path.relative_to(root / "csv").with_suffix(".json").as_posix()
        for path in (root / "csv").glob("**/*.csv")
    }
    wanted = {path.relative_to(root / "translations").as_posix() for path in batches}
    if actual != wanted:
        raise ValueError("Missing or extra CSV files")
    if (root / "graphics/catalog.json").is_file():
        from image_workflow import validate_graphic_translations

        validate_graphic_translations(root)
    if (root / "reference/opening_scene.json").is_file():
        from issue_imports import validate_script_changes

        scene = load(root / "reference/opening_scene.json")
        validate_script_changes("reference/opening_scene.json", scene, scene, root=root)
    if (root / "reference/battle.json").is_file():
        from battle_writer import load_pack

        load_pack(root=root)
    return reference, locations


def validate(base: Path, candidate: Path) -> dict:
    publication_issues = publication_check(candidate)
    if publication_issues:
        raise ValueError(
            "Candidate publication audit failed: " + "; ".join(publication_issues)
        )
    base_files, new_files = inventory(base), inventory(candidate)
    if base_files.keys() != new_files.keys():
        raise ValueError(
            "Added/deleted files are forbidden: "
            + repr(sorted(base_files.keys() ^ new_files.keys())[:10])
        )
    for rel in base_files:
        if (base_files[rel].stat().st_mode ^ new_files[rel].stat().st_mode) & 0o111:
            raise ValueError(f"Executable permissions changed: {rel}")
    reference, _ = check_repo(base)
    check_repo(candidate)
    changed = [
        rel
        for rel in sorted(base_files)
        if base_files[rel].read_bytes() != new_files[rel].read_bytes()
    ]
    if not changed:
        return {
            "changed_files": 0,
            "edited_records": 0,
            "english_changes": 0,
            "warnings": [],
        }
    if any(
        not (
            rel in REFERENCE_PATHS or (
                rel.startswith(
                    (
                        "translations/ready/",
                        "translations/graphics/",
                        "csv/ready/",
                        "csv/graphics/",
                    )
                )
                and rel.endswith((".json", ".csv"))
            )
        )
        for rel in changed
    ):
        raise ValueError(
            "Ordinary PRs may edit only English translations and their synchronized CSV views: "
            + repr(changed[:10])
        )

    edits = 0
    english_changes = 0
    warnings = []
    for rel in changed:
        if rel.startswith("csv/"):
            continue  # Checked against the canonical JSON by check_repo(candidate).
        previous = load(base_files[rel])
        proposed = load(new_files[rel])
        if rel in REFERENCE_PATHS:
            from issue_imports import validate_script_changes
            from credits import measure_reference_records

            validate_script_changes(rel, previous, proposed, root=base)
            measured = measure_reference_records(rel, previous, proposed)
            edits += len(measured)
            english_changes += len(measured)
            continue
        if (
            set(previous) != set(proposed)
            or previous["batch_id"] != proposed["batch_id"]
            or previous["format"] != proposed["format"]
        ):
            raise ValueError(f"Batch header altered: {rel}")
        if len(previous["records"]) != len(proposed["records"]):
            raise ValueError(f"Batch length altered: {rel}")
        for before, after in zip(previous["records"], proposed["records"]):
            if (
                before["id"] != after["id"]
                or before["source_words_sha256"] != after["source_words_sha256"]
            ):
                raise ValueError(f"Immutable ID/hash/order altered: {rel}")
            if before == after:
                continue
            edits += 1
            if before["english"] is not None and after["english"] is None:
                raise ValueError(f"Cannot erase existing translation: {after['id']}")
            if before["english"] != after["english"]:
                english_changes += 1
            for field in ("english", "translator_note"):
                warnings += check_text(
                    after[field],
                    f"{after['id']}.{field}",
                    2500 if field == "english" else 500,
                )
            if (
                after["english"] is not None
                and after["english"].count("\f")
                != reference[after["id"]]["page_breaks"]
            ):
                raise ValueError(f"Invalid page count: {after['id']}")
            check_record_controls(after["english"], reference[after["id"]])
    if english_changes == 0:
        raise ValueError(
            "A translation PR must actually change English text, not only notes/formatting/CSV"
        )
    if not any(rel.startswith("translations/") or rel in REFERENCE_PATHS for rel in changed):
        raise ValueError(
            "CSV-only change: run tools/sync_csv.py --from csv --batch NAME"
        )
    return {
        "changed_files": len(changed),
        "edited_records": edits,
        "english_changes": english_changes,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate proposed translation files against the trusted base checkout"
    )
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.base.resolve(), args.candidate.resolve())
    except (ValueError, KeyError, OSError, TypeError) as error:
        print("PR REJECTED:", error, file=sys.stderr)
        return 1
    print("Translation validation:", result)
    for warning in result["warnings"]:
        print("REVIEW WARNING:", warning)
    print(
        "Automatic checks do not replace Japanese fluency, content moderation, copyright review, or emulator testing."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
