# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import struct
from pathlib import Path

from dialogue_writer import END, LINE, advance, read_json, words_at
from english_font import encode_text
from image_workflow import require, sha
from text_policy import check_safe_text

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = {0xFFA1, 0xFFA2, 0xFFA3, 0xFFA5, 0xFF81, 0xFF84, 0xFFB1, 0xFFB2}


def text_runs(words):
    runs, start = [], None
    for i, word in enumerate(words):
        if 1 <= word <= 6953 or word == LINE:
            if start is None:
                start = i
        else:
            require(word in CONTROLS or word == END, "Unsupported cutscene control")
            if start is not None:
                runs.append((start, i))
                start = None
    require(start is None and words[-1] == END, "Unterminated cutscene message")
    return runs


def load_scene(path=None):
    scene = read_json(Path(path) if path else ROOT / "reference/opening_scene.json")
    require(
        isinstance(scene, dict)
        and set(scene)
        == {
            "format",
            "script",
            "scope",
            "source_msb_sha256",
            "source_cdb_sha256",
            "notes",
            "messages",
        },
        "Invalid cutscene metadata",
    )
    require(scene["format"] == "gintama-cutscene-v1", "Unsupported cutscene format")
    require(
        isinstance(scene["messages"], list) and 0 < len(scene["messages"]) <= 2000,
        "Invalid cutscene message list",
    )
    for key in ("source_msb_sha256", "source_cdb_sha256"):
        value = scene[key]
        require(
            isinstance(value, str)
            and len(value) == 64
            and set(value) <= set("0123456789abcdef"),
            "Invalid cutscene source hash",
        )
    require(
        scene["script"] == "adventure/script/s01.msb", "Unsupported cutscene script"
    )
    seen = set()
    for row in scene["messages"]:
        require(
            isinstance(row, dict)
            and set(row) == {"offset", "source_words_sha256", "parts"},
            "Invalid cutscene entry",
        )
        offset = row["offset"]
        require(
            type(offset) is int
            and offset >= 16
            and offset % 2 == 0
            and offset not in seen,
            "Invalid cutscene offset",
        )
        seen.add(offset)
        require(
            isinstance(row["parts"], list) and 0 < len(row["parts"]) <= 64,
            "Missing English cutscene parts",
        )
        require(
            any(isinstance(part, str) and part.strip() for part in row["parts"]),
            "Empty cutscene message",
        )
        require(
            sum(len(part) for part in row["parts"] if isinstance(part, str)) <= 2500,
            "Oversized cutscene message",
        )
        for part in row["parts"]:
            require(isinstance(part, str), "Cutscene English must be text")
            if part:
                check_safe_text(part, "cutscene", 2500)
            require(
                "\f" not in part and "\r" not in part,
                "Unsupported cutscene page control",
            )
        check_safe_text("".join(row["parts"]), "cutscene", 2500)
    return scene


def wrap_parts(parts, fonts, latin, width=176):
    chars = [(i, ch) for i, part in enumerate(parts) for ch in part]
    x, line, last_space, line_start = 0, 0, None, 0
    for at, (owner, ch) in enumerate(chars):
        if ch == "\n":
            x, line, last_space, line_start = 0, line + 1, None, at + 1
            continue
        code = encode_text(ch, latin)[0]
        x += max(advance(code, font, stride) for font, stride in fonts)
        if ch == " ":
            last_space = at
        if x > width:
            require(
                last_space is not None and last_space >= line_start,
                "Cutscene word exceeds its bubble",
            )
            chars[last_space] = (chars[last_space][0], "\n")
            line += 1
            line_start = last_space + 1
            x = sum(
                max(advance(encode_text(c, latin)[0], f, s) for f, s in fonts)
                for _, c in chars[line_start : at + 1]
            )
            require(x <= width, "Cutscene word exceeds its bubble")
            last_space = None
    require(line < 3, "Cutscene message exceeds three lines")
    result = [""] * len(parts)
    for owner, ch in chars:
        result[owner] += ch
    return result


def record_pixels(font, stride, code):
    at = (code - 1) * stride
    require(0 <= at and at + stride <= len(font), "Missing cluster source glyph")
    rows = []
    for left in range(at + 4, at + stride, 4):
        b = font[left : left + 4]
        row = []
        for v in (b[1], b[0], b[3], b[2]):
            row.extend((v >> shift) & 3 for shift in (6, 4, 2, 0))
        rows.append(row)
    return rows


def cluster_record(text, font, stride, latin):
    return cluster_codes(encode_text(text, latin), font, stride)


