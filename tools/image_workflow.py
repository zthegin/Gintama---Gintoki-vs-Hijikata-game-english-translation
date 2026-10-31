#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from functools import lru_cache
from pathlib import Path

from optimal_lz10 import compress

ROOT = Path(__file__).resolve().parents[1]
MAX_ROM = 512 * 1024 * 1024


def require(test, message):
    if not test:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    require(path.stat().st_size <= 2_000_000, "Oversized graphics metadata")
    return json.loads(path.read_text(encoding="utf-8"))


def lz10(data, start=0, vram=False):
    require(0 <= start < len(data) - 4 and data[start] == 0x10, "Missing LZ10 header")
    size = int.from_bytes(data[start + 1 : start + 4], "little")
    require(0 < size <= 1024 * 1024, "Invalid decoded image length")
    out = bytearray(size)
    used = 0
    pos = start + 4
    committed = 0
    while used < size:
        require(pos < len(data), "Truncated LZ flags")
        flags = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if used >= size:
                break
            if flags & (1 << bit):
                require(pos + 2 <= len(data), "Truncated LZ match")
                token = data[pos] << 8 | data[pos + 1]
                pos += 2
                length, distance = (token >> 12) + 3, (token & 4095) + 1
                require(
                    distance <= used and (not vram or distance >= 2),
                    "Invalid or unsafe VRAM match",
                )
            else:
                length, distance = 1, None
            for _ in range(length):
                if used >= size:
                    break
                if distance is None:
                    require(pos < len(data), "Truncated LZ literal")
                    value = data[pos]
                    pos += 1
                else:
                    require(
                        not vram or used - distance < committed,
                        "VRAM reads an uncommitted byte",
                    )
                    value = out[used - distance]
                out[used] = value
                used += 1
                if used % 2 == 0:
                    committed = used
    return bytes(out), pos


def unpack_obj(data):
    require(len(data) == 512, "Expected a 64x16 4bpp label")
    pixels = [0] * 1024
    pos = 0
    for cell_x in (0, 32):
        for ty in range(2):
            for tx in range(4):
                for y in range(8):
                    for x in range(0, 8, 2):
                        byte = data[pos]
                        pos += 1
                        at = (ty * 8 + y) * 64 + cell_x + tx * 8 + x
                        pixels[at], pixels[at + 1] = byte & 15, byte >> 4
    return pixels


def pack_obj(pixels):
    require(
        len(pixels) == 1024 and all(type(v) is int and 0 <= v < 16 for v in pixels),
        "Invalid pixels",
    )
    data = bytearray()
    for cell_x in (0, 32):
        for ty in range(2):
            for tx in range(4):
                for y in range(8):
                    for x in range(0, 8, 2):
                        at = (ty * 8 + y) * 64 + cell_x + tx * 8 + x
                        data.append(pixels[at] | pixels[at + 1] << 4)
    return bytes(data)


def font_rows(root=ROOT):
    rows = read_json(root / "graphics/pixel_font.json")["rows"]
    require(
        all(
            len(v) == 7
            and len({len(r) for r in v}) == 1
            and 1 <= len(v[0]) <= 8
            and all(set(r) <= {".", "#"} for r in v)
            for v in rows.values()
        ),
        "Invalid project pixel alphabet",
    )
    return rows


def render_label(text, rows, background="original_transparent", dx=0, dy=0):
    require(
        isinstance(text, str) and text.strip() and len(text) <= 80,
        "Expected a short English label",
    )
    require(
        background in {"original_transparent", "native_dark_backplate"},
        "Unknown label background",
    )
    lines = text.upper().split("\n")
    require(1 <= len(lines) <= 2, "Names allow at most two lines")
    ink = set()
    for line_no, line in enumerate(lines):
        require(
            line and all(c in rows for c in line), "Unsupported or empty label line"
        )
        width = sum(len(rows[c][0]) + 1 for c in line) - 1
        x = (64 - width) // 2 + dx
        y = (4 if len(lines) == 1 else line_no * 9) + dy
        require(
            width <= 62 and x >= 1 and x + width <= 63 and 0 <= y and y + 7 <= 16,
            "Label exceeds its 64x16 surface; use a shorter display name",
        )
        for char in line:
            for yy, row in enumerate(rows[char]):
                for xx, value in enumerate(row):
                    if value == "#":
                        ink.add((x + xx, y + yy))
            x += len(rows[char][0]) + 1
    pixels = [11 if background == "native_dark_backplate" else 0] * 1024
    for x, y in ink:
        for yy in range(max(0, y - 1), min(16, y + 2)):
            for xx in range(max(0, x - 1), min(64, x + 2)):
                pixels[yy * 64 + xx] = 11
    for x, y in ink:
        pixels[y * 64 + x] = 15
    return pixels


