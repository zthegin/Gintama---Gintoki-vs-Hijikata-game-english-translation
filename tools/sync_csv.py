#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import unicodedata
from pathlib import Path

from text_policy import strict_json

COLUMNS = ("id", "source_words_sha256", "english", "translator_note")
FORMULA_START = re.compile(r"^\s*[=+@-]")


def formula_start(value: str) -> bool:
    return bool(FORMULA_START.match(unicodedata.normalize("NFKC", value)))


def csv_path(json_path: Path, root: Path) -> Path:
    return (
        root / "csv" / json_path.relative_to(root / "translations").with_suffix(".csv")
    )


def escape(value: str | None) -> str:
    if value is None:
        return ""
    result = json.dumps(value, ensure_ascii=False)[1:-1]
    # Spreadsheet quoting alone does not prevent formulas. Double an existing
    # leading apostrophe too, so the safety prefix is reversible on CSV import.
    return "'" + result if result.startswith("'") or formula_start(result) else result


def unescape(value: str) -> str | None:
    if not value:
        return None
    if value.startswith("'") and (
        value[1:].startswith("'") or formula_start(value[1:])
    ):
        value = value[1:]
    result = json.loads('"' + value + '"')
    if not isinstance(result, str) or not result.strip():
        raise ValueError("CSV cell contains an empty or invalid value")
    return result


def render(data: dict) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in data["records"]:
        writer.writerow(
            {
                col: escape(row[col])
                if col in ("english", "translator_note")
                else row[col]
                for col in COLUMNS
            }
        )
    return stream.getvalue()


def import_csv(csv_text: str, original: dict) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text, newline=""), strict=True)
    if reader.fieldnames != list(COLUMNS):
        raise ValueError("CSV columns must be: " + ", ".join(COLUMNS))
    rows = list(reader)
    if len(rows) != len(original["records"]):
        raise ValueError("CSV record count changed")
    updated = json.loads(json.dumps(original, allow_nan=False))
    for number, (incoming, previous) in enumerate(zip(rows, updated["records"]), 2):
        if None in incoming or None in incoming.values():
            raise ValueError(f"CSV row {number} has extra or missing columns")
        for field in ("id", "source_words_sha256"):
            if incoming[field] != previous[field]:
                raise ValueError(f"CSV row {number}: {field} is immutable")
        for field in ("english", "translator_note"):
            previous[field] = unescape(incoming[field])
    return updated


def canonical_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def sync_one(root: Path, source: Path, direction: str, check: bool) -> bool:
    view = csv_path(source, root)
    current = strict_json(source.read_text(encoding="utf-8"))
    if direction == "csv":
        if not view.is_file():
            raise ValueError(f"Missing CSV: {view}")
        changed = import_csv(view.read_text(encoding="utf-8-sig"), current)
        expected = canonical_json(changed)
        target = source
    else:
        expected = render(current)
        target = view
    actual = target.read_text(encoding="utf-8-sig") if target.exists() else None
    if actual == expected:
        return False
    if check:
        raise ValueError(
            f"JSON/CSV out of sync: {target}; run tools/sync_csv.py --from {direction}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(expected, encoding="utf-8", newline="")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Round-trip translation batches between canonical JSON and spreadsheet-friendly CSV"
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    parser.add_argument(
        "--from", dest="direction", choices=("json", "csv"), default="json"
    )
    parser.add_argument(
        "--batch", help="batch_0001 or field_dialogue; omit for all batches"
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail on drift without writing any file"
    )
    args = parser.parse_args()
    root = args.root.resolve()
    sources = sorted((root / "translations").glob("**/*.json"))
    if args.batch:
        sources = [path for path in sources if path.stem == args.batch]
    if not sources:
        parser.error("No matching JSON batch")
    changes = sum(sync_one(root, path, args.direction, args.check) for path in sources)
    print(f"Checked {len(sources)} batches; {changes} file(s) updated.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, csv.Error) as error:
        raise SystemExit(str(error)) from error
