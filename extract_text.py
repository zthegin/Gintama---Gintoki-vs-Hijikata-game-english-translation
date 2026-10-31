#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re
import struct
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
CONTROL = {0xFF70: "\n", 0xFF72: "\f"}
STRUCTURE_SUSPECTS = {
    0x0000: "\u27e6STRUCT:0x0000\u27e7",
    0x5353: "\u27e6STRUCT:0x5353\u27e7",
}
END = b"\x71\xff"
UNKNOWN = "\u27e60x{:04X}\u27e7"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def pick(provided, candidates, *, required=True):
    if provided is not None:
        p = pathlib.Path(provided).expanduser()
        if not p.is_absolute():
            p = HERE / p
        if not p.is_file():
            raise FileNotFoundError(p)
        return p.resolve()
    for name in candidates:
        p = HERE / name
        if p.is_file():
            return p.resolve()
    if required:
        raise FileNotFoundError(
            "Missing required file; tried: " + ", ".join(map(str, candidates))
        )
    return None


def get_tables(path):
    if path is None:
        return None, None, "not supplied"
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            matches = [
                n for n in z.namelist() if n.endswith("/source_name_tables.json")
            ]
            glosses = [n for n in z.namelist() if n.endswith("/glossary.json")]
            if len(matches) != 1 or len(glosses) != 1:
                raise ValueError(
                    "Source tables ZIP needs one source_name_tables.json and one glossary.json"
                )
            return (
                json.loads(z.read(matches[0])),
                json.loads(z.read(glosses[0])),
                str(path),
            )
    if path.name == "source_name_tables.json":
        gp = path.with_name("glossary.json")
        if not gp.is_file():
            raise FileNotFoundError(gp)
        return (
            json.loads(path.read_text(encoding="utf-8")),
            json.loads(gp.read_text(encoding="utf-8")),
            str(path.parent),
        )
    raise ValueError("--tables must be source tables ZIP or source_name_tables.json")


def decode_map(tables, existing):
    seen = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    skipped = []
    for category, rows in tables.items():
        for row in rows:
            for field, obj in row.items():
                if not (
                    isinstance(obj, dict)
                    and isinstance(obj.get("text"), str)
                    and isinstance(obj.get("raw_words"), list)
                ):
                    continue
                text = obj["text"]
                words = obj["raw_words"][:]
                if words and words[-1] in (0, 0xFF71):
                    words = words[:-1]
                if len(text) != len(words):
                    skipped.append(
                        {
                            "category": category,
                            "stable_id": row.get("stable_id"),
                            "field": field,
                            "reason": "alignment length mismatch",
                        }
                    )
                    continue
                for char, code in zip(text, words):
                    if code < 0xFF00:
                        seen[code]["source_name_tables"][char] += 1
    # Only bitmap transcriptions can train the map; contextual guesses cannot.
    for entry in existing:
        if (
            re.fullmatch(r"v\d+_ladies4_context", entry.get("origin_batch", ""))
            or entry.get("origin_batch") == "context_inference"
        ):
            continue
        t = entry.get("japanese_recovered", "")
        w = entry.get("_verified_source_words")
        if (
            not isinstance(t, str)
            or not w
            or len(t) != len(w) - 1
            or "\u27e6" in t
            or "\ufffd" in t
        ):
            continue
        for c, code in zip(t, w[:-1]):
            if code < 0xFF00:
                seen[code]["bitmap_transcription"][c] += 1
    mapping = {}
    provenance = {}
    conflicts = []
    for code, by_source in seen.items():
        chars = set().union(*(set(d) for d in by_source.values()))
        if len(chars) > 1:
            conflicts.append(
                {
                    "code": f"0x{code:04X}",
                    "readings": {
                        source: dict(counter) for source, counter in by_source.items()
                    },
                }
            )
        else:
            mapping[code] = next(iter(chars))
            provenance[code] = (
                "source_name_tables"
                if "source_name_tables" in by_source
                else "bitmap_transcription"
            )
    return mapping, provenance, conflicts, skipped


