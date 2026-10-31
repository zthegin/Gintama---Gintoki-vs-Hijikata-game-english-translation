# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import struct
from pathlib import Path

from image_workflow import read_json, require

CHARACTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ?. ,!"
GLYPH_CODES = {ch: 6954 + i for i, ch in enumerate(CHARACTERS)}
ROOT = Path(__file__).resolve().parents[1]


def append_font(original, stride, lowercase):
    require(stride in (44, 52), "Unsupported font record stride")
    require(len(original) == 6953 * stride, "Unexpected original font size")
    extra = read_json(ROOT / "graphics/extended_font.json")["letters"]
    require(set(lowercase) == set(CHARACTERS[:26]), "Incomplete lowercase bank")
    require(set(extra) == set(CHARACTERS[26:]), "Incomplete extended bank")
    letters = {**lowercase, **extra}
    out = bytearray(original)
    for ch in CHARACTERS:
        entry = letters[ch]
        rows = entry["rows"]
        require(
            len(rows) == 12 and all(len(row) == 16 for row in rows),
            "Invalid glyph geometry: " + ch,
        )
        require(
            all(set(row) <= set(".123") for row in rows), "Invalid glyph pixels: " + ch
        )
        require(
            all(set(row) <= {"."} for row in rows[10:]),
            "Glyph would be cropped by DFGB10: " + ch,
        )
        advance = entry["advance"]
        require(
            type(advance) is int and 2 <= advance <= 16, "Invalid glyph advance: " + ch
        )
        require(
            all(set(row[advance:]) <= {"."} for row in rows),
            "Glyph ink exceeds advance: " + ch,
        )
        # Packed 16-pixel cells need an empty right bearing to avoid clipped ink.
        require(
            all(set(row[advance - 1 :]) <= {"."} for row in rows),
            "Glyph must leave a trailing blank column: " + ch,
        )
        bitmap = bytearray()
        for row in rows[: (stride - 4) // 4]:
            pixels = [".123".index(value) for value in row]
            packed = [
                sum(pixels[x + i] << (6 - 2 * i) for i in range(4))
                for x in range(0, 16, 4)
            ]
            bitmap.extend([packed[1], packed[0], packed[3], packed[2]])
        out.extend(struct.pack("<I", advance - 1) + bitmap)
    require(out[: len(original)] == original, "Original font records changed")
    return bytes(out)


def encode_text(text, latin):
    lookup = dict(GLYPH_CODES)
    lookup["\n"] = 0xFF70
    for ch in text:
        if ch not in lookup:
            native = {"'": "’", '"': "”", "-": "‐"}.get(
                ch, chr(ord(ch) + 0xFEE0) if "!" <= ch <= "~" else ch
            )
            require(native in latin, "Unsupported UI character: " + repr(ch))
            lookup[ch] = latin[native]
    return [lookup[ch] for ch in text]
