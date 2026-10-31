#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser(
    description="Look up records by ID or English text without loading game assets"
)
p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
group = p.add_mutually_exclusive_group(required=True)
group.add_argument("--id", help="Exact record ID, such as msb_00000254")
group.add_argument("--contains", help="Case-insensitive English text search")
p.add_argument("--limit", type=int, default=20)
a = p.parse_args()
index = json.loads((a.root / "reference/record_index.json").read_text(encoding="utf-8"))
refs = {row["id"]: row for row in index["records"]}
found = 0
for path in sorted((a.root / "translations").glob("**/*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["records"]:
        if a.id and entry["id"] != a.id:
            continue
        if (
            a.contains
            and a.contains.casefold() not in (entry["english"] or "").casefold()
        ):
            continue
        print(
            entry["id"],
            refs[entry["id"]]["offset_hex"],
            f"in {path.relative_to(a.root)}",
        )
        print(repr(entry["english"]), "note:", entry["translator_note"])
        found += 1
        if found >= a.limit:
            raise SystemExit(0)
print(f"{found} matches")
