#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import csv
import html
import json
import struct
import zipfile
from pathlib import Path

from sync_csv import escape
from dialogue_writer import LINE, PAGE, read_json, record_terminator, words_at
from field_markup import INLINE_CONTROLS, ACCENT
from image_workflow import sha

ROOT = Path(__file__).resolve().parents[1]


def collect(zip_path: Path, batch_path: Path) -> list[dict]:
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    if any(entry["id"].startswith("gfx_") for entry in batch["records"]):
        raise ValueError(
            "Image batches use tools/image_workflow.py or the Images editor, not the MSB text viewer"
        )
    with zipfile.ZipFile(zip_path) as archive:
        source = json.loads(archive.read("all_records.json"))["records"]
    lookup = {entry["id"]: entry for entry in source}
    rows = []
    for entry in batch["records"]:
        original = lookup[entry["id"]]
        if original["source_words_sha256"] != entry["source_words_sha256"]:
            raise ValueError(f"Source hash mismatch: {entry['id']}")
        rows.append(
            {
                "id": entry["id"],
                "japanese": original["japanese"],
                "english": entry["english"] or "",
                "translator_note": entry["translator_note"] or "",
                "decode_status": original["decode_status"],
            }
        )
    return rows


def collect_source(msb_path: Path, batch_path: Path, *, root: Path = ROOT) -> list[dict]:
    """Read only hash-verified message spans from the matching local source file."""
    reference = read_json(root / "reference/record_index.json")
    field = msb_path.read_bytes()
    if sha(field) != reference["source_msb_sha256"]:
        raise ValueError("Original dialogue hash mismatch")
    lookup = {entry["id"]: entry for entry in reference["records"]}
    if len(lookup) != len(reference["records"]):
        raise ValueError("Duplicate reference ID")
    glyphs = read_json(root / "reference/glyph_codes_public.json")["codes"]
    batch = read_json(batch_path)
    rows, seen = [], set()
    markers = {LINE: "\n", PAGE: "\f", 0xFF81: "[red]", 0xFF82: "[blue]", 0xFF84: "[/color]"}
    markers.update({code: f"[ctrl:{code:04X}]" for code in INLINE_CONTROLS | {ACCENT}})
    for entry in batch["records"]:
        identifier = entry["id"]
        if identifier in seen or identifier not in lookup or not identifier.startswith("msb_"):
            raise ValueError("Unknown or duplicate dialogue ID: " + identifier)
        seen.add(identifier)
        indexed = lookup[identifier]
        if entry["source_words_sha256"] != indexed["source_words_sha256"]:
            raise ValueError("Source hash mismatch: " + identifier)
        raw_colors = indexed.get("raw_color_controls", False)
        if type(raw_colors) is not bool:
            raise ValueError("Invalid raw color control metadata")
        record_markers = dict(markers)
        if raw_colors:
            record_markers.update({code: f"[ctrl:{code:04X}]" for code in (0xFF81, 0xFF82, 0xFF83, 0xFF84)})
        terminator = record_terminator(indexed)
        words = words_at(field, int(indexed["offset_hex"], 16), terminator=terminator)
        raw = struct.pack("<" + "H" * len(words), *words)
        if sha(raw) != indexed["source_words_sha256"]:
            raise ValueError("Source span hash mismatch: " + identifier)
        suffix = indexed.get("trailing_controls", [])
        if not isinstance(suffix, list) or (suffix and
                (terminator != 0 or suffix != [0xFF81] or type(suffix[0]) is not int)):
            raise ValueError("Unsupported protected dialogue suffix")
        if len(words) <= len(suffix) + 1:
            raise ValueError("Empty dialogue source prefix")
        if suffix and words[-len(suffix)-1:-1] != suffix:
            raise ValueError("Protected dialogue suffix changed")
        editable = words[:-len(suffix)-1] if suffix else words[:-1]
        text = []
        for code in editable:
            if code in record_markers:
                text.append(record_markers[code])
            elif 1 <= code <= 6953 and f"0x{code:04X}" in glyphs:
                value = glyphs[f"0x{code:04X}"]
                if not isinstance(value, str) or len(value) != 1:
                    raise ValueError("Invalid source glyph mapping")
                text.append(value)
            else:
                raise ValueError(f"Unresolved source glyph or control: {code:04X}")
        rows.append({
            "id": identifier,
            "japanese": "".join(text),
            "english": entry["english"] or "",
            "translator_note": entry["translator_note"] or "",
            "decode_status": indexed["decode_status"],
        })
    return rows


