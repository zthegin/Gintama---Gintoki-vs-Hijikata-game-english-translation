#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import csv
import html
import json
import zipfile
from pathlib import Path

from sync_csv import escape


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
        description="Build private side-by-side CSV, Markdown or HTML from your own extraction"
    )
    p.add_argument(
        "--extraction",
        type=Path,
        required=True,
        help="Your local private-extraction.zip",
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
    if resolved in {args.extraction.resolve(), args.batch.resolve()}:
        p.error("Preview output must be separate from the extraction and batch inputs")
    rows = collect(args.extraction, args.batch)
    save(rows, args.format, output)
    print(f"Wrote {len(rows)} records to {resolved} (PRIVATE LOCAL VIEW)")


if __name__ == "__main__":
    main()
