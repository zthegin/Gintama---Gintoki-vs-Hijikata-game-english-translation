#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import unicodedata
import zipfile
from pathlib import Path

if __package__:
    from .text_policy import SECRET
else:
    from text_policy import SECRET

BANNED = set(
    (
        ".nds .srl .rom .gba .gb .gbc .3ds .cia .nsp .xci .nca .wad .iso .cue .chd "
        ".msb .cdb .sav .srm .dsv .dst .ml0 .ml1 .ml2 .ml3 .ml4 .ml5 .ml6 .ml7 .ml8 .ml9 "
        ".bin .arm9 .arm7 .elf .bios .firmware .dat .img .narc .carc .szs .arc "
        ".nbfc .nbfp .nbfs .ncgr .nclr .nscr .ncer .nanr .nsbmd .nsbtx .nsbca .sdat .sseq .swav .swar .sbnk "
        ".ab .rws .rtb .rpb .tb .pb .z .bps .ips .ups .xdelta .vcdiff .patch "
        ".png .jpg .jpeg .gif .webp .svg .bmp .ico .tif .tiff .avif .heic .psd .ase .aseprite "
        ".wav .mp3 .ogg .flac .aac .m4a .mid .midi .mp4 .webm .avi .mkv .mov "
        ".ttf .otf .woff .woff2 .fnt .fon .zip .7z .rar .gz .tgz .bz2 .xz .tar .zst "
        ".pdf .exe .dll .com .scr .msi .bat .cmd .ps1 .vbs .jar .wasm .lnk"
    ).split()
)
ALLOWED = {
    ".py",
    ".json",
    ".csv",
    ".md",
    ".mjs",
    ".js",
    ".txt",
    ".css",
    ".html",
    ".yml",
    ".yaml",
}
SPECIAL = {".gitignore", ".gitattributes", "LICENSE", "NOTICE", "COPYING"}
PRIVATE_DIRS = {
    "local",
    "private",
    "private-extraction",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "site",
}
MAX_TRACKED_FILE = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_FILES = 10000
# Exact reviewed editor images only. Manifest edits cannot authorize images.
REVIEWED_SCREENSHOTS = {
    "docs/screenshots/image-label.png": "aa22d72a231ff6ceae90fa315273c3fb05216d02da41a028989aecc356354f95",
    "docs/screenshots/two-line-label.png": "a4a99557ccc11d86fa18c914e9ffa3c2f2af3648a848b2555f4fdbce10f2df6a",
    "docs/screenshots/dialogue-editor.png": "4e01304db8f51762ad20a564b559f0e52d47534115684ad4c42ffceb85137586",
}
SOURCE_FIELDS = {
    "japanese",
    "japaneseoriginal",
    "originaljapanese",
    "japanesetext",
    "japanesesource",
    "sourcejapanese",
    "originaldescriptionjapanese",
    "japanesewithmarkers",
    "japaneserecovered",
    "raworiginaltext",
    "originalscript",
    "scriptdump",
    "dialoguedump",
    "sourcetextdump",
    "sourceprose",
    "rawbytes",
    "rawdata",
    "rawwords",
    "rawwordshex",
    "originalpixels",
    "sourcepixels",
    "fontbitmap",
    "fontdata",
    "paletteentries",
    "palettedata",
    "tiledata",
    "rombytes",
    "romdata",
    "rompayload",
    "rombase64",
    "biosdata",
    "firmwaredata",
    "sourceasset",
    "originalasset",
    "originalbytes",
    "originaldata",
    "sourcebytes",
    "embeddedrom",
    "embeddedgame",
    "binarypayload",
}
JAPANESE_PROSE = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff][\u3040-\u30ff\u3400-\u9fff\u3000-\u303f\s]{5,}"
)
EMAIL_ADDRESS = re.compile(r"[A-Z0-9._%+\-]+@([A-Z0-9.\-]+\.[A-Z]{2,})", re.I)
HOME_DIRECTORY = re.compile(
    r"(?:[A-Z]:\\+Users\\+|/(?:Users|home)/)([^/\\\s\"<>]+)", re.I
)