def encode_label(text, entry, rows):
    signature = tuple(sorted((key, tuple(value)) for key, value in rows.items()))
    try:
        return _encode_label(
            text, entry["background"], entry["compressed_capacity"], signature
        )
    except ValueError as error:
        raise ValueError(f"{entry['id']}: {error}") from error


@lru_cache(maxsize=4096)
def _encode_label(text, background, capacity, signature):
    rows = dict(signature)
    require(
        type(capacity) is int and 1 <= capacity <= 4096, "Invalid compressed capacity"
    )
    centered = render_label(text, rows, background)
    width = max(
        sum(len(rows[char][0]) + 1 for char in line) - 1
        for line in text.upper().split("\n")
    )
    left = (64 - width) // 2
    candidates = [(0, 0)] + [
        (x, y)
        for x in (0, -1, 1, -2, 2)
        for y in ((0,) if "\n" in text else (0, -1, 1, -2, 2))
        if (x, y) != (0, 0) and 1 <= left + x and left + x + width <= 63
    ]
    best = None
    for dx, dy in candidates:
        pixels = (
            centered
            if (dx, dy) == (0, 0)
            else render_label(text, rows, background, dx, dy)
        )
        raw = pack_obj(pixels)
        packed = compress(raw)
        if best is None or len(packed) < len(best[1]):
            best = raw, packed, (dx, dy)
        if len(packed) <= capacity:
            break
    raw, packed, shift = best
    require(
        len(packed) <= capacity,
        f"needs {len(packed)} compressed bytes, slot holds {capacity}; shorten the label",
    )
    require(
        lz10(packed)[0] == raw and lz10(packed, vram=True)[0] == raw,
        "LZ/VRAM roundtrip failed",
    )
    require(pack_obj(unpack_obj(raw)) == raw, "OBJ pixel roundtrip failed")
    return raw, packed, shift


def validate_graphic_translations(root, batch=None):
    catalog = read_json(root / "graphics/catalog.json")
    rows = font_rows(root)
    batch = batch or read_json(root / "translations" / catalog["translation_batch"])
    entries = catalog["entries"]
    require(len(entries) == len(batch["records"]), "Graphic record count changed")
    for entry, translation in zip(entries, batch["records"]):
        require(
            entry["id"] == translation["id"]
            and entry["source_words_sha256"] == translation["source_words_sha256"],
            "Graphic ID/hash/order changed",
        )
        require(
            (
                entry["width"],
                entry["height"],
                entry["cell_width"],
                entry["cell_height"],
                entry["decoded_bytes"],
            )
            == (64, 16, 32, 16, 512),
            "Unsupported source geometry",
        )
        if translation["english"] is not None:
            encode_label(translation["english"], entry, rows)
    return catalog, batch, rows


