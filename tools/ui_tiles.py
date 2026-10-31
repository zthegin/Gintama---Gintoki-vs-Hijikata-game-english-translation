# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import struct

import numpy as np
from image_workflow import require as need
from PIL import Image


def strip(data, unit):
    if len(data) % unit == 4:
        need(
            struct.unpack_from("<I", data)[0] == len(data) - 4,
            "Unrecognized length header",
        )
        return (data[:4], data[4:])
    need(len(data) % unit == 0, "Unrecognized payload size")
    return (b"", data)


def decode(data, bpp=4):
    head, raw = strip(data, 32 if bpp == 4 else 64)
    v = np.frombuffer(raw, np.uint8)
    indices = np.stack((v & 15, v >> 4), axis=1).ravel() if bpp == 4 else v.copy()
    return (head, indices.reshape(-1, 8, 8).copy())


def encode(head, tiles, bpp=4):
    a = np.asarray(tiles, np.uint8).ravel()
    need(not np.any(a >= 1 << bpp), "Out-of-range palette index")
    raw = (a[::2] | a[1::2] << 4).tobytes() if bpp == 4 else a.tobytes()
    return head + raw


def palette(data):
    head, raw = strip(data, 2)
    if len(data) % 32 == 4 and struct.unpack_from("<I", data)[0] == len(data) - 4:
        raw = data[4:]
    colors = []
    for (v,) in struct.iter_unpack("<H", raw):
        colors.append(tuple(((v >> s & 31) * 255 // 31 for s in (0, 5, 10))))
    return colors


def mapped(tiles, colors, data, bpp):
    width, height = struct.unpack_from("<HH", data)
    need(len(data) == 4 + width * height * 2, "Map size mismatch")
    a = np.zeros((height * 8, width * 8, 3), np.uint8)
    for i, (word,) in enumerate(struct.iter_unpack("<H", data[4:])):
        idx = word & 1023
        need(idx < len(tiles), "Map tile index outside bank")
        tile = tiles[idx]
        if word & 1024:
            tile = tile[:, ::-1]
        if word & 2048:
            tile = tile[::-1]
        index = tile.astype(int) + (word >> 12) * 16 if bpp == 4 else tile.astype(int)
        need(index.max() < len(colors), "Map palette out of range")
        a[i // width * 8 : i // width * 8 + 8, i % width * 8 : i % width * 8 + 8] = (
            np.array(colors, np.uint8)[index]
        )
    return Image.fromarray(a)


LEGAL = [
    (64, 64),
    (64, 32),
    (32, 64),
    (32, 32),
    (32, 16),
    (16, 32),
    (16, 16),
    (32, 8),
    (8, 32),
    (16, 8),
    (8, 16),
    (8, 8),
]


def pieces(width, height):
    if (width, height) == (224, 32):
        return [(x, 0, 32, 32) for x in range(0, 224, 32)]
    if (width, height) == (112, 16):
        return [(i * 16, 0, 16, 16) for i in range(7)]
    filled = np.zeros((height // 8, width // 8), bool)
    result = []
    while not filled.all():
        yy, xx = np.argwhere(~filled)[0]
        x = int(xx * 8)
        y = int(yy * 8)
        for cw, ch in LEGAL:
            if (
                x + cw <= width
                and y + ch <= height
                and (not filled[yy : yy + ch // 8, xx : xx + cw // 8].any())
            ):
                break
        else:
            raise ValueError("No legal OBJ cell fits")
        filled[yy : yy + ch // 8, xx : xx + cw // 8] = True
        result.append((x, y, cw, ch))
    return result


def sprite(tiles, width, height):
    need(width * height == len(tiles) * 64, "Sprite dimensions do not fit tiles")
    image = np.zeros((height, width), np.uint8)
    pos = 0
    for x, y, cw, ch in pieces(width, height):
        for ty in range(ch // 8):
            for tx in range(cw // 8):
                image[y + ty * 8 : y + ty * 8 + 8, x + tx * 8 : x + tx * 8 + 8] = tiles[
                    pos
                ]
                pos += 1
    return image


def pack_sprite(image, bpp=4, header=b""):
    height, width = image.shape
    tiles = []
    for x, y, cw, ch in pieces(width, height):
        for ty in range(ch // 8):
            for tx in range(cw // 8):
                tiles.append(
                    image[y + ty * 8 : y + ty * 8 + 8, x + tx * 8 : x + tx * 8 + 8]
                )
    return encode(header, np.array(tiles), bpp)


def rgb(indices, palette):
    colors = np.array(palette + [(255, 0, 255)] * (256 - len(palette)), np.uint8)
    return Image.fromarray(colors[indices])


def cells(row, width, height):
    if "cells" in row:
        return row["cells"]
    if "cell" in row:
        cw, ch = row["cell"]
        need(width % cw == 0 and height % ch == 0, "Cell geometry mismatch")
        return [
            (x, y, cw, ch) for y in range(0, height, ch) for x in range(0, width, cw)
        ]
    return pieces(width, height)


def unpack_obj(data, row):
    head, tiles = decode(data, row.get("bpp", 4))
    width, height = row["dimensions"]
    a = np.zeros((height, width), np.uint8)
    pos = 0
    for x, y, cw, ch in cells(row, width, height):
        for yy in range(y, y + ch, 8):
            for xx in range(x, x + cw, 8):
                a[yy : yy + 8, xx : xx + 8] = tiles[pos]
                pos += 1
    need(pos == len(tiles), "Unused OBJ tiles")
    return (a, head)


def pack_obj(a, row, head):
    height, width = a.shape
    tiles = []
    for x, y, cw, ch in cells(row, width, height):
        for yy in range(y, y + ch, 8):
            for xx in range(x, x + cw, 8):
                tiles.append(a[yy : yy + 8, xx : xx + 8])
    return encode(head, np.array(tiles), row.get("bpp", 4))


def load_map(f):
    bpp = 8 if f.parent.name == "chaptertitle" else 4
    data = f.read_bytes()
    head, tiles = decode(data, bpp)
    need(encode(head, tiles, bpp) == data, "Mapped source no-op mismatch")
    mapdata = f.with_suffix(".nbfs").read_bytes()
    width, height = struct.unpack_from("<HH", mapdata)
    need(len(mapdata) == 4 + width * height * 2, "Map size mismatch")
    a = np.zeros((height * 8, width * 8), np.uint8)
    for i, (word,) in enumerate(struct.iter_unpack("<H", mapdata[4:])):
        tile = tiles[word & 1023]
        if word & 1024:
            tile = tile[:, ::-1]
        if word & 2048:
            tile = tile[::-1]
        a[i // width * 8 : i // width * 8 + 8, i % width * 8 : i % width * 8 + 8] = (
            tile + (word >> 12) * 16 if bpp == 4 else tile
        )
    return (a, head, tiles, mapdata, "native tilemap with original palette banks")


def pack_map(f, after, head, tiles, mapdata):
    unique = []
    lookup = {}
    words = []
    bpp = 8 if f.parent.name == "chaptertitle" else 4
    original_words = list(
        struct.unpack("<" + "H" * ((len(mapdata) - 4) // 2), mapdata[4:])
    )
    ordinal = 0
    for y in range(0, after.shape[0], 8):
        for x in range(0, after.shape[1], 8):
            bank = original_words[ordinal] >> 12 if bpp == 4 else 0
            ordinal += 1
            global_tile = after[y : y + 8, x : x + 8]
            need(
                np.all((global_tile >= bank * 16) & (global_tile < bank * 16 + 16))
                if bpp == 4
                else True,
                "New text crossed a source palette bank",
            )
            tile = global_tile - bank * 16 if bpp == 4 else global_tile
            key = tile.tobytes()
            if key not in lookup:
                index = len(unique)
                unique.append(tile.copy())
                for flip, variant in [
                    (0, tile),
                    (1024, tile[:, ::-1]),
                    (2048, tile[::-1]),
                    (3072, tile[::-1, ::-1]),
                ]:
                    lookup.setdefault(variant.tobytes(), index | flip)
            words.append(lookup[key] | bank << 12)
    need(
        len(unique) <= len(tiles),
        "Mapped English exceeds original tile bank "
        + f.name
        + " "
        + str((len(unique), len(tiles))),
    )
    bpp = 8 if f.parent.name == "chaptertitle" else 4
    result = tiles.copy()
    result[: len(unique)] = unique
    payload = encode(head, result, bpp)
    newmap = mapdata[:4] + struct.pack("<" + "H" * len(words), *words)
    colors = [(i, i, i) for i in range(256)]
    decoded = np.asarray(mapped(result, colors, newmap, bpp))[:, :, 0]
    need(np.array_equal(decoded, after), "Mapped edited pixel roundtrip failed")
    return (
        {f: payload, f.with_suffix(".nbfs"): newmap},
        {
            "tilemap_rebuilt": True,
            "original_tile_bank": len(tiles),
            "English_unique_tiles": len(unique),
            "tile_flip_reuse": True,
        },
    )