def cluster_codes(codes, font, stride):
    height = (stride - 4) // 4
    canvas = [[0] * 16 for _ in range(height)]
    x = 0
    for code in codes:
        width = advance(code, font, stride)
        pixels = record_pixels(font, stride, code)
        require(x + width <= 16, "English cluster exceeds font width")
        require(
            not any(any(row[width:]) for row in pixels),
            "Source glyph overhang requires separate handling",
        )
        for y, row in enumerate(pixels):
            canvas[y][x : x + width] = row[:width]
        x += width
    payload = bytearray(struct.pack("<I", x - 1))
    for row in canvas:
        b = [sum(row[i + j] << (6 - j * 2) for j in range(4)) for i in range(0, 16, 4)]
        payload.extend((b[1], b[0], b[3], b[2]))
    return bytes(payload)



class DialogueClusters:
    """Use the existing cutscene packing for field text that exceeds its slot."""
    def __init__(self, fonts):
        self.fonts = [(bytearray(font), stride) for font, stride in fonts]
        self.first_code = len(fonts[0][0]) // fonts[0][1] + 1
        self.codes = {}

    def pack(self, codes, budget):
        tokens, at = [], 0
        while at < len(codes):
            if codes[at] >= 0xFF00:
                tokens.append((codes[at],))
                at += 1
                continue
            end = at + 1
            widths = [advance(codes[at], font, stride) for font, stride in self.fonts]
            require(max(widths) <= 16, "Dialogue character exceeds font width")
            while end < len(codes) and codes[end] < 0xFF00:
                next_widths = [width + advance(codes[end], font, stride)
                               for width, (font, stride) in zip(widths, self.fonts)]
                if max(next_widths) > 16:
                    break
                widths, end = next_widths, end + 1
            tokens.append(tuple(codes[at:end]))
            at = end
        require(len(tokens) <= budget, "English dialogue exceeds its fixed message slot")
        while len(tokens) < budget:
            at = next((i for i, token in enumerate(tokens) if len(token) > 1), None)
            if at is None:
                break
            token = tokens[at]
            tokens[at:at + 1] = [token[:1], token[1:]]
        result = []
        for token in tokens:
            if len(token) == 1:
                code = token[0]
            else:
                if token not in self.codes:
                    code = self.first_code + len(self.codes)
                    require(code < 0xFF00, "English cluster bank exhausted")
                    self.codes[token] = code
                    for font, stride in self.fonts:
                        font.extend(cluster_codes(token, font, stride))
                code = self.codes[token]
            result.append(code)
        return result