def private_contact(value):
    normalized = unicodedata.normalize("NFKC", value)
    for match in EMAIL_ADDRESS.finditer(normalized):
        domain = match[1].lower()
        public_examples = {
            "example.com", "example.net", "example.org", "users.noreply.github.com"
        }
        if domain not in public_examples and not domain.endswith(
            (".invalid", ".example", ".test")
        ):
            return True
    placeholders = {
        "user", "username", "you", "example", "public", "runner",
        "<user>", "$user", "${user}",
    }
    return any(
        match[1].casefold() not in placeholders
        for match in HOME_DIRECTORY.finditer(normalized)
    )


BASE64_BLOCK = re.compile(
    r"(?<![A-Za-z0-9+/])(?:[A-Za-z0-9+/]{64,}[\r\n \t]*){4,}={0,2}"
)
HEX_BLOCK = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{256,}(?![0-9A-Fa-f])")
MAGIC = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!",
    b"\x1f\x8b",
    b"\xfd7zXZ",
    b"BZh",
    b"\x89PNG\r\n\x1a\n",
    b"GIF87a",
    b"GIF89a",
    b"\xff\xd8\xff",
    b"RIFF",
    b"OggS",
    b"fLaC",
    b"BPS1",
    b"PATCH",
    b"NARC",
    b"SDAT",
    b"RGCN",
    b"RLCN",
    b"RCSN",
    b"RECN",
    b"RNAN",
    b"MZ",
    b"\x7fELF",
    b"%PDF-",
    b"scr\x1a",
)


def normalize_key(value):
    return "".join(
        c for c in unicodedata.normalize("NFKC", str(value)).casefold() if c.isalnum()
    )


def source_payload(value):
    if isinstance(value, dict):
        return any(
            normalize_key(k) in SOURCE_FIELDS or source_payload(v)
            for k, v in value.items()
        )
    if isinstance(value, list):
        if len(value) >= 128 and all(type(v) is int and 0 <= v <= 65535 for v in value):
            return True
        return any(source_payload(v) for v in value)
    return False


def strict_json(text):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("Non-finite JSON number")

    value = json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)

    def finite(item):
        if isinstance(item, float) and (item != item or abs(item) == float("inf")):
            raise ValueError("Non-finite JSON number")
        if isinstance(item, dict):
            for part in item.values():
                finite(part)
        elif isinstance(item, list):
            for part in item:
                finite(part)

    finite(value)
    return value


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def encoded_blocks(text):
    for match in BASE64_BLOCK.finditer(text):
        candidate = re.sub(r"\s", "", match.group())
        if len(candidate) > MAX_TRACKED_FILE * 2:
            continue
        try:
            yield base64.b64decode(
                candidate + "=" * (-len(candidate) % 4), validate=True
            )
        except ValueError:
            pass
    for match in HEX_BLOCK.finditer(text):
        value = match.group()
        if len(value) % 2 == 0:
            yield bytes.fromhex(value)


def binary_payload(data, fingerprints=frozenset()):
    if data.startswith(MAGIC) or hashlib.sha256(data).hexdigest() in fingerprints:
        return True
    if len(data) >= 64 and (
        b"\0" in data or sum(x < 9 or 13 < x < 32 for x in data) > len(data) // 16
    ):
        return True
    try:
        decoded = data.decode("utf-8")
    except UnicodeError:
        return True
    return bool(JAPANESE_PROSE.search(decoded))


def public_names(root, *, include_private=False):
    result = []
    for parent, dirs, names in os.walk(root, followlinks=False):
        keep = []
        for name in dirs:
            path = Path(parent) / name
            if not include_private and (
                name == ".git" or name.casefold() in PRIVATE_DIRS
            ):
                continue
            if path.is_symlink():
                result.append(path.relative_to(root))
            else:
                keep.append(name)
        dirs[:] = keep
        result.extend((Path(parent) / name).relative_to(root) for name in names)
    return sorted(result)


