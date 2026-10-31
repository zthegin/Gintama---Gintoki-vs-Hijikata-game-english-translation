#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path

if __package__:
    from .check_public_tree import (
        REVIEWED_SCREENSHOTS,
        check,
        reviewed_screenshot,
    )
else:
    from check_public_tree import (
        REVIEWED_SCREENSHOTS,
        check,
        reviewed_screenshot,
    )

from validate_pr import check_repo

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPOSITORY = "zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation"


def generated_paths():
    paths = {
        ".nojekyll",
        ".gintama-site-build",
        "LICENSE",
        "RIGHTS.md",
        "assets/catalog.json",
        "assets/glyphs.json",
        "assets/glossary.json",
        "assets/opening_scene.json",
        "assets/battle.json",
        "assets/graphics/catalog.json",
        "assets/graphics/pixel_font.json",
        "assets/graphics/translations.json",
    }
    paths.update(
        path.name
        for path in (ROOT / "web").iterdir()
        if path.is_file() and path.suffix in {".html", ".css", ".js", ".mjs", ".json"}
    )
    paths.update("screenshots/" + Path(name).name for name in REVIEWED_SCREENSHOTS)
    for path in (ROOT / "translations").glob("**/*.json"):
        if path.parent.name != "graphics":
            relative = path.relative_to(ROOT / "translations").as_posix()
            paths.update(
                {"assets/translations/" + relative, "assets/metadata/" + relative}
            )
    return paths


def check_existing_site(out):
    expected = generated_paths()
    directories = {
        parent.as_posix()
        for name in expected
        for parent in Path(name).parents
        if parent != Path(".")
    }
    for path in out.rglob("*"):
        relative = path.relative_to(out).as_posix()
        if path.is_symlink() or relative not in (
            directories if path.is_dir() else expected
        ):
            raise ValueError(f"Refusing to delete unexpected site content: {relative}")


def build(out: Path, *, repository: str | None = None):
    # An explicit source repository prevents a separate Pages repo receiving issues.
    repository = (
        repository
        if repository is not None
        else os.environ.get("GITHUB_REPOSITORY") or SOURCE_REPOSITORY
    )
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repository) or any(
        part in {".", ".."} for part in repository.split("/")
    ):
        raise ValueError("Repository must be owner/name, not a URL or other text")
    if out.is_symlink() or any(parent.is_symlink() for parent in out.parents):
        raise ValueError("Symlink output refused")
    out = out.resolve()
    if out == ROOT or out.is_relative_to(ROOT) or ROOT.is_relative_to(out):
        raise ValueError(
            "Build the site outside the repository; do not include private game files"
        )
    if out.exists():
        if not out.is_dir() or out.is_symlink():
            raise ValueError("Output must be a directory, not a symlink")
        if (
            not (out / ".gintama-site-build").is_file()
            or (out / ".gintama-site-build").read_text(encoding="utf-8")
            != "Static translation editor build\n"
        ):
            raise ValueError(
                "Refusing to replace a directory not created by this site builder"
            )
        check_existing_site(out)
    issues = check(ROOT)
    if issues:
        raise ValueError(
            "Publication audit failed before site build: " + "; ".join(issues)
        )
    check_repo(ROOT)
    for name in REVIEWED_SCREENSHOTS:
        if not reviewed_screenshot(ROOT, name):
            raise ValueError(f"Unreviewed or changed screenshot: {name}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for source in (ROOT / "web").iterdir():
        if source.is_file() and source.suffix in {
            ".html",
            ".css",
            ".js",
            ".mjs",
            ".json",
        }:
            shutil.copy2(source, out / source.name)
    screenshots = out / "screenshots"
    screenshots.mkdir()
    for name in REVIEWED_SCREENSHOTS:
        shutil.copy2(ROOT / name, screenshots / Path(name).name)
    for notice in ["LICENSE", "RIGHTS.md"]:
        shutil.copy2(ROOT / notice, out / notice)
    assets = out / "assets"
    assets.mkdir()
    index = json.loads(
        (ROOT / "reference/record_index.json").read_text(encoding="utf-8")
    )
    lookup = {r["id"]: r for r in index["records"]}
    paths = []
    for source in sorted(
        (ROOT / "translations").glob("**/*.json"),
        key=lambda p: (p.parent.name != "ready", p.as_posix()),
    ):
        if source.is_symlink():
            raise ValueError("Symlink batch refused")
        if source.parent.name == "graphics":
            continue
        data = json.loads(source.read_text(encoding="utf-8"))
        rel = source.relative_to(ROOT / "translations")
        destination = assets / "translations" / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        items = []
        for record in data["records"]:
            original = lookup[record["id"]]
            if record["source_words_sha256"] != original["source_words_sha256"]:
                raise ValueError(f"Mismatched source hash in {source}: {record['id']}")
            items.append(
                {
                    field: original[field]
                    for field in (
                        "id",
                        "offset_hex",
                        "source_words_sha256",
                        "decode_status",
                        "page_breaks",
                        "line_breaks",
                        "duplicate_count",
                    )
                } | ({"control_sequence": original["control_sequence"]}
                     if "control_sequence" in original else {})
            )
        metadata = assets / "metadata" / rel
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(
            json.dumps(items, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        paths.append(
            {
                "batch": data["batch_id"],
                "file": rel.as_posix(),
                "count": len(items),
                "drafts": sum(bool(r["english"]) for r in data["records"]),
            }
        )
    for name, src in [
        ("glyphs.json", "glyph_codes_public.json"),
        ("glossary.json", "glossary.json"),
        ("opening_scene.json", "opening_scene.json"),
        ("battle.json", "battle.json"),
    ]:
        shutil.copy2(ROOT / "reference" / src, assets / name)
    graphics = assets / "graphics"
    graphics.mkdir()
    for name in ("catalog.json", "pixel_font.json"):
        shutil.copy2(ROOT / "graphics" / name, graphics / name)
    shutil.copy2(
        ROOT / "translations/graphics/gin_tama_names.json",
        graphics / "translations.json",
    )
    (assets / "catalog.json").write_text(
        json.dumps(
            {
                "format": "gintama-site-v1",
                "source_msb_sha256": index["source_msb_sha256"],
                "source_cdb_sha256": index["source_cdb_sha256"],
                "repository": repository,
                "batches": paths,
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / ".gintama-site-build").write_text(
        "Static translation editor build\n", encoding="utf-8"
    )
    issues = check(out, profile="site")
    if issues:
        raise ValueError("Finished site failed publication audit: " + "; ".join(issues))
    return {"batches": len(paths), "records": sum(b["count"] for b in paths)}


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Assemble the static translation editor from public repository data"
    )
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--repository",
        help="Contribution destination as owner/name; overrides the workflow repository",
    )
    args = p.parse_args()
    print(build(args.out, repository=args.repository))