def prepare(field, cdb, scene, fonts, latin, *, minimum_offset=16):
    require(
        sha(field) == scene["source_msb_sha256"]
        and sha(cdb) == scene["source_cdb_sha256"],
        "Original cutscene files changed",
    )
    require(
        len(fonts) == 2
        and len(fonts[0][0]) // fonts[0][1] == len(fonts[1][0]) // fonts[1][1],
        "Font banks disagree",
    )
    extended = [bytearray(font) for font, _ in fonts]
    first_code = len(fonts[0][0]) // fonts[0][1] + 1
    clusters, messages, spans = {}, [], []
    target = bytearray(field)

    def size(text):
        codes = encode_text(text, latin)
        return max(sum(advance(c, f, s) for c in codes) for f, s in fonts)

    def code_for(text):
        if text == "\n":
            return LINE
        if len(text) == 1:
            return encode_text(text, latin)[0]
        if text not in clusters:
            code = first_code + len(clusters)
            require(code < 0xFF00, "English cluster bank exhausted")
            clusters[text] = code
            for i, (font, stride) in enumerate(fonts):
                extended[i].extend(cluster_record(text, font, stride, latin))
        return clusters[text]

    for row in scene["messages"]:
        offset = row["offset"]
        original = words_at(field, offset, minimum_offset=minimum_offset)
        raw = struct.pack("<" + "H" * len(original), *original)
        require(sha(raw) == row["source_words_sha256"], "Cutscene source span changed")
        runs = text_runs(original)
        require(len(runs) == len(row["parts"]), "Cutscene English part count changed")
        parts = wrap_parts(row["parts"], fonts, latin)
        tokens, cursor = [], 0
        for (left, right), part in zip(runs, parts):
            tokens.extend(original[cursor:left])
            at = 0
            while at < len(part):
                if part[at] == "\n":
                    tokens.append("\n")
                    at += 1
                    continue
                end = at + 1
                require(size(part[at:end]) <= 16, "Character exceeds font width")
                while (
                    end < len(part)
                    and part[end] != "\n"
                    and size(part[at : end + 1]) <= 16
                ):
                    end += 1
                tokens.append(part[at:end])
                at = end
            cursor = right
        tokens.extend(original[cursor:-1])
        budget = len(original) - 1
        require(
            len(tokens) <= budget,
            "English cutscene exceeds its fixed message slot: " + hex(offset),
        )
        while len(tokens) < budget:
            found = next(
                (i for i, v in enumerate(tokens) if isinstance(v, str) and len(v) > 1),
                None,
            )
            if found is None:
                break
            value = tokens[found]
            tokens[found : found + 1] = [value[0], value[1:]]
        encoded = [code_for(v) if isinstance(v, str) else v for v in tokens]
        padding = budget - len(encoded)
        encoded += [1] * padding + [END]
        for font, (_, stride) in zip(extended, fonts):
            x = line = 0
            for word in encoded:
                if word == END:
                    break
                if word == LINE:
                    x, line = 0, line + 1
                    require(line < 3, "Cutscene exceeds three lines")
                elif word not in CONTROLS:
                    x += advance(word, font, stride)
                    require(x <= 176, "Cutscene text or padding exceeds its bubble")
        require(
            [v for v in encoded if v in CONTROLS]
            == [v for v in original if v in CONTROLS],
            "Cutscene controls changed",
        )
        payload = struct.pack("<" + "H" * len(encoded), *encoded)
        end = offset + len(payload)
        require(payload[-2:] == field[end - 2 : end] == b"q\xff", "Cutscene END moved")
        target[offset:end] = payload
        spans.append((offset, end))
        messages.append(
            {
                "offset": offset,
                "end_offset": end,
                "english": "".join(parts),
                "parts": parts,
                "padding_words": padding,
                "encoded_words": encoded,
            }
        )
    cursor = 0
    for left, right in sorted(spans):
        require(
            left >= cursor and target[cursor:left] == field[cursor:left],
            "Overlapping or unexpected cutscene edit",
        )
        cursor = right
    require(
        target[cursor:] == field[cursor:] and len(target) == len(field),
        "Cutscene size or tail changed",
    )
    return (
        bytes(target),
        [(bytes(v), fonts[i][1]) for i, v in enumerate(extended)],
        spans,
        {
            "messages": messages,
            "extra_font_records": len(clusters),
            "clusters": clusters,
        },
    )


def prepare_labels(scripts, labels, fonts, latin, occupied):
    """Pack fixed labels without touching their null terminators or colour controls."""
    packer = DialogueClusters(fonts)
    used = {path: list(spans) for path, spans in occupied.items()}
    patches = []
    for row in labels:
        path, offset, capacity = row["script"], row["offset"], row["word_capacity"]
        require(path in scripts, "Unsupported label script")
        data = scripts[path]
        require(type(offset) is int and offset >= 16 and offset % 2 == 0
                and type(capacity) is int and 0 < capacity <= 256,
                "Invalid label span")
        end = offset + capacity * 2
        require(end + 2 <= len(data), "Label is outside its script")
        original = data[offset:end]
        require(sha(original) == row["source_sha256"], "Label source hash changed")
        words = struct.unpack("<" + "H" * capacity, original)
        require(all(1 <= code <= 6953 for code in words)
                and struct.unpack_from("<H", data, end)[0] in {0, 0xFF81, 0xFF84, LINE, 0xFF72, END},
                "Label span contains controls or lacks a boundary")
        require(all(end <= left or offset >= right for left, right in used.get(path, [])),
                "Label overlaps another translation")
        text = row["english"]
        check_safe_text(text, row["id"])
        require(bool(text.strip()) and "\n" not in text and "\f" not in text,
                "Labels must use one line")
        codes = encode_text(text, latin)
        require(all(sum(advance(code, font, stride) for code in codes) <= 176
                    for font, stride in fonts), "Label exceeds its text box")
        if len(codes) > capacity:
            codes = packer.pack(codes, capacity)
        require(len(codes) <= capacity, "English label exceeds its fixed slot")
        codes += [1] * (capacity - len(codes))
        require(all(sum(advance(code, font, stride) for code in codes) <= 176
                    for font, stride in packer.fonts),
                "Label padding exceeds its text box")
        payload = struct.pack("<" + "H" * capacity, *codes)
        patches.append((path, offset, end, payload))
        used.setdefault(path, []).append((offset, end))
    return patches, [(bytes(font), stride) for font, stride in packer.fonts]
