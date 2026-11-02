# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import struct
from pathlib import Path

from english_font import encode_text
from field_markup import COLOR_CONTROLS, TEXT_CONTROLS, TEXT_MARKER, color_tokens, strip_colors
from image_workflow import require, sha
from text_policy import check_safe_text, strict_json

ROOT = Path(__file__).resolve().parents[1]
LINE, END, PAGE = 0xFF70, 0xFF71, 0xFF72
FIELD_CONTROLS = frozenset({LINE, END, PAGE}) | TEXT_CONTROLS
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


def record_terminator(indexed):
    require("raw_color_controls" not in indexed or type(indexed["raw_color_controls"]) is bool, "Invalid raw color controls flag")
    termination = indexed.get("termination", "end")
    require(isinstance(termination, str) and termination in {"end", "nul"}, "Invalid indexed termination")
    return 0 if termination == "nul" else END


def words_at(field, offset, *, minimum_offset=16, terminator=END):
    require(
        type(offset) is int and minimum_offset <= offset < len(field) and offset % 2 == 0,
        "Invalid dialogue offset",
    )
    require(type(terminator) is int and terminator in {END, 0}, "Invalid dialogue terminator")
    words = []
    for at in range(offset, len(field) - 1, 2):
        word = struct.unpack_from("<H", field, at)[0]
        require(terminator != 0 or word != END, "Unexpected END inside NUL record")
        words.append(word)
        if word == terminator:
            if terminator == END:
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
        codes = encode_text(TEXT_MARKER.sub("", line), latin)
        return max(
            sum(advance(code, font, stride) for code in codes) for font, stride in fonts
        )

    pages = []
    for page in text.split("\f"):
        require(bool(TEXT_MARKER.sub("", page).strip()), "Empty dialogue page")
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


def check_layout(words, fonts, width=176, *, terminator=END):
    for font, stride in fonts:
        x, line = 0, 0
        for word in words:
            if word == terminator:
                break
            if word == PAGE:
                x, line = 0, 0
            elif word == LINE:
                x, line = 0, line + 1
                require(line < 3, "Dialogue exceeds three lines")
            elif word in TEXT_CONTROLS:
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
        terminator = record_terminator(source)
        original = words_at(field, offset, terminator=terminator)
        suffix = source.get("trailing_controls", [])
        require(isinstance(suffix, list) and (not suffix or
                (terminator == 0 and suffix == [0xFF81] and type(suffix[0]) is int)),
                "Unsupported protected dialogue suffix")
        require(len(original) > len(suffix) + 1, "Empty dialogue source prefix")
        if suffix:
            require(original[-len(suffix)-1:-1] == suffix, "Protected dialogue suffix changed")
        editable_original = original[:-len(suffix)-1] if suffix else original[:-1]
        raw = struct.pack("<" + "H" * len(original), *original)
        require(
            sha(raw) == source["source_words_sha256"],
            "Dialogue source span changed: " + entry_id,
        )
        require(
            all(1 <= word <= 6953 or word in FIELD_CONTROLS for word in original[:-1]),
            "Complex dialogue controls need separate handling: " + entry_id,
        )
        check_safe_text(row["english"], entry_id)
        require(
            row["english"].count("\f") == editable_original.count(PAGE),
            "Preserve dialogue page count: " + entry_id,
        )
        laid_out, codes = layout(row["english"], fonts, latin)
        if terminator == 0:
            line_limits = [1]
            for word in editable_original:
                if word == PAGE:
                    line_limits.append(1)
                elif word == LINE:
                    line_limits[-1] += 1
            require(all(page.count("\n") + 1 <= limit
                        for page, limit in zip(laid_out.split("\f"), line_limits)),
                    "Menu text exceeds its original line count: " + entry_id)
        require(
            [word for word in codes if word in TEXT_CONTROLS or word == PAGE]
            == [word for word in editable_original if word in TEXT_CONTROLS or word == PAGE],
            "Preserve dialogue color controls and their page order: " + entry_id,
        )
        budget = len(editable_original)
        if len(codes) > budget and packer is not None:
            codes = packer.pack(codes, budget)
        padding = budget - len(codes)
        require(
            padding >= 0,
            f"{entry_id}: English needs {len(codes)} words; the fixed slot holds {budget}. Shorten the line; text is never truncated.",
        )
        # A trailing newline positions the value drawn after this menu prefix.
        if terminator == 0 and editable_original[-1] == LINE:
            require(codes and codes[-1] == LINE,
                    "Preserve the menu prefix's final newline: " + entry_id)
            encoded = codes[:-1] + [1] * padding + [LINE] + suffix + [terminator]
        else:
            encoded = codes + [1] * padding + suffix + [terminator]
        require(
            [word for word in encoded[:budget] if word in TEXT_CONTROLS or word == PAGE]
            == [word for word in editable_original if word in TEXT_CONTROLS or word == PAGE],
            "Packed dialogue color controls changed: " + entry_id,
        )
        check_layout(encoded, fonts, terminator=terminator)
        payload = struct.pack("<" + "H" * len(encoded), *encoded)
        end = offset + len(payload)
        require(payload[-2:] == field[end - 2 : end] == struct.pack("<H", terminator), "Dialogue END moved")
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