def extract(data):
    if len(data) % 2:
        raise ValueError("MSB size is not aligned to 16-bit words")
    if data[:4] != b"scr\x1a":
        raise ValueError(
            "Unrecognized MSB header: expected scr\\x1a; refusing speculative extraction"
        )
    # Observed original scr header occupies the first 16 bytes.
    cursor = 16
    records = []
    idx = 0
    while True:
        end = data.find(END, cursor)
        while end != -1 and (end - cursor) % 2:
            end = data.find(END, end + 1)
        if end < 0:
            break
        if (end + 4 > len(data)) or data[end + 2 : end + 4] != b"\x00\x00":
            raise ValueError(f"Missing 0x0000 separator after text at 0x{end:X}")
        if end < cursor:
            raise ValueError("Overlapping records")
        idx += 1
        raw = data[cursor : end + 2]
        if not raw or len(raw) % 2:
            raise ValueError(f"Invalid message length at 0x{cursor:X}")
        words = list(struct.unpack("<" + "H" * (len(raw) // 2), raw))
        if words[-1] != 0xFF71:
            raise AssertionError("Missing terminator")
        records.append(
            {
                "sequence": idx,
                "offset": cursor,
                "words": words,
                "source_words_sha256": sha(raw),
            }
        )
        cursor = end + 4
        if data[cursor : cursor + 2] == b"SS":
            cursor += 2
    return (
        records,
        data[cursor:],
        {"header_hex": data[:16].hex(), "first_text_offset_hex": "0x10"},
    )


def source_pointers(cdb, offsets):
    possible = collections.defaultdict(list)
    if cdb is None:
        return possible
    pos = 0
    while True:
        i = cdb.find(b"\x82", pos)
        if i < 0 or i + 5 > len(cdb):
            break
        dest = struct.unpack_from("<I", cdb, i + 1)[0]
        if dest in offsets:
            possible[dest].append(f"0x{i + 1:X}")
        pos = i + 1
    return possible


def main():
    p = argparse.ArgumentParser(
        description="Read-only Gintama MSB -> complete JSON, translation batches, optional ZIP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--msb", type=pathlib.Path)
    p.add_argument("--cdb", type=pathlib.Path)
    p.add_argument(
        "--tables",
        type=pathlib.Path,
        help="Source tables ZIP or source_name_tables.json",
    )
    p.add_argument(
        "--existing", type=pathlib.Path, help="Existing translated messages JSON"
    )
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument(
        "--out", type=pathlib.Path, default=pathlib.Path("translation_export")
    )
    p.add_argument("--no-zip", action="store_true")
    args = p.parse_args()
    if not 1 <= args.batch_size <= 2000:
        raise ValueError("Batch size must be 1–2000")
    msb = pick(
        args.msb, ["root/field/script/fld_scr.msb", "fld_scr(2).msb", "fld_scr.msb"]
    )
    cdb = pick(
        args.cdb, ["root/field/script/fld_scr.cdb", "fld_scr.cdb"], required=False
    )
    tables_path = pick(args.tables, ["source_tables.zip", "source_name_tables.json"])
    old = pick(args.existing, ["translations.json"], required=False)
    out = args.out.expanduser()
    if not out.is_absolute():
        out = HERE / out
    if out.is_symlink() or any(parent.is_symlink() for parent in out.parents):
        raise ValueError("Symlink extraction output refused")
    out = out.resolve()
    inputs = {x for x in [msb, cdb, tables_path, old] if x}
    if out in inputs or out == HERE or out == HERE / "root" or out == msb.parent:
        raise ValueError(
            "Choose a separate output directory, never your original asset folder"
        )
    if out.exists():
        raise ValueError("Extraction output already exists; choose a new directory")
    zip_path = out.parent / (out.name + ".zip")
    if not args.no_zip and (zip_path.exists() or zip_path.is_symlink()):
        raise ValueError("Extraction ZIP already exists; choose a new output name")
    data = msb.read_bytes()
    cdb_bytes = cdb.read_bytes() if cdb else None
    tables, glossary, glossary_source = get_tables(tables_path)
    records, tail, hdr = extract(data)
    offsets = {r["offset"] for r in records}
    by_offset = {r["offset"]: r for r in records}
    previous = json.loads(old.read_text(encoding="utf-8")) if old else {"messages": []}
    for kind, blob in [("msb", data), ("cdb", cdb_bytes)]:
        expected = previous.get("source_" + kind + "_sha256")
        if expected and (blob is None or expected != sha(blob)):
            raise ValueError(
                f"Existing translation database expects a different {kind.upper()} SHA256; do not mix game versions"
            )
    existing = []
    rejected = []
    for item in previous.get("messages", []):
        try:
            off = int(item["offset_hex"], 16)
        except (ValueError, KeyError, TypeError):
            rejected.append(
                {"offset": item.get("offset_hex"), "reason": "invalid offset"}
            )
            continue
        r = by_offset.get(off)
        if (
            r is None
            or r["source_words_sha256"] != item.get("source_words_sha256")
            or len(r["words"]) != item.get("word_count")
        ):
            rejected.append(
                {
                    "offset": item.get("offset_hex"),
                    "reason": "missing or mismatched source span",
                }
            )
            continue
        verified = dict(item)
        verified["_verified_source_words"] = r["words"]
        existing.append(verified)
    if rejected:
        raise ValueError(
            f"{len(rejected)} previous translations failed source-span verification; first: {rejected[0]}"
        )
    emap = {int(e["offset_hex"], 16): e for e in existing}
    decode, provenance, conflicts, skipped = decode_map(tables, existing)
    cdb_refs = source_pointers(cdb_bytes, offsets)
    grouped = collections.defaultdict(list)
    for r in records:
        r["group_id"] = (
            "exact_words_"
            + sha(struct.pack("<" + "H" * len(r["words"]), *r["words"]))[:20]
        )
        grouped[r["group_id"]].append(r["offset"])
    first_per_group = {g: members[0] for g, members in grouped.items()}
    canonical_existing = {}
    for r in records:
        e = emap.get(r["offset"])
        if e and isinstance(e.get("english"), str) and e["english"].strip():
            canonical_existing.setdefault(r["group_id"], e["english"])
    records_out = []
    glyph_counter = collections.Counter()
    affected = 0
    extra_ctrl = collections.Counter()
    for r in records:
        off = r["offset"]
        words = r["words"]
        unknown = []
        special = []
        structure = []
        chars = []
        covered_by = []
        for w in words[:-1]:
            if w in STRUCTURE_SUSPECTS:
                chars.append(STRUCTURE_SUSPECTS[w])
                structure.append(f"0x{w:04X}")
                continue
            if w in CONTROL:
                chars.append(CONTROL[w])
                continue
            if w >= 0xFF00:
                chars.append(f"\u27e6CTRL:0x{w:04X}\u27e7")
                extra_ctrl[w] += 1
                special.append(f"0x{w:04X}")
                continue
            if w in decode:
                chars.append(decode[w])
                covered_by.append(provenance[w])
            else:
                chars.append(UNKNOWN.format(w))
                glyph_counter[w] += 1
                unknown.append(f"0x{w:04X}")
        text = "".join(chars)
        if unknown:
            affected += 1
        e = emap.get(off)
        r_out = {
            "id": f"msb_{off:08X}",
            "sequence": r["sequence"],
            "offset_hex": f"0x{off:X}",
            "word_count": len(words),
            "source_words_sha256": r["source_words_sha256"],
            "raw_words_hex": [f"0x{w:04X}" for w in words],
            "japanese": text,
            "decode_status": "unresolved_glyphs"
            if unknown
            else (
                "structure_needs_review"
                if structure
                else ("inline_controls_need_review" if special else "mapped")
            ),
            "decoding_sources": sorted(set(covered_by)),
            "unknown_glyph_ids": sorted(set(unknown)),
            "inline_control_ids": sorted(set(special)),
            "structure_candidates": sorted(set(structure)),
            "line_breaks": words.count(0xFF70),
            "page_breaks": words.count(0xFF72),
            "duplicate_group": r["group_id"],
            "duplicate_count": len(grouped[r["group_id"]]),
            "is_duplicate_representative": first_per_group[r["group_id"]] == off,
            "cdb_candidate_operand_offsets": cdb_refs.get(off, []),
            "cdb_pointer_warning": "Heuristic 0x82 + little-endian offset matches only; not verified safe pointers"
            if cdb
            else "CDB not supplied",
            "english": e.get("english") if e else None,
            "translation_status": (e.get("translation_status") or "previous_draft")
            if e
            else "not_translated",
            "previous_translation_notes": (e.get("translation_notes", e.get("notes")))
            if e
            else None,
            "fixed_slot_validated": bool(e.get("fixed_slot_validated", False))
            if e
            else False,
            "suggested_translation_from_exact_duplicate": canonical_existing.get(
                r["group_id"]
            )
            if not e
            else None,
        }
        records_out.append(r_out)
    # Only fully-decoded, as-yet-untranslated, one-per-exact-duplicate records go to ordinary translation batches.
    by_id = {r["id"]: r for r in records_out}
    ready = []
    needs_review = []
    memory = []
    for i, r in enumerate(records_out):
        if (
            r["unknown_glyph_ids"]
            or r["inline_control_ids"]
            or r["structure_candidates"]
        ):
            if r["is_duplicate_representative"] and not r["english"]:
                needs_review.append(
                    {
                        "id": r["id"],
                        "offset_hex": r["offset_hex"],
                        "japanese_with_markers": r["japanese"],
                        "unknown_glyph_ids": r["unknown_glyph_ids"],
                        "inline_control_ids": r["inline_control_ids"],
                        "structure_candidates": r["structure_candidates"],
                        "source_words_sha256": r["source_words_sha256"],
                    }
                )
            continue
        if (
            r["english"]
            or r["duplicate_group"] in canonical_existing
            or not r["is_duplicate_representative"]
        ):
            continue

        def neighbor(index):
            if 0 <= index < len(records_out):
                n = records_out[index]
                return {
                    "id": n["id"],
                    "japanese": n["japanese"][:300],
                    "caution": "source adjacency, NOT verified gameplay dialogue order",
                }
            return None

        ready.append(
            {
                "id": r["id"],
                "offset_hex": r["offset_hex"],
                "source_words_sha256": r["source_words_sha256"],
                "japanese": r["japanese"],
                "english": None,
                "translation_status": "to_translate",
                "duplicate_group": r["duplicate_group"],
                "duplicate_count": r["duplicate_count"],
                "context_before": neighbor(i - 1),
                "context_after": neighbor(i + 1),
                "translator_note": None,
                "game_compatible_english": None,
            }
        )
    for r in records_out:
        if r["english"]:
            memory.append(
                {
                    "id": r["id"],
                    "offset_hex": r["offset_hex"],
                    "japanese": r["japanese"],
                    "english": r["english"],
                    "status": r["translation_status"],
                    "duplicate_group": r["duplicate_group"],
                    "warning": "Natural-English draft; not proof of in-game fit",
                }
            )
    out.mkdir(parents=True)
    source = {
        "msb_path": str(msb),
        "msb_sha256": sha(data),
        "msb_bytes": len(data),
        "cdb_path": str(cdb) if cdb else None,
        "cdb_sha256": sha(cdb_bytes) if cdb_bytes is not None else None,
        "tables_source": glossary_source,
        "previous_translations": str(old) if old else None,
        **hdr,
        "trailing_bytes_after_final_terminated_message_hex": tail.hex(),
        "warning": "Any trailing bytes are retained as audit information, NOT invented as a message",
    }
    report = {
        "format": "gintama-msb-full-extraction-v1",
        "source": source,
        "counts": {
            "terminated_records": len(records),
            "exact_unique_raw_word_groups": len(grouped),
            "previously_translated_records_verified": len(emap),
            "previous_translation_source_failures": len(rejected),
            "glyph_map_entries": len(decode),
            "glyph_map_conflicts": len(conflicts),
            "records_with_unmapped_glyphs": affected,
            "unique_unmapped_glyph_ids": len(glyph_counter),
            "unmapped_glyph_instances": sum(glyph_counter.values()),
            "records_with_other_inline_control": sum(
                bool(r["inline_control_ids"]) for r in records_out
            ),
            "records_with_embedded_structure_candidates": sum(
                bool(r["structure_candidates"]) for r in records_out
            ),
            "untranslated_unique_ready_to_translate": len(ready),
            "untranslated_unique_needing_glyph_or_control_review": len(needs_review),
            "previous_translated_memory_entries": len(memory),
            "cdb_candidate_operand_matches": sum(map(len, cdb_refs.values())),
        },
        "unmapped_glyphs_by_frequency": [
            {"id": f"0x{code:04X}", "instances": n}
            for code, n in glyph_counter.most_common()
        ],
        "nonstandard_inline_controls": {
            f"0x{k:04X}": v for k, v in sorted(extra_ctrl.items())
        },
        "conflicting_decoder_evidence": conflicts,
        "skipped_misaligned_name_table_fields": skipped,
        "limitations": [
            "The source-name tables are not a complete font decoder. Unknown glyphs are preserved as markers.",
            "Bitmap transcriptions supply additional mappings; context-inferred glyphs never train the map.",
            "Embedded 0x0000 and 0x5353 word IDs may be structure/padding; they are flagged separately for structural review.",
            "Source file order and adjacent records do not prove gameplay conversation order.",
            "0x82 CDB operand matches are heuristic; no binary patching or pointer relocation is performed.",
            "Existing English strings are natural-language drafts and are not necessarily fitted to DS font/slot budgets.",
        ],
    }
    dump(out / "manifest.json", report)
    dump(
        out / "all_records.json",
        {"format": report["format"], "source": source, "records": records_out},
    )
    dump(
        out / "needs_glyph_review.json",
        {
            "format": report["format"],
            "records": needs_review,
            "note": "Resolve source glyphs, structure and inline controls with original font or project tooling before translating.",
        },
    )
    dump(
        out / "translation_memory.json",
        {"format": "gintama-translation-memory-v1", "entries": memory},
    )
    dump(
        out / "glyph_map.json",
        {
            "map": {
                f"0x{k:04X}": {"character": v, "source": provenance[k]}
                for k, v in sorted(decode.items())
            },
            "conflicts": conflicts,
            "not_a_complete_font_map": True,
        },
    )
    dump(out / "glossary.json", glossary)
    batch_paths = []
    for j in range(0, len(ready), args.batch_size):
        name = f"batch_{j // args.batch_size + 1:04d}.json"
        bp = out / "ready_to_translate_batches" / name
        dump(
            bp,
            {
                "format": "gintama-translation-batch-v1",
                "batch_number": j // args.batch_size + 1,
                "glossary_version": glossary.get("version"),
                "instructions": [
                    "Translate natural English in english; leave all Japanese, id, offset, hash, duplicate group and context fields unchanged.",
                    "Use the supplied glossary. Gin Tama refers to the collectible; Gintama refers to the franchise.",
                    "Preserve the meaning, character voice, jokes and page-break structure (\\f); wrapping can be reworked for the game font later.",
                    "Do not invent unknown glyphs. There should be none in ready-to-translate batches.",
                    "Do not patch the ROM: natural English is a separate deliverable.",
                ],
                "records": ready[j : j + args.batch_size],
            },
        )
        batch_paths.append(str(bp.relative_to(out)))
    dump(
        out / "batch_index.json",
        {
            "batch_size": args.batch_size,
            "batch_count": len(batch_paths),
            "batches": batch_paths,
            "ready_unique_count": len(ready),
        },
    )
    readme = f"""# Gintama read-only MSB export

This directory was generated by `extract_text.py` from the exact files listed in `manifest.json`.
Original MSB, CDB, ROM, save states, and game assets were **not edited**.

- `all_records.json`: every 0xFF71-terminated message, in source order, with raw 16-bit word IDs, absolute offsets, SHA256 checksums, reconstructed Japanese, control markers, duplicate groups and any previously translated English.
- `glossary.json`: project terminology policy. Keep **Gin Tama** (game collectible) separate from **Gintama** (franchise).
- `glyph_map.json`: evidence-backed character mappings and conflicts.
- `translation_memory.json`: previously translated drafts, not automatically approved as game compatible.
- `ready_to_translate_batches/`: {len(ready):,} unique fully-decoded untranslated entries in {len(batch_paths)} batches of up to {args.batch_size}. Translate these one JSON file at a time.
- `needs_glyph_review.json`: {len(needs_review):,} representative untranslated entries with unknown original glyphs, embedded structure candidates or other inline control codes. Resolve before translating, never guess.
- `manifest.json`: overall counts, hashes, extraction limitations and an unmapped-glyph frequency list.

## Important parsing details

The actual text delimiter is word `0xFF71` (END), followed by `0x0000`. Some records also have an `SS` prefix marker (`0x5353`) which is NOT message text. Text begins after that marker. `0xFF70` = newline, `0xFF72` = page break. All other `0xFFxx` values are emitted as explicit control tokens. Unrecognized glyphs appear as `⟦0xNNNN⟧`; structural candidates 0x0000/0x5353 are labeled separately. Raw word arrays and source SHA256 are retained to avoid any silent data loss. Source sequence is NOT guaranteed gameplay sequence.

## Working through batches

Read `manifest.json`, `glossary.json` and `translation_memory.json` before editing a batch. Work through one file in `ready_to_translate_batches` at a time. Edit only the English field; leave source IDs, hashes, Japanese, offsets and controls unchanged. Keep page breaks (`\\f`) and save finished files under a separate directory such as `translated_batches`. Record uncertain references for review. Entries in `needs_glyph_review.json` must wait for source-font verification. Check text widths, storage space and in-game layout separately when building a patch.

To run again locally (Windows PowerShell), place the script alongside the existing project scripts and use:
`py -3 .\\extract_text.py --batch-size 200`
To point at a specific game: `py -3 .\\extract_text.py --msb ".\\root\\field\\script\\fld_scr.msb" --cdb ".\\root\\field\\script\\fld_scr.cdb" --tables ".\\source_tables.zip"`
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    if not args.no_zip:
        with zipfile.ZipFile(zip_path, "x", zipfile.ZIP_DEFLATED, compresslevel=8) as z:
            for path in sorted(out.rglob("*")):
                if path.is_file():
                    z.write(path, arcname=str(path.relative_to(out)))
    print("Source MSB SHA256:", sha(data))
    print("Terminated records:", len(records), "exact unique groups:", len(grouped))
    print("Previous valid translations:", len(emap), "glyphs mapped:", len(decode))
    print(
        "Ready unique entries:",
        len(ready),
        "batches:",
        len(batch_paths),
        "unresolved representatives:",
        len(needs_review),
    )
    print("Export:", out)
    if not args.no_zip:
        print("ZIP:", zip_path)
    print("NO source or ROM files modified; NOT a game patch.")


if __name__ == "__main__":
    main()
