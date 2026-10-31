# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import struct
from pathlib import Path

from english_font import encode_text
from field_markup import COLOR_CONTROLS, COLOR_MARKER, color_tokens, strip_colors
from image_workflow import require, sha
from text_policy import check_safe_text, strict_json

ROOT = Path(__file__).resolve().parents[1]
LINE, END, PAGE = 0xFF70, 0xFF71, 0xFF72
FIELD_CONTROLS = frozenset({LINE, END, PAGE}) | COLOR_CONTROLS
FIELD = "field/script/fld_scr.msb"
CDB = "field/script/fld_scr.cdb"


def read_json(path):
    require(path.stat().st_size <= 20_000_000, "Oversized dialogue metadata")
    return strict_json(path.read_text(encoding="utf-8"))


def load_records(root=ROOT, batch=None):
    if batch is not None:
        paths = [Path(batch)]
    else:
        paths = sorted((root / "translations/ready").glob("*.json"))
        if not paths and (root / "approved_translations.json").is_file():
            paths = [root / "approved_translations.json"]
    result, seen = [], set()
    for path in paths:
        payload = read_json(path)
        if payload.get("format") == "gintama-approved-translation-export-v2":
            rows = payload["translations"]
        else:
            require(
                payload.get("format") == "gintama-community-translation-v1",
                "Unsupported dialogue batch",
            )
            rows = payload["records"]
        require(isinstance(rows, list), "Invalid dialogue records")
        for row in rows:
            require(
                isinstance(row, dict)
                and set(row)
                == {"id", "source_words_sha256", "english", "translator_note"},
                "Invalid dialogue entry",
            )
            require(
                isinstance(row["id"], str) and row["id"] not in seen,
                "Duplicate dialogue ID",
            )
            seen.add(row["id"])
            check_safe_text(row["english"], row["id"])
            check_safe_text(row["translator_note"], row["id"] + ".note", 500)
            if row["english"] is not None:
                require(bool(row["english"].strip()), "Empty dialogue: " + row["id"])
                result.append(row)
    return result


def words_at(field, offset, *, minimum_offset=16):
    require(
        type(offset) is int and minimum_offset <= offset < len(field) and offset % 2 == 0,
        "Invalid dialogue offset",
    )
    words = []
    for at in range(offset, len(field) - 1, 2):
        word = struct.unpack_from("<H", field, at)[0]
        words.append(word)
        if word == END:
            require(field[at + 2 : at + 4] == b"\0\0", "Missing dialogue separator")
            return words
    raise ValueError("Unterminated dialogue")


def advance(code, font, stride):
    at = (code - 1) * stride
    require(0 <= at and at + stride <= len(font), "Dialogue refers to a missing glyph")
    return struct.unpack_from("<I", font, at)[0] + 1


def layout(text, fonts, latin, width=176):
    strip_colors(text)  # Validate the complete spans before wrapping fragments.

    def size(line):
        codes = encode_text(COLOR_MARKER.sub("", line), latin)
        return max(
            sum(advance(code, font, stride) for code in codes) for font, stride in fonts
        )

    pages = []
    for page in text.split("\f"):
        require(bool(COLOR_MARKER.sub("", page).strip()), "Empty dialogue page")
        lines = []
        for paragraph in page.split("\n"):
            line = ""
            for word in paragraph.split():
                require(size(word) <= width, "A dialogue word exceeds the text box")
                candidate = (line + " " + word).strip()
                if size(candidate) > width:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            lines.append(line)
        require(len(lines) <= 3, "Dialogue exceeds three lines on a page")
        pages.append("\n".join(lines))
    laid_out = "\f".join(pages)
    codes = []
    for token in color_tokens(laid_out):
        if isinstance(token, int):
            codes.append(token)
            continue
        for i, page in enumerate(token.split("\f")):
            if i:
                codes.append(PAGE)
            codes.extend(encode_text(page, latin))
    return laid_out, codes


