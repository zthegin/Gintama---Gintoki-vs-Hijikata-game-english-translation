#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

from rom_patch import header, sha256


def package(
    patch_file: Path, manifest_file: Path, guide: Path, tool: Path, output: Path
) -> None:
    patch = patch_file.read_bytes()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    info = header(patch)
    required = ("source_sha256", "target_sha256", "patch_sha256")
    if any(
        not isinstance(manifest.get(key), str)
        or not re.fullmatch(r"[0-9a-f]{64}", manifest[key])
        for key in required
    ):
        raise ValueError("Manifest is missing a valid SHA-256 digest")
    if (
        manifest.get("format") != "gintama-bps-release-v1"
        or manifest.get("patch_sha256") != sha256(patch)
        or manifest.get("patch_filename") != patch_file.name
        or manifest.get("source_size") != info["source_size"]
        or manifest.get("target_size") != info["target_size"]
    ):
        raise ValueError("Patch and manifest disagree")
    if patch_file.suffix.lower() != ".bps" or manifest_file.suffix.lower() != ".json":
        raise ValueError("Expected a .bps patch and a .json manifest")
    if output.exists():
        raise ValueError("Release ZIP already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [
        (patch_file.name, patch),
        (manifest_file.name, manifest_file.read_bytes()),
        ("rom_patch.py", tool.read_bytes()),
        ("HOW_TO_APPLY.md", guide.read_bytes()),
        *[
            (name, (Path(__file__).resolve().parents[1] / name).read_bytes())
            for name in ["LICENSE", "RIGHTS.md"]
        ],
    ]
    if len({name for name, _ in files}) != len(files):
        raise ValueError("Duplicate release filenames")
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files:
            archive.writestr(name, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != {
            entry[0] for entry in files
        }:
            raise ValueError("Broken release ZIP")
        if any(
            Path(name).suffix.lower()
            in {".nds", ".srl", ".msb", ".cdb", ".bin", ".sav", ".ml1"}
            for name in archive.namelist()
        ):
            raise ValueError("Game asset found in release ZIP")
    print(f"Created patch release: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Package a BPS patch for a GitHub release"
    )
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--guide",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "docs/APPLY_PATCH.md",
    )
    parser.add_argument(
        "--tool", type=Path, default=Path(__file__).resolve().parent / "rom_patch.py"
    )
    args = parser.parse_args()
    try:
        package(args.patch, args.manifest, args.guide, args.tool, args.output)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Error: {exc}\n")