def nds_files(data):
    require(len(data) >= 0x50, "Truncated NDS header")
    fnt, fnt_size, fat, fat_size = struct.unpack_from("<4I", data, 0x40)
    require(
        fnt_size >= 8
        and fat_size >= 8
        and fat_size % 8 == 0
        and fnt + fnt_size <= len(data)
        and fat + fat_size <= len(data),
        "Invalid NitroFS tables",
    )
    count = struct.unpack_from("<H", data, fnt + 6)[0]
    require(0 < count <= 4096 and count * 8 <= fnt_size, "Invalid directory count")
    result = {}
    visited = set()

    def walk(ident, prefix, depth=0):
        require(
            0 <= ident - 0xF000 < count and ident not in visited and depth < 64,
            "Invalid/repeated NitroFS directory",
        )
        visited.add(ident)
        at = fnt + (ident - 0xF000) * 8
        offset, file_id = struct.unpack_from("<IH", data, at)
        pos = fnt + offset
        require(fnt + count * 8 <= pos < fnt + fnt_size, "Invalid NitroFS name offset")
        while pos < fnt + fnt_size:
            size = data[pos]
            pos += 1
            if not size:
                return
            length = size & 127
            require(length and pos + length <= fnt + fnt_size, "Invalid NitroFS name")
            name = data[pos : pos + length].decode("ascii")
            pos += length
            require(
                "/" not in name and "\\" not in name and name not in {".", ".."},
                "Invalid NitroFS path",
            )
            if size & 128:
                require(pos + 2 <= fnt + fnt_size, "Truncated child directory")
                child = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                walk(child, prefix + name + "/", depth + 1)
            else:
                require((file_id + 1) * 8 <= fat_size, "Invalid file ID")
                left, right = struct.unpack_from("<II", data, fat + file_id * 8)
                file_id += 1
                require(
                    left <= right <= len(data)
                    and (prefix + name).lower() not in result,
                    "Invalid/duplicate file span",
                )
                result[(prefix + name).lower()] = left, right
        raise ValueError("Unterminated NitroFS directory")

    walk(0xF000, "")
    return result


def read_rom(path):
    require(
        path.exists(),
        f"ROM file not found: {path}. Check the path and keep quotes around it.",
    )
    require(
        path.is_file(),
        f"ROM path is not a file: {path}. Choose the extracted .nds file.",
    )
    require(
        path.suffix.lower() not in {".zip", ".7z", ".rar", ".gz"},
        "Extract the archive first, then use the path to its .nds file",
    )
    size = path.stat().st_size
    require(size > 0, f"ROM file is empty: {path}")
    require(size <= MAX_ROM, "ROM file exceeds the supported 512 MiB size limit")
    return path.read_bytes()


def prepare(source, catalog, batch, rows, base=None):
    require(
        sha(source) == catalog["source_rom_sha256"],
        "Original ROM SHA-256 does not match the supported version",
    )
    files = nds_files(source)
    left, right = files[catalog["source_container"]]
    original = source[left:right]
    require(
        sha(original) == catalog["source_container_sha256"],
        "Source image container hash mismatch",
    )
    base = source if base is None else base
    target_files = nds_files(base)
    target_left, target_right = target_files[catalog["source_container"]]
    require(
        base[0x0C:0x10] == source[0x0C:0x10]
        and target_right - target_left == len(original),
        "Base ROM is incompatible",
    )
    modified = bytearray(base[target_left:target_right])
    spans = []
    previews = []
    records = []
    palette, _ = lz10(original, catalog["palette_offset"])
    require(len(palette) == 32, "Invalid shared palette")
    colors = [
        tuple(((v >> shift) & 31) * 255 // 31 for shift in (0, 5, 10))
        for (v,) in struct.iter_unpack("<H", palette)
    ]
    for entry, translation in zip(catalog["entries"], batch["records"]):
        at, capacity = entry["offset"], entry["compressed_capacity"]
        require(
            type(at) is int and 0 <= at and at + capacity <= len(original),
            "Graphic offset outside container",
        )
        raw, end = lz10(original, at)
        require(
            end - at == capacity
            and sha(raw) == entry["source_words_sha256"]
            and len(raw) == 512,
            "Source image fingerprint mismatch",
        )
        spans.append((at, at + capacity))
        if translation["english"] is None:
            continue
        new, packed, shift = encode_label(translation["english"], entry, rows)
        modified[at : at + capacity] = packed + bytes(capacity - len(packed))
        previews.append((entry, raw, new))
        records.append(
            {
                "id": entry["id"],
                "compressed_bytes": len(packed),
                "capacity": capacity,
                "shift": shift,
                "decoded_sha256": sha(new),
            }
        )
    cursor = 0
    old_base = base[target_left:target_right]
    for start, end in sorted(spans):
        require(
            start >= cursor
            and original[cursor:start]
            == old_base[cursor:start]
            == modified[cursor:start],
            "Base or output changed protected artwork/palettes",
        )
        cursor = end
    require(
        original[cursor:] == old_base[cursor:] == modified[cursor:],
        "Container tail changed",
    )
    result = bytearray(base)
    result[target_left:target_right] = modified
    require(
        result[:target_left] == base[:target_left]
        and result[target_right:] == base[target_right:]
        and len(result) == len(base),
        "ROM bytes outside the image container changed",
    )
    return (
        bytes(result),
        previews,
        colors,
        {
            "images": len(records),
            "source_rom_sha256": sha(source),
            "base_rom_sha256": sha(base),
            "output_rom_sha256": sha(result),
            "all_other_base_rom_bytes_identical": True,
            "palettes_and_primary_pictures_unchanged": True,
            "byte_and_vram_roundtrips": True,
            "runtime_verified": False,
            "records": records,
        },
    )


def private_output(path):
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT):
        require(
            resolved.relative_to(ROOT).parts[0] in {"local", "private"},
            "Generated game material must be under ignored local/ or private/, or outside the repository",
        )
    require(
        not path.is_symlink() and not any(p.is_symlink() for p in path.parents),
        "Symlink output refused",
    )
    return resolved


