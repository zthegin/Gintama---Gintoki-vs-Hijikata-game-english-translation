#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import unicodedata
from pathlib import Path

from check_public_tree import check, encoded_blocks, public_names, strict_json, strings
from image_workflow import lz10, nds_files

ROOT = Path(__file__).resolve().parents[1]
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]{8,}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text) if c.isalnum())


def compare(root, fingerprints, source_grams):
    matches = []
    checked = 0
    for name in public_names(root):
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        raw = path.read_bytes()
        checked += 1
        if digest(raw) in fingerprints:
            matches.append({"file": name.as_posix(), "kind": "exact original asset"})
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError:
            continue
        texts = [text]
        if name.suffix.lower() == ".json":
            try:
                texts += list(strings(strict_json(text)))
            except ValueError:
                continue
        if any(
            digest(blob) in fingerprints
            for value in texts
            for blob in encoded_blocks(value)
        ):
            matches.append({"file": name.as_posix(), "kind": "encoded original asset"})
        found = False
        for value in texts:
            for run in JAPANESE.findall(normalize(value)):
                if any(run[i : i + 8] in source_grams for i in range(len(run) - 7)):
                    found = True
                    break
            if found:
                break
        if found:
            matches.append(
                {"file": name.as_posix(), "kind": "source-script text match"}
            )
    return {
        "files_compared": checked,
        "source_fingerprints_tested": len(fingerprints),
        "script_fingerprints_tested": len(source_grams),
        "matches": matches,
    }


def source_index(rom, root):
    catalog = strict_json((root / "graphics/catalog.json").read_text(encoding="utf-8"))
    if digest(rom) != catalog["source_rom_sha256"]:
        raise ValueError("Use the matching unmodified legally obtained ROM")
    files = nds_files(rom)
    fingerprints = {digest(rom)}
    for left, right in files.values():
        if right - left >= 64:
            fingerprints.add(digest(rom[left:right]))
    for offset, size_offset in [(0x20, 0x2C), (0x30, 0x3C)]:
        start = struct.unpack_from("<I", rom, offset)[0]
        size = struct.unpack_from("<I", rom, size_offset)[0]
        if start and size >= 64 and start + size <= len(rom):
            fingerprints.add(digest(rom[start : start + size]))
    left, right = files[catalog["source_container"]]
    container = rom[left:right]
    for entry in catalog["entries"]:
        fingerprints.add(digest(lz10(container, entry["offset"])[0]))
    msb_left, msb_right = files["field/script/fld_scr.msb"]
    msb = rom[msb_left:msb_right]
    codes = strict_json(
        (root / "reference/glyph_codes_public.json").read_text(encoding="utf-8")
    )["codes"]
    records = strict_json(
        (root / "reference/record_index.json").read_text(encoding="utf-8")
    )["records"]
    grams = set()
    messages = 0
    for record in records:
        if record.get("kind") == "graphic":
            continue
        offset = int(record["offset_hex"], 16)
        pos = offset
        text = []
        while pos + 1 < len(msb) and pos - offset < 10000:
            code = struct.unpack_from("<H", msb, pos)[0]
            pos += 2
            if code == 0xFF71:
                break
            text.append(codes.get(f"0x{code:04X}", " "))
        else:
            continue
        raw = msb[offset:pos]
        if digest(raw) != record["source_words_sha256"]:
            raise ValueError("Script fingerprint mismatch")
        fingerprints.add(digest(raw))
        messages += 1
        for run in JAPANESE.findall(normalize("".join(text))):
            grams.update(run[i : i + 8] for i in range(len(run) - 7))
    return fingerprints, grams, messages


def main():
    p = argparse.ArgumentParser(
        description="Compare publication files against a user's legally obtained original, without publishing source bytes"
    )
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--rom",
        type=Path,
        required=True,
        help="Your legally obtained, matching unmodified ROM; read only",
    )
    p.add_argument(
        "--out",
        type=Path,
        help="Optional private JSON report; no source text or bytes are stored",
    )
    a = p.parse_args()
    root = a.repo.resolve()
    try:
        issues = check(root)
        if issues:
            raise ValueError("Publication audit failed: " + "; ".join(issues))
        if not a.rom.is_file() or not 0 < a.rom.stat().st_size <= 512 * 1024 * 1024:
            raise ValueError("Missing or oversized source")
        before = digest(a.rom.read_bytes())
        fingerprints, grams, messages = source_index(a.rom.read_bytes(), root)
        report = compare(root, fingerprints, grams)
        report.update(
            source_records_compared=messages,
            passed=not report["matches"],
            scope="Exact whole-file/decompressed-name-image/encoded payload fingerprints and decoded Japanese script snippets. Not a complete rights/provenance assessment or proof against every transformation.",
        )
        if digest(a.rom.read_bytes()) != before:
            raise ValueError("Source changed during read-only audit")
        if a.out:
            target = a.out.resolve()
            if (
                target == a.rom.resolve()
                or a.out.exists()
                or a.out.is_symlink()
                or any(p.is_symlink() for p in a.out.parents)
            ):
                raise ValueError("Choose a new private report path")
            if target.is_relative_to(root) and target.relative_to(root).parts[
                0
            ] not in {"local", "private"}:
                raise ValueError("Keep source-audit reports private")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    except (OSError, ValueError, KeyError, struct.error) as e:
        p.exit(1, str(e) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
