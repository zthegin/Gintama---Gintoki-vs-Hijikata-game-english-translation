#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

from check_public_tree import check
from sync_csv import escape
from validate_pr import check_repo


def export(root: Path, output: Path):
    root = root.resolve()
    if output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError("Symlink export destination refused")
    output = output.resolve()
    if output == root or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Export to a new directory outside the public source tree")
    if output.exists():
        raise ValueError("Export directory already exists; choose a new path")
    issues = check(root)
    if issues:
        raise ValueError("Publication audit failed before export: " + "; ".join(issues))
    check_repo(root)
    rows = []
    image_batches = []
    for path in sorted((root / "translations").glob("**/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.parent.name == "graphics":
            image_batches.append(data)
            continue
        for entry in data["records"]:
            if entry["english"] is not None:
                rows.append(entry)
    rows.sort(key=lambda row: row["id"])
    names = {"approved_translations.json", "approved_translations.csv"}
    for batch in image_batches:
        name = batch["batch_id"] + ".json"
        if name.casefold() in names:
            raise ValueError(f"Duplicate export filename: {name}")
        names.add(name.casefold())
    output.mkdir(parents=True)
    payload = {"format": "gintama-approved-translation-export-v2", "translations": rows}
    (output / "approved_translations.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for batch in image_batches:
        (output / (batch["batch_id"] + ".json")).write_text(
            json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if image_batches:
        for relative in (
            "graphics/catalog.json",
            "graphics/pixel_font.json",
            "graphics/lowercase_font.json",
            "graphics/extended_font.json",
            "tools/english_font.py",
            "tools/dialogue_writer.py",
            "tools/cutscene_writer.py",
            "tools/battle_writer.py",
            "reference/battle.json",
            "reference/opening_scene.json",
            "tools/text_policy.py",
            "tools/field_markup.py",
            "reference/record_index.json",
            "graphics/ui_recipes.json",
            "tools/build_ui.py",
            "tools/ui_tiles.py",
            "tools/ui_render.py",
            "tools/rom_patch.py",
            "requirements.txt",
            "tools/image_workflow.py",
            "tools/optimal_lz10.py",
            "translations/graphics/gin_tama_names.json",
            "csv/graphics/gin_tama_names.csv",
            "docs/IMAGE_WORKFLOW.md",
            "docs/APPLY_PATCH.md",
            "RIGHTS.md",
            "LICENSE",
        ):
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, target)
    with (output / "approved_translations.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("id", "source_words_sha256", "english", "translator_note"),
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    name: escape(row[name])
                    if name in ("english", "translator_note")
                    else row[name]
                    for name in writer.fieldnames
                }
            )
    issues = check(output, profile="export")
    if issues:
        raise ValueError(
            "Finished export failed publication audit: " + "; ".join(issues)
        )
    print(
        f"Exported {len(rows)} translations to {output} (JSON and CSV). No ROM files included."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export approved English records as JSON and CSV, without game assets"
    )
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parent.parent
    )
    parser.add_argument("--out", type=Path, required=True, help="Output DIRECTORY")
    args = parser.parse_args()
    export(args.repo, args.out)
