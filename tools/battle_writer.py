# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import re
import struct
from pathlib import Path

import cutscene_writer as cutscene
from dialogue_writer import read_json
from image_workflow import require, sha

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = re.compile(r"battle/script/(?:character|interrupt|item|message)/[a-z0-9_]+\.msb\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")
SCRIPT_FIELDS = {"script", "source_msb_sha256", "source_cdb_sha256", "record_count", "messages"}


def scan(data):
    """Read END-terminated records after the four-byte battle header.

    Some records contain embedded tables or page controls. Keep them visible in
    the inventory, but do not offer them for editing until their format is known.
    Null-terminated strings after the last END are not dialogue records.
    """
    require(data[:4] == b"scr\x1a" and len(data) % 2 == 0, "Invalid battle script header")
    rows, start = [], 4
    for end in range(4, len(data) - 3, 2):
        if data[end:end + 2] != b"q\xff":
            continue
        require(data[end + 2:end + 4] == b"\0\0", "Invalid battle record separator")
        words = struct.unpack("<" + "H" * ((end - start) // 2 + 1), data[start:end + 2])
        try:
            runs = cutscene.text_runs(words)
        except ValueError:
            runs = []
        rows.append({"offset": start, "end": end + 2,
                     "source_words_sha256": sha(data[start:end + 2]),
                     "runs": runs})
        start = end + 4
        if data[start:start + 2] == b"SS":
            start += 2
    return rows


def validate_pack(pack):
    require(isinstance(pack, dict) and set(pack) == {"format", "notes", "scripts"}
            and pack["format"] == "gintama-battle-v1", "Invalid battle translation pack")
    require(isinstance(pack["notes"], list) and len(pack["notes"]) <= 10
            and all(isinstance(n, str) and len(n) <= 1000 for n in pack["notes"]),
            "Invalid battle notes")
    require(isinstance(pack["scripts"], list) and 0 < len(pack["scripts"]) <= 128,
            "Invalid battle script list")
    scripts = set()
    for script in pack["scripts"]:
        require(isinstance(script, dict) and set(script) == SCRIPT_FIELDS, "Invalid battle script entry")
        path = script["script"]
        require(isinstance(path, str) and SCRIPT.fullmatch(path) and path not in scripts,
                "Unsupported or repeated battle script")
        scripts.add(path)
        for key in ("source_msb_sha256", "source_cdb_sha256"):
            require(isinstance(script[key], str) and HASH.fullmatch(script[key]), "Invalid battle source hash")
        require(type(script["record_count"]) is int and 0 <= script["record_count"] <= 20000,
                "Invalid battle record count")
        require(isinstance(script["messages"], list)
                and len(script["messages"]) <= script["record_count"], "Invalid battle messages")
        seen = set()
        for row in script["messages"]:
            require(isinstance(row, dict) and set(row) == {"offset", "source_words_sha256", "parts"},
                    "Invalid battle translation")
            offset = row["offset"]
            require(type(offset) is int and offset >= 4 and offset % 2 == 0 and offset not in seen,
                    "Invalid or repeated battle offset")
            seen.add(offset)
            require(isinstance(row["source_words_sha256"], str) and HASH.fullmatch(row["source_words_sha256"]),
                    "Invalid battle record hash")
            parts = row["parts"]
            require(isinstance(parts, list) and 0 < len(parts) <= 64
                    and all(isinstance(p, str) and p.isascii() and "\r" not in p and "\f" not in p for p in parts)
                    and any(p.strip() for p in parts), "Invalid battle English parts")
            cutscene.check_safe_text("".join(parts), "battle", 2500)
    return pack


def load_pack(path=None, *, root=ROOT):
    bundled = validate_pack(read_json(root / "reference/battle.json"))
    if path is None:
        return bundled
    edited = validate_pack(read_json(Path(path)))
    scripts = {row["script"]: {**row, "messages": list(row["messages"])} for row in bundled["scripts"]}
    for row in edited["scripts"]:
        original = scripts.get(row["script"])
        require(original is not None and all(row[k] == original[k] for k in SCRIPT_FIELDS - {"messages"}),
                "Battle script metadata differs from the supported original")
        messages = {r["offset"]: r for r in original["messages"]}
        messages.update({r["offset"]: r for r in row["messages"]})
        original["messages"] = sorted(messages.values(), key=lambda r: r["offset"])
    return {**bundled, "scripts": list(scripts.values())}


def prepare(scripts, pack, fonts, latin):
    validate_pack(pack)
    patches, report = {}, []
    for script in pack["scripts"]:
        if not script["messages"]:
            continue
        path = script["script"]
        cdb_path = path[:-3] + "cdb"
        require(path in scripts and cdb_path in scripts, "Missing original battle files")
        data, cdb = scripts[path], scripts[cdb_path]
        require(sha(data) == script["source_msb_sha256"] and sha(cdb) == script["source_cdb_sha256"],
                "Original battle files changed")
        records = scan(data)
        require(len(records) == script["record_count"], "Battle inventory count changed")
        indexed = {r["offset"]: r for r in records}
        for row in script["messages"]:
            original = indexed.get(row["offset"])
            require(original is not None and original["runs"], "Unsupported battle record or offset")
            require(row["source_words_sha256"] == original["source_words_sha256"], "Battle source span changed")
        patched, fonts, spans, details = cutscene.prepare(data, cdb, script, fonts, latin, minimum_offset=4)
        patches[path] = (patched, spans)
        report.append({"script": path, "messages": details["messages"],
                       "extra_font_records": details["extra_font_records"]})
    return patches, fonts, report