def tracked_names(root):
    """Ignored directories can still be force-added to Git; audit those public paths too."""
    git = shutil.which("git")
    if git is None:
        return []
    top = subprocess.run(
        [git, "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if top.returncode or not root.is_relative_to(Path(top.stdout.strip()).resolve()):
        return []
    result = subprocess.run(
        [git, "-C", str(root), "ls-files", "-z", "--", "."], capture_output=True
    )
    if result.returncode:
        raise ValueError("Cannot inventory tracked publication paths")
    return [
        Path(p.decode("utf-8", "surrogateescape"))
        for p in result.stdout.split(b"\0")
        if p
    ]


def screenshot_key(name, profile):
    key = name.as_posix()
    if profile == "site" and key.startswith("screenshots/"):
        return "docs/" + key
    return key


def reviewed_screenshot(root, name, profile="source"):
    path = root / name
    expected = REVIEWED_SCREENSHOTS.get(screenshot_key(Path(name), profile))
    return bool(
        expected
        and path.is_file()
        and not path.is_symlink()
        and not any(p.is_symlink() for p in path.parents)
        and path.stat().st_size <= 250000
        and hashlib.sha256(path.read_bytes()).hexdigest() == expected
    )


def source_fingerprints(root):
    found = set()
    for rel in [
        "reference/record_index.json",
        "graphics/catalog.json",
        "assets/graphics/catalog.json",
    ]:
        path = root / rel
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size > MAX_TRACKED_FILE
        ):
            continue
        try:
            data = strict_json(path.read_text(encoding="utf-8-sig"))
        except (ValueError, RecursionError):
            continue

        def visit(item):
            if isinstance(item, dict):
                for key, value in item.items():
                    if (
                        key.startswith("source_")
                        and key.endswith("sha256")
                        and isinstance(value, str)
                        and re.fullmatch("[0-9a-f]{64}", value)
                    ):
                        found.add(value)
                    elif isinstance(value, (dict, list)):
                        visit(value)
            elif isinstance(item, list):
                for value in item:
                    visit(value)

        visit(data)
    return found


def check(
    root: Path, names: list[Path] | None = None, *, profile="source"
) -> list[str]:
    root = Path(root)
    if profile not in {"source", "site", "export"}:
        return ["Unknown publication profile"]
    if not root.is_dir() or root.is_symlink():
        return [f"Missing or symlinked source directory: {root}"]
    root = root.resolve()
    if names is None:
        names = public_names(root, include_private=profile != "source")
        if profile == "source":
            try:
                names = sorted(set(names) | set(tracked_names(root)))
            except ValueError as e:
                return [str(e)]
    else:
        names = list(map(Path, names))
    if len(names) > MAX_FILES:
        return ["Too many publication candidates"]
    problems = []
    seen = set()
    total = 0
    fingerprints = source_fingerprints(root)
    for name in names:
        path = root / name
        key = name.as_posix()
        folded = unicodedata.normalize("NFKC", key).casefold()
        unsafe = (
            name.is_absolute()
            or ".." in name.parts
            or not name.parts
            or any(
                ":" in part
                or "\\" in part
                or part.rstrip(" .") != part
                or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in part)
                for part in name.parts
            )
        )
        try:
            unsafe = (
                unsafe
                or not path.resolve().is_relative_to(root)
                or path.is_symlink()
                or any(p.is_symlink() for p in path.parents)
                or not path.is_file()
            )
        except (OSError, ValueError):
            unsafe = True
        if unsafe:
            problems.append(f"Unsafe, missing or non-file entry: {key}")
            continue
        if folded in seen:
            problems.append(f"Duplicate or case-colliding publication path: {key}")
            continue
        seen.add(folded)
        if any(
            part.casefold() in PRIVATE_DIRS or part == ".git" for part in name.parts
        ):
            problems.append(f"Private output must not be published: {key}")
            continue
        size = path.stat().st_size
        total += size
        if size > MAX_TRACKED_FILE:
            problems.append(f"Oversized file: {key}")
            continue
        if total > MAX_TOTAL_BYTES:
            problems.append("Publication tree exceeds size limit")
            break
        if screenshot_key(name, profile) in REVIEWED_SCREENSHOTS:
            if not reviewed_screenshot(root, name, profile):
                problems.append(f"Reviewed editor screenshot changed: {key}")
            continue
        if profile == "site" and key in {".nojekyll", ".gintama-site-build"}:
            expected = (
                b"" if key == ".nojekyll" else b"Static translation editor build\n"
            )
            if path.read_bytes() not in {expected, expected.replace(b"\n", b"\r\n")}:
                problems.append(f"Invalid site marker: {key}")
            continue
        if any(
            suffix.lower() in BANNED
            for suffix in Path(unicodedata.normalize("NFKC", key)).suffixes
        ) or (name.suffix.lower() not in ALLOWED and name.name not in SPECIAL):
            problems.append(
                f"Asset, archive or unreviewed file type must not be published: {key}"
            )
            continue
        raw = path.read_bytes()
        if (
            raw.startswith(MAGIC)
            or zipfile.is_zipfile(path)
            or hashlib.sha256(raw).hexdigest() in fingerprints
        ):
            problems.append(
                f"Binary/archive or known original payload disguised as text: {key}"
            )
            continue
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError:
            problems.append(f"Non-UTF-8 payload: {key}")
            continue
        if "\0" in text:
            problems.append(f"Binary/NUL payload in text file: {key}")
            continue
        if any(
            unicodedata.category(c) == "Cf" or (ord(c) < 32 and c not in "\t\n\r\f")
            for c in text
        ):
            problems.append(f"Hidden/control characters in public text: {key}")
            continue
        values = []
        if name.suffix.lower() == ".json":
            try:
                data = strict_json(text)
                if source_payload(data):
                    problems.append(f"Copied source/binary payload fields: {key}")
                values = list(strings(data))
            except (ValueError, RecursionError):
                problems.append(f"Invalid, duplicate-key or non-finite JSON: {key}")
                continue
        elif name.suffix.lower() == ".csv":
            try:
                rows = list(csv.reader(io.StringIO(text), strict=True))
                if rows and any(normalize_key(k) in SOURCE_FIELDS for k in rows[0]):
                    problems.append(f"Source payload CSV column: {key}")
                values = [cell for row in rows for cell in row]
            except csv.Error:
                problems.append(f"Invalid CSV: {key}")
                continue
        if any(private_contact(value) for value in [text, *values]):
            problems.append(f"Possible personal contact or home-directory path: {key}")
        if SECRET.search(text) or any(SECRET.search(value) for value in values):
            problems.append(f"Possible credential/private-key material: {key}")
        if any(
            any(
                unicodedata.category(c) in {"Cf", "Cs"}
                or (ord(c) < 32 and c not in "\t\n\r\f")
                for c in value
            )
            for value in values
        ):
            problems.append(f"Hidden/control characters in decoded data: {key}")
        if any(JAPANESE_PROSE.search(value) for value in [text, *values]):
            problems.append(f"Possible copied Japanese source prose: {key}")
        if any(
            binary_payload(blob, fingerprints)
            for value in [text, *values]
            for blob in encoded_blocks(value)
        ):
            problems.append(f"Encoded binary/archive or source payload: {key}")
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Audit publication candidates for game payloads and unsafe file types; not legal clearance"
    )
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--profile", choices=["source", "site", "export"], default="source"
    )
    a = parser.parse_args()
    issues = check(a.repo, profile=a.profile)
    if issues:
        parser.exit(1, "\n".join(issues) + "\n")
    print(
        "Publication audit passed: approved file types and exact reviewed images; no detected source payloads. This is a technical filter, not legal clearance."
    )