def save(rows: list[dict], fmt: str, output: Path):
    if output.is_symlink() or any(parent.is_symlink() for parent in output.parents):
        raise ValueError("Symlink preview output refused")
    if output.exists():
        raise ValueError("Preview output already exists; choose a new filename")
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        with output.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=rows[0].keys(), lineterminator="\n"
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        key: escape(value)
                        if key in ("japanese", "english", "translator_note")
                        else value
                        for key, value in row.items()
                    }
                )
    elif fmt == "md":
        lines = [
            "# Private side-by-side translation preview",
            "",
            "Generated from your local extraction. Keep this file out of the public repository.",
            "",
        ]
        for row in rows:
            lines.extend(
                [
                    f"## {row['id']} ({row['decode_status']})",
                    "",
                    "Japanese:",
                    "",
                    "```text",
                    row["japanese"],
                    "```",
                    "",
                    "English:",
                    "",
                    "```text",
                    row["english"],
                    "```",
                    "",
                    f"Note: {row['translator_note']}",
                    "",
                ]
            )
        with output.open("x", encoding="utf-8") as stream:
            stream.write("\n".join(lines))
    elif fmt == "html":
        blocks = []
        for row in rows:
            rid = html.escape(row["id"])
            status = html.escape(row["decode_status"])
            japanese = html.escape(row["japanese"])
            english = html.escape(row["english"])
            note = html.escape(row["translator_note"])
            blocks.append(
                f"<section><h2>{rid} <small>{status}</small></h2>"
                f'<div class="pair"><pre lang="ja">{japanese}</pre><pre lang="en">{english}</pre></div>'
                f'<p class="note">{note}</p></section>'
            )
        content = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Private Gintama translation preview</title>
<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222}
section{border-bottom:1px solid #ddd;padding:1rem 0}h2{font-size:1.05rem}small{color:#666}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f5;padding:1rem;border-radius:6px;font:1rem/1.5 sans-serif}
.note{color:#555}@media(max-width:650px){.pair{grid-template-columns:1fr}}</style>
<h1>Private side-by-side translation preview</h1><p>Local use only. Do not publish the Japanese source script.</p>"""
        with output.open("x", encoding="utf-8") as stream:
            stream.write(content + "\n".join(blocks) + "</html>\n")
    else:
        raise ValueError(f"Unknown format: {fmt}")


def main():
    p = argparse.ArgumentParser(
        description="Build a private side-by-side preview from your matching MSB or extraction"
    )
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--extraction", "--zip", dest="extraction", type=Path,
        help="Your local private-extraction.zip (legacy span hashes)",
    )
    inputs.add_argument(
        "--msb", type=Path,
        help="Matching original field MSB; reads current trusted message spans",
    )
    p.add_argument(
        "--batch",
        type=Path,
        required=True,
        help="Path to a public translations batch JSON",
    )
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Private output path outside the repository",
    )
    p.add_argument("--format", choices=("csv", "md", "html"), default="html")
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = args.out.expanduser()
    resolved = output.resolve()
    if resolved.is_relative_to(repo):
        p.error(
            "The private source preview must be written OUTSIDE the public repository"
        )
    source_path = args.msb if args.msb is not None else args.extraction
    if resolved in {source_path.resolve(), args.batch.resolve()}:
        p.error("Preview output must be separate from the source and batch inputs")
    rows = (collect_source(args.msb, args.batch, root=repo)
            if args.msb is not None else collect(args.extraction, args.batch))
    save(rows, args.format, output)
    print(f"Wrote {len(rows)} records to {resolved} (PRIVATE LOCAL VIEW)")


if __name__ == "__main__":
    main()

