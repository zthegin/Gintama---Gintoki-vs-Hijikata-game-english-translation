#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
reference = json.loads(
    (root / "reference/record_index.json").read_text(encoding="utf-8")
)["records"]
status = Counter(row["decode_status"] for row in reference)
batches = sorted((root / "translations").glob("**/*.json"))
filled = sum(
    row["english"] is not None
    for path in batches
    for row in json.loads(path.read_text(encoding="utf-8"))["records"]
)
print(
    f"Source index: {len(reference)} records ({sum(r.get('kind') == 'graphic' for r in reference)} graphic recipes; remaining entries are text metadata)"
)
print(f"Editable batches: {len(batches)}; filled English entries: {filled}")
print("Source decode status:", dict(status))
print("A filled entry is not automatically reviewed, in-game validated, or released.")

field_count = sum(r.get("kind") != "graphic" for r in reference)
field_filled = sum(
    row["english"] is not None
    for path in (root / "translations/ready").glob("*.json")
    for row in json.loads(path.read_text(encoding="utf-8"))["records"]
)
opening = json.loads((root / "reference/opening_scene.json").read_text(encoding="utf-8"))
from battle_writer import load_pack

battle = load_pack(root=root)
battle_count = sum(row["record_count"] for row in battle["scripts"])
battle_filled = sum(len(row["messages"]) for row in battle["scripts"])
print(f"Field: {field_filled}/{field_count} indexed messages ({field_filled / field_count:.2%})")
print(f"Opening: {len(opening['messages'])} bundled English entries")
print(f"Battle: {battle_filled}/{battle_count} indexed records ({battle_filled / battle_count:.2%})")
print("Battle counts include repeated variants. These are script-entry counts, not whole-game completion.")