def check_layout(words, fonts, width=176):
    for font, stride in fonts:
        x, line = 0, 0
        for word in words:
            if word == END:
                break
            if word == PAGE:
                x, line = 0, 0
            elif word == LINE:
                x, line = 0, line + 1
                require(line < 3, "Dialogue exceeds three lines")
            elif word in COLOR_CONTROLS:
                continue
            else:
                x += advance(word, font, stride)
                require(
                    x <= width,
                    "Dialogue or its fixed-slot padding exceeds the text box",
                )


def patch(field, cdb, records, reference, fonts, latin, *, packer=None):
    require(
        sha(field) == reference["source_msb_sha256"], "Original dialogue hash mismatch"
    )
    require(sha(cdb) == reference["source_cdb_sha256"], "Original CDB hash mismatch")
    require(field[:4] == b"scr\x1a", "Unrecognized dialogue header")
    index = {row["id"]: row for row in reference["records"]}
    require(len(index) == len(reference["records"]), "Duplicate reference ID")
    target, spans, report, seen = bytearray(field), [], [], set()
    for row in records:
        entry_id = row["id"]
        require(
            entry_id not in seen and entry_id in index,
            "Unknown or duplicate dialogue ID",
        )
        seen.add(entry_id)
        source = index[entry_id]
        require(
            row["source_words_sha256"] == source["source_words_sha256"],
            "Dialogue source hash changed: " + entry_id,
        )
        offset = int(source["offset_hex"], 16)
        original = words_at(field, offset)
        raw = struct.pack("<" + "H" * len(original), *original)
        require(
            sha(raw) == source["source_words_sha256"],
            "Dialogue source span changed: " + entry_id,
        )
        require(
            all(1 <= word <= 6953 or word in FIELD_CONTROLS for word in original),
            "Complex dialogue controls need separate handling: " + entry_id,
        )
        check_safe_text(row["english"], entry_id)
        require(
            row["english"].count("\f") == original.count(PAGE),
            "Preserve dialogue page count: " + entry_id,
        )
        laid_out, codes = layout(row["english"], fonts, latin)
        require(
            [word for word in codes if word in COLOR_CONTROLS or word == PAGE]
            == [word for word in original if word in COLOR_CONTROLS or word == PAGE],
            "Preserve dialogue color controls and their page order: " + entry_id,
        )
        if len(codes) >= len(original) and packer is not None:
            codes = packer.pack(codes, len(original) - 1)
        padding = len(original) - len(codes) - 1
        require(
            padding >= 0,
            f"{entry_id}: English needs {len(codes) + 1} words; the fixed slot holds {len(original)}. Shorten the line; text is never truncated.",
        )
        encoded = codes + [1] * padding + [END]
        require(
            [word for word in encoded if word in COLOR_CONTROLS or word == PAGE]
            == [word for word in original if word in COLOR_CONTROLS or word == PAGE],
            "Packed dialogue color controls changed: " + entry_id,
        )
        check_layout(encoded, fonts)
        payload = struct.pack("<" + "H" * len(encoded), *encoded)
        end = offset + len(payload)
        require(payload[-2:] == field[end - 2 : end] == b"q\xff", "Dialogue END moved")
        target[offset:end] = payload
        spans.append((offset, end))
        report.append(
            {
                "id": entry_id,
                "offset": offset,
                "end_offset": end,
                "word_capacity": len(original),
                "padding_words": padding,
                "laid_out_english": laid_out,
                "pages": encoded.count(PAGE) + 1,
            }
        )
    cursor = 0
    for left, right in sorted(spans):
        require(
            left >= cursor and target[cursor:left] == field[cursor:left],
            "Overlapping or unauthorized dialogue edits",
        )
        cursor = right
    require(
        len(target) == len(field) and target[cursor:] == field[cursor:],
        "Dialogue size or suffix changed",
    )
    return bytes(target), spans, report