def build_destinations(out, inputs):
    out = private_output(out)
    report = private_output(out.with_suffix(".report.private.json"))
    inputs = {p.resolve() for p in inputs}
    require(out.suffix.lower() == ".nds", "Build output must be a separate .nds file")
    require(
        out not in inputs and report not in inputs,
        "Refusing to overwrite an input ROM or its path with a report",
    )
    require(
        not out.exists() and not report.exists(),
        "Build output or report already exists; choose new paths",
    )
    return out, report


def png(pixels, colors, scale=4):
    width, height = 64 * scale, 16 * scale
    raw = b"".join(
        b"\0"
        + b"".join(
            bytes(colors[pixels[(y // scale) * 64 + x // scale]]) for x in range(width)
        )
        for y in range(height)
    )

    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def write_outputs(payloads):
    created = []
    try:
        for path, payload in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                created.append(path)
                stream.write(payload)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Inspect and rebuild supported image labels using a locally supplied, legally obtained original ROM"
    )
    parser.add_argument("command", choices=["inspect", "build"])
    parser.add_argument(
        "--rom",
        type=Path,
        required=True,
        help="Your legally obtained, matching unmodified ROM (read only)",
    )
    parser.add_argument(
        "--base-rom",
        type=Path,
        help="Optional compatible translated copy of your legally obtained ROM",
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--translations", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    a = parser.parse_args()
    try:
        catalog, batch, rows = validate_graphic_translations(
            ROOT, read_json(a.translations) if a.translations else None
        )
        source = read_rom(a.rom)
        base = read_rom(a.base_rom) if a.base_rom else None
        result, previews, colors, report = prepare(source, catalog, batch, rows, base)
        if a.validate_only:
            print(
                json.dumps(
                    {k: v for k, v in report.items() if k != "records"}, indent=2
                )
            )
            return 0
        require(a.out is not None, "--out is required unless --validate-only is used")
        out = private_output(a.out)
        require(
            out
            not in {
                a.rom.resolve(),
                a.base_rom.resolve() if a.base_rom else a.rom.resolve(),
            },
            "Refusing to overwrite an input ROM",
        )
        require(not out.exists(), "Output already exists; choose a new path")
        if a.command == "build":
            out, report_path = build_destinations(
                out, [a.rom] + ([a.base_rom] if a.base_rom else [])
            )
            write_outputs(
                {
                    out: result,
                    report_path: (json.dumps(report, indent=2) + "\n").encode("utf-8"),
                }
            )
        else:
            out.mkdir(parents=True)
            for entry, raw, new in previews:
                for kind, data in [("source", raw), ("english", new)]:
                    (out / (entry["id"] + "_" + kind + ".png")).write_bytes(
                        png(unpack_obj(data), colors)
                    )
            (out / "report.private.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
        require(
            sha(read_rom(a.rom)) == report["source_rom_sha256"], "Source ROM changed"
        )
        print(
            json.dumps(
                {
                    "images": report["images"],
                    "output": str(out),
                    "sha256": report["output_rom_sha256"],
                    "runtime_verified": False,
                }
            )
        )
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(1, str(error) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
