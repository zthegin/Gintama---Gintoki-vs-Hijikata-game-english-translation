# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import json
import math
import struct
from pathlib import Path

import numpy as np
import ui_tiles as tilecodec
from english_font import GLYPH_CODES
from image_workflow import require as need
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads((ROOT / "graphics/pixel_font.json").read_text(encoding="utf-8"))[
    "rows"
]
GLYPH_IDS = json.loads((ROOT / "graphics/ui_recipes.json").read_text(encoding="utf-8"))[
    "latin_glyphs"
]


def decode_glyph(data):
    raw = np.frombuffer(data, np.uint8).reshape(-1, 4)[:, [1, 0, 3, 2]]
    return np.stack([(raw >> shift) & 3 for shift in [6, 4, 2, 0]], axis=2).reshape(
        -1, 16
    )


def font_decoder(font):
    def glyph(code):
        start = (code - 1) * 52
        need(0 <= start and start + 52 <= len(font), "Glyph is outside the font bank")
        return int.from_bytes(font[start : start + 4], "little") + 1, decode_glyph(
            font[start + 4 : start + 52]
        )

    return glyph


def glyph_text(text, font):
    glyph = font_decoder(font)
    cols = []
    for ch in text:
        if ch == " ":
            cols.append(np.zeros((12, 4), np.uint8))
            continue
        if "a" <= ch <= "z":
            code = 6954 + ord(ch) - 97
        else:
            full = chr(ord(ch) + 65248) if "!" <= ch <= "~" else ch
            full = {"＇": "’", "＂": "”", "－": "‐"}.get(full, full)
            need(full in GLYPH_IDS, "Unsupported graphic lettering: " + repr(ch))
            code = GLYPH_IDS[full]
        advance, pix = glyph(code)
        ink = np.nonzero(np.any(pix > 0, axis=0))[0]
        need(len(ink) > 0, "Empty glyph")
        left = int(ink.min())
        right = int(ink.max()) + 1
        cols.extend([pix[:, left:right], np.zeros((12, 1), np.uint8)])
    canvas = np.hstack(cols)
    yy, xx = np.nonzero(canvas)
    return canvas[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1]


def lettering(text, font, width, height, maxscale=1.5):
    mask = glyph_text(text, font)
    factor = min((width - 2) / mask.shape[1], (height - 2) / mask.shape[0], maxscale)
    need(factor >= 0.65, "Translation too long; edit the UI-specific wording: " + text)
    im = Image.fromarray(mask * 85).resize(
        (max(1, round(mask.shape[1] * factor)), max(1, round(mask.shape[0] * factor))),
        Image.Resampling.LANCZOS,
    )
    a = np.zeros((height, width), np.uint8)
    v = np.asarray(im)
    x = (width - im.width) // 2
    y = (height - im.height) // 2
    a[y : y + im.height, x : x + im.width] = v
    return (a, {"raster_scale": factor, "letter_size": [im.width, im.height]})


def dilate(mask):
    padded = np.pad(mask, 1)
    return np.logical_or.reduce(
        [
            padded[y : y + mask.shape[0], x : x + mask.shape[1]]
            for y in range(3)
            for x in range(3)
        ]
    )


def draw_title(shape, text, font, kind):
    height, width = shape
    mask, info = lettering(text, font, width, height)
    visible = mask > 24
    result = np.zeros(shape, np.uint8)
    result[dilate(visible)] = 10 if kind == "cyan" else 1
    if kind == "cyan":
        yy = np.indices(shape)[0]
        shade = np.clip(3 - (yy - height * 0.35) / (height * 0.35), 1, 3)
        level = np.clip(np.rint(mask / 255 * shade), 0, 3).astype(int) + 11
        result[visible] = level[visible]
    else:
        result[visible] = (
            np.clip(np.ceil(mask[visible] / 85), 1, 3).astype(np.uint8) + 1
        )
    return (result, info)


def erase_gold(image, rect, ink_indices):
    result = image.copy()
    x0, y0, x1, y1 = rect
    roi = result[y0:y1, x0:x1]
    missing = np.isin(roi, ink_indices)
    todo = missing.copy()
    while todo.any():
        changed = False
        for y, x in np.argwhere(todo):
            choices = [
                int(roi[yy, xx])
                for xx, yy in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
                if 0 <= xx < roi.shape[1]
                and 0 <= yy < roi.shape[0]
                and (not todo[yy, xx])
            ]
            if choices:
                roi[y, x] = max(set(choices), key=choices.count)
                todo[y, x] = False
                changed = True
        if not changed:
            roi[todo] = 13
            todo[:] = False
    return result


def nearest_grayscale(mask, colors, allowed):
    levels = np.array([sum(colors[i]) / 3 for i in allowed])
    target = mask.astype(float)
    return np.array(allowed, np.uint8)[
        np.abs(target[:, :, None] - levels).argmin(axis=2)
    ]


def name_mask(text, width=64, height=16):
    name_glyphs = {
        "(": ["..#", ".#.", "#..", "#..", "#..", ".#.", "..#"],
        ")": ["#..", ".#.", "..#", "..#", "..#", ".#.", "#.."],
        "-": ["...", "...", "...", "###", "...", "...", "..."],
        "L": ["#..", "#..", "#..", "#..", "#..", "#..", "###"],
    }
    columns = []
    previous = None
    for ch in text.upper():
        if ch == " ":
            columns.append(np.zeros((7, 3), np.uint8))
        else:
            need(
                ch in ROWS or ch in name_glyphs,
                "Unsupported name character: " + repr(ch),
            )
            rows = name_glyphs.get(ch, ROWS.get(ch))
            pixels = np.array(
                [[255 if p == "#" else 0 for p in row] for row in rows], np.uint8
            )
            ink = np.flatnonzero(pixels.any(axis=0))
            pixels = pixels[:, ink.min() : ink.max() + 1]
            if previous not in {None, " ", "-"} and ch != "-":
                columns.append(np.zeros((7, 1), np.uint8))
            columns.append(pixels)
        previous = ch
    letters = np.hstack(columns)
    need(letters.shape[1] <= width - 2, "Name does not fit without shrinking: " + text)
    need(height >= 9, "Nameplate needs room for its outline")
    mask = np.zeros((height, width), np.uint8)
    x, y = (width - letters.shape[1]) // 2, (height - 7) // 2
    mask[y : y + 7, x : x + letters.shape[1]] = letters
    return mask


def outlined_name(mask, colors):
    indices = range(1, min(16, len(colors)))
    dark = min(indices, key=lambda i: sum(colors[i]))
    light = max(indices, key=lambda i: sum(colors[i]))
    need(
        sum(colors[light]) - sum(colors[dark]) >= 600,
        "Nameplate palette lacks contrast",
    )
    ink = mask > 0
    need(ink.any(), "Nameplate has no visible text")
    padded = np.pad(ink, 1)
    edge = (
        ink
        | padded[:-2, 1:-1]
        | padded[2:, 1:-1]
        | padded[1:-1, :-2]
        | padded[1:-1, 2:]
    )
    result = np.zeros(mask.shape, np.uint8)
    result[edge] = dark
    result[ink] = light
    return result


def white_text(shape, text, font, colors, maxscale=2.0):
    h, w = shape
    lines = text.split("\n")
    scale = maxscale
    while True:
        limit = (w - 12) / scale
        wrapped = []
        for para in lines:
            line = ""
            for word in para.split():
                trial = (line + " " + word).strip()
                if line and glyph_text(trial, font).shape[1] > limit:
                    wrapped.append(line)
                    line = word
                else:
                    line = trial
            wrapped.append(line)
        lineh = round(10 * scale)
        gap = max(3, round(scale * 3))
        total = len(wrapped) * lineh + (len(wrapped) - 1) * gap
        if total <= h - 8:
            break
        scale -= 0.1
        need(scale >= 0.9, "Chapter title does not fit")
    mask = np.zeros(shape, np.uint8)
    y = (h - total) // 2
    for line in wrapped:
        g = glyph_text(line, font)
        im = Image.fromarray(g * 85).resize(
            (round(g.shape[1] * scale), round(g.shape[0] * scale)),
            Image.Resampling.LANCZOS,
        )
        a = np.asarray(im)
        x = (w - im.width) // 2
        mask[y : y + im.height, x : x + im.width] = a
        y += lineh + gap
    gray = [i for i, c in enumerate(colors) if c[0] == c[1] == c[2]]
    need(gray, "No native grayscale colors")
    result = nearest_grayscale(mask, colors, gray)
    result[mask == 0] = 0
    return (
        result,
        {
            "wrapped_English_lines": wrapped,
            "raster_scale": scale,
            "original_palette_only": True,
        },
    )


def extra_render(before, kind, text, font, colors):
    if kind in ["white", "chapter", "summer"]:
        return white_text(
            before.shape,
            text,
            font,
            colors,
            3.0 if kind == "summer" else 2.0 if kind == "chapter" else 1.8,
        )
    if kind == "dark":
        mask, info = lettering(text, font, before.shape[1], before.shape[0])
        result = np.zeros_like(before)
        visible = mask > 20
        result[visible] = np.where(
            mask[visible] > 180, 1, np.where(mask[visible] > 90, 2, 4)
        )
        return (result, info)
    after = before.copy()
    rectangles = []
    if kind == "option":
        rect = (12, 7, 60, 25)
        after = erase_gold_native(
            after, rect, [1, 2, 3, 4, 5, 6, 7, 14, 15], range(8, 13)
        )
        x0, y0, x1, y1 = rect
        mask, info = lettering(text, font, x1 - x0, y1 - y0)
        roi = after[y0:y1, x0:x1]
        visible = mask > 24
        roi[visible] = np.where(
            mask[visible] > 180, 1, np.where(mask[visible] > 90, 2, 15)
        )
        rectangles = [rect]
    elif kind == "start":
        rect = (6, 12, 122, 50)
        after = erase_gold_native(after, rect, range(2, 8), range(8, 11))
        x0, y0, x1, y1 = rect
        lettering_pixels, info = white_text(
            (y1 - y0, x1 - x0), text, font, [(i * 255 // 7,) * 3 for i in range(8)], 1.5
        )
        roi = after[y0:y1, x0:x1]
        visible = lettering_pixels > 0
        roi[visible] = np.maximum(2, lettering_pixels[visible])
        rectangles = [rect]
    elif kind == "profile":
        rectangles = [(21, 7, 112, 23), (18, 24, 113, 40), (18, 40, 112, 55)]
        info = {"line_labels": text.split("\n")}
        for rect, line in zip(rectangles, text.split("\n")):
            after = erase_gold_native(after, rect, range(1, 8), range(8, 13))
            x0, y0, x1, y1 = rect
            mask, _ = lettering(line, font, x1 - x0, y1 - y0)
            roi = after[y0:y1, x0:x1]
            visible = mask > 24
            roi[visible] = np.where(
                mask[visible] > 180, 1, np.where(mask[visible] > 90, 2, 3)
            )
    else:
        raise ValueError(kind)
    outside = np.ones(before.shape, bool)
    for x0, y0, x1, y1 in rectangles:
        outside[y0:y1, x0:x1] = False
    need(
        np.array_equal(before[outside], after[outside]),
        "Extra art changed outside reviewed text boxes",
    )
    info.update(label_ROIs_xyxy=rectangles, outside_ROI_pixels_identical=True)
    return (after, info)


def erase_gold_native(image, rect, ink_indices, background_indices):
    result = image.copy()
    x0, y0, x1, y1 = rect
    roi = result[y0:y1, x0:x1]
    todo = np.isin(roi, list(ink_indices))
    allowed = set(background_indices)
    while todo.any():
        changed = False
        for y, x in np.argwhere(todo):
            choices = [
                int(roi[yy, xx])
                for xx, yy in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
                if 0 <= xx < roi.shape[1]
                and 0 <= yy < roi.shape[0]
                and (not todo[yy, xx])
                and (int(roi[yy, xx]) in allowed)
            ]
            if choices:
                roi[y, x] = max(set(choices), key=choices.count)
                todo[y, x] = False
                changed = True
        if not changed:
            roi[todo] = max(allowed)
            todo[:] = False
    return result


def load_indices(path):
    data = path.read_bytes()
    bpp = 8 if path.parent.name == "chaptertitle" else 4
    head, tiles = tilecodec.decode(data, bpp)
    need(
        tilecodec.encode(head, tiles, bpp) == data, "Source no-op tile roundtrip failed"
    )
    sm = path.with_suffix(".nbfs")
    if sm.exists():
        mapdata = sm.read_bytes()
        width, height = struct.unpack_from("<HH", mapdata)
        need(len(mapdata) == 4 + width * height * 2, "Invalid map dimensions")
        indices = np.zeros((height * 8, width * 8), np.uint8)
        for n, (v,) in enumerate(struct.iter_unpack("<H", mapdata[4:])):
            need(
                v >> 12 == 0,
                "This editor only supports verified palette-bank-zero maps",
            )
            need(v & 1023 < len(tiles), "Out-of-bank source map")
            tile = tiles[v & 1023]
            if v & 1024:
                tile = tile[:, ::-1]
            if v & 2048:
                tile = tile[::-1]
            indices[
                n // width * 8 : n // width * 8 + 8, n % width * 8 : n % width * 8 + 8
            ] = tile
        layout = "native-NBFS-tilemap"
    else:
        width, height = path.dimensions
        indices = tilecodec.sprite(tiles, width, height)
        need(
            tilecodec.pack_sprite(indices, header=head) == data,
            "Source OBJ no-op roundtrip failed",
        )
        mapdata = None
        layout = "visually-reviewed-OBJ-cell-order"
    return (indices, head, tiles, mapdata, layout)


def encode_indices(path, indices, head, oldtiles, mapdata):
    bpp = 8 if path.parent.name == "chaptertitle" else 4
    if mapdata is None:
        data = tilecodec.pack_sprite(indices, bpp, header=head)
        _, roundtiles = tilecodec.decode(data, bpp)
        need(
            np.array_equal(
                tilecodec.sprite(roundtiles, indices.shape[1], indices.shape[0]),
                indices,
            ),
            "Edited OBJ pixel roundtrip failed",
        )
        need(len(data) == path.stat().st_size, "OBJ byte length changed")
        return ({path: data}, {"tilemap_rebuilt": False})
    height, width = indices.shape
    rows = []
    unique = []
    lookup = {}
    for y in range(0, height, 8):
        for x in range(0, width, 8):
            tile = indices[y : y + 8, x : x + 8]
            key = tile.tobytes()
            if key not in lookup:
                lookup[key] = len(unique)
                unique.append(tile.copy())
            rows.append(lookup[key])
    need(
        len(unique) <= len(oldtiles),
        "English needs more unique tiles than the original bank: "
        + path.name
        + " "
        + str((len(unique), len(oldtiles))),
    )
    newtiles = oldtiles.copy()
    newtiles[: len(unique)] = unique
    data = tilecodec.encode(head, newtiles, bpp)
    newmap = mapdata[:4] + struct.pack("<" + "H" * len(rows), *rows)
    need(
        len(data) == path.stat().st_size and len(newmap) == len(mapdata),
        "Mapped asset byte length changed",
    )
    need(
        np.array_equal(
            np.asarray(
                tilecodec.mapped(newtiles, [(i, i, i) for i in range(256)], newmap, bpp)
            )[:, :, 0],
            indices,
        ),
        "Edited tilemap pixel roundtrip failed",
    )
    return (
        {path: data, path.with_suffix(".nbfs"): newmap},
        {
            "tilemap_rebuilt": True,
            "original_tile_bank": len(oldtiles),
            "English_unique_tiles": len(unique),
            "map_dimensions_and_palette_banks_preserved": True,
        },
    )


def compact_mask(text, font, width, height):
    words = text.split()
    layouts = [[text]] + [
        [" ".join(words[:i]), " ".join(words[i:])] for i in range(1, len(words))
    ]
    options = []
    for lines in layouts:
        masks = [glyph_text(line, font) for line in lines]
        gap = 1 if len(lines) > 1 else 0
        scale = min(
            1.0,
            (width - 2) / max((a.shape[1] for a in masks)),
            (height - 2 - gap) / sum((a.shape[0] for a in masks)),
        )
        options.append((scale, lines, masks))
    scale, lines, masks = max(options, key=lambda row: row[0])
    need(scale >= 0.65, "Two-row inventory label still does not fit: " + text)
    images = [
        Image.fromarray(a * 85).resize(
            (max(1, round(a.shape[1] * scale)), max(1, round(a.shape[0] * scale))),
            Image.Resampling.LANCZOS,
        )
        for a in masks
    ]
    total = sum((im.height for im in images)) + len(images) - 1
    mask = np.zeros((height, width), np.uint8)
    y = (height - total) // 2
    for im in images:
        x = (width - im.width) // 2
        mask[y : y + im.height, x : x + im.width] = np.asarray(im)
        y += im.height + 1
    return (
        mask,
        {
            "horizontal_and_vertical_scale": scale,
            "wrapped_English_lines": lines,
            "maximum_rows": 2,
        },
    )


def light_text(mask, colors, used):
    used = sorted(set((int(i) for i in used)))
    foreground = max(used, key=lambda i: sum(colors[i]))
    rgb = np.array(colors, np.int32)
    target = mask[:, :, None] / 255 * rgb[foreground]
    result = np.array(used, np.uint8)[
        np.square(target[:, :, None, :] - rgb[used][None, None, :, :])
        .sum(axis=3)
        .argmin(axis=2)
    ]
    result[mask == 0] = 0
    black = min([i for i in used if i != 0], key=lambda i: sum(colors[i]))
    result[dilate(mask > 32) & (mask == 0)] = black
    return result


def text_mask(text, font, width, height, scale_limit=1.5):
    if not text:
        return (np.zeros((height, width), np.uint8), {"lines": [], "scale": 1})
    lines = text.split("\n")
    raw = [
        glyph_text(line, font) if line else np.zeros((1, 1), np.uint8) for line in lines
    ]
    gap = 1 if len(lines) > 1 else 0
    scale = min(
        scale_limit,
        (width - 2) / max((a.shape[1] for a in raw)),
        (height - 2 - gap * (len(lines) - 1)) / sum((a.shape[0] for a in raw)),
    )
    need(
        scale >= 0.6,
        "UI lettering too small: " + repr(text) + " " + str((width, height, scale)),
    )
    ims = [
        Image.fromarray(a * 85).resize(
            (max(1, round(a.shape[1] * scale)), max(1, round(a.shape[0] * scale))),
            Image.Resampling.LANCZOS,
        )
        for a in raw
    ]
    a = np.zeros((height, width), np.uint8)
    y = (height - sum((im.height for im in ims)) - gap * (len(ims) - 1)) // 2
    for im in ims:
        x = (width - im.width) // 2
        a[y : y + im.height, x : x + im.width] = np.asarray(im)
        y += im.height + gap
    return (
        a,
        {
            "lines": lines,
            "scale": scale,
            "minimum_letter_height": min((im.height for im in ims)),
        },
    )


def draw(before, row, font, colors):
    after = before.copy()
    allowed = np.zeros(before.shape, bool)
    infos = []
    if row.get("coin_face"):
        yy, xx = np.indices(before.shape)
        face = (xx - 15.5) ** 2 + (yy - 15.5) ** 2 <= 12.5**2
        shade = np.clip(
            np.rint(7.5 - (xx - 15.5) * 0.16 - (yy - 15.5) * 0.18), 3, 11
        ).astype(np.uint8)
        after[face] = shade[face]
        allowed |= face
    for task in row["labels"]:
        previous = after.copy()
        x0, y0, x1, y1 = task["rect"]
        need(
            0 <= x0 < x1 <= before.shape[1] and 0 <= y0 < y1 <= before.shape[0],
            "Label ROI out of bounds",
        )
        allowed[y0:y1, x0:x1] = True
        protected = None
        if "component_box" in task:
            from scipy.ndimage import find_objects, label

            rgb = np.array(colors)[before]
            foreground = rgb.max(2) > 0
            components, _ = label(foreground, np.ones((3, 3)))
            erase = np.zeros(before.shape, bool)
            bx0, by0, bx1, by1 = task["component_box"]
            allowed[by0:by1, bx0:bx1] = True
            for index, sl in enumerate(find_objects(components), 1):
                if (
                    sl is not None
                    and bx0 <= sl[1].start
                    and (sl[1].stop <= bx1)
                    and (by0 <= sl[0].start)
                    and (sl[0].stop <= by1)
                ):
                    erase[components == index] = True
            need(erase.any(), "Caption components not found")
            after[erase] = task.get("background", 1)
            protected = foreground & ~erase
        elif "erase_indices" in task:
            after = erase_gold_native(
                after,
                (x0, y0, x1, y1),
                task["erase_indices"],
                task["background_indices"],
            )
        elif task.get("preserve_background"):
            pass
        elif "background_pattern_x" in task:
            phase = task["background_pattern_x"]
            after[y0:y1, x0:x1] = before[y0:y1, phase + np.arange(x0, x1) % 8]
        else:
            after[y0:y1, x0:x1] = task.get("background", 0)
        dx0, dy0, dx1, dy1 = task.get("text_rect", task["rect"])
        need(
            x0 <= dx0 < dx1 <= x1 and y0 <= dy0 < dy1 <= y1,
            "Text box escaped erase region",
        )
        if task.get("font_style") == "crisp":
            mask, info = crisp_mask(
                task["English_UI"],
                dx1 - dx0,
                dy1 - dy0,
                task.get("pixel_height", 10),
                task.get("maximum_integer_scale", 2),
            )
        else:
            mask, info = text_mask(
                task["English_UI"],
                font,
                dx1 - dx0,
                dy1 - dy0,
                task.get("scale_limit", 1.5),
            )
        if task.get("align") == "left" and np.any(mask):
            first = int(np.nonzero(mask)[1].min())
            shift = first - 1
            if shift > 0:
                mask = np.pad(mask[:, shift:], ((0, 0), (0, shift)))
        roi = after[dy0:dy1, dx0:dx1]
        visible = mask > 40
        if "edge" in task:
            roi[dilate(visible)] = task["edge"]
        if "ink" in task:
            roi[visible] = task["ink"]
        else:
            levels = task.get(
                "gray_indices",
                [i for i, col in enumerate(colors) if col[0] == col[1] == col[2]],
            )
            need(levels, "No gray text colors")
            shade = nearest_grayscale(mask, colors, levels)
            roi[visible] = shade[visible]
        infos.append(
            {
                "English_UI": task["English_UI"],
                "English_canonical": task.get(
                    "English_canonical", task["English_UI"].replace("\n", " ")
                ),
                "rect": task["rect"],
                **info,
            }
        )
        if protected is not None:
            need(
                np.array_equal(previous[protected], after[protected]),
                "English caption touched original portrait/art",
            )
            infos[-1]["original_portrait_and_retained_calligraphy_identical"] = True
    need(
        np.array_equal(before[~allowed], after[~allowed]),
        "Pixels outside reviewed text boxes changed",
    )
    return (after, infos)


def crisp_mask(text, width, height, target_height=10, maximum_scale=2):
    lines = []
    for line in text.upper().split("\n"):
        columns = []
        for ch in line:
            if ch not in ROWS:
                raise ValueError("Unsupported crisp UI character: " + repr(ch))
            pixels = np.array(
                [[255 if p == "#" else 0 for p in row] for row in ROWS[ch]], np.uint8
            )
            columns.extend([pixels, np.zeros((7, 1), np.uint8)])
        lines.append(
            np.hstack(columns)[:, :-1] if columns else np.zeros((7, 1), np.uint8)
        )
    maxwidth = max((a.shape[1] for a in lines))
    scale = min(maximum_scale, (width - 2) // maxwidth)
    scale = max(1, scale)
    if maxwidth * scale > width - 2:
        raise ValueError("Crisp lettering does not fit: " + text)
    lineheight = min(target_height, (height - 2 - (len(lines) - 1) * 2) // len(lines))
    lineheight = max(7, lineheight)
    if lineheight * len(lines) + (len(lines) - 1) * 2 > height:
        raise ValueError("Crisp line height does not fit: " + text)
    result = np.zeros((height, width), np.uint8)
    y = (height - lineheight * len(lines) - (len(lines) - 1) * 2) // 2
    for pixels in lines:
        im = Image.fromarray(pixels).resize(
            (pixels.shape[1] * scale, lineheight), Image.Resampling.NEAREST
        )
        x = (width - im.width) // 2
        result[y : y + lineheight, x : x + im.width] = np.asarray(im)
        y += lineheight + 2
    return (
        result,
        {
            "lines": text.upper().split("\n"),
            "horizontal_integer_scale": scale,
            "letter_height": lineheight,
        },
    )


def unpack_sign(data):
    header, tiles = tilecodec.decode(data)
    need(not header and len(tiles) == 384, "Unverified sign format")
    image = np.zeros((128, 192), np.uint8)
    for n in range(6):
        for y in range(8):
            for x in range(8):
                image[
                    n // 3 * 64 + y * 8 : n // 3 * 64 + y * 8 + 8,
                    n % 3 * 64 + x * 8 : n % 3 * 64 + x * 8 + 8,
                ] = tiles[n * 64 + y * 8 + x]
    return image


def pack_sign(image):
    need(image.shape == (128, 192), "Sign canvas dimensions changed")
    tiles = []
    for n in range(6):
        for y in range(8):
            for x in range(8):
                tiles.append(
                    image[
                        n // 3 * 64 + y * 8 : n // 3 * 64 + y * 8 + 8,
                        n % 3 * 64 + x * 8 : n % 3 * 64 + x * 8 + 8,
                    ]
                )
    return tilecodec.encode(b"", np.array(tiles))


def flood(mask, start):
    result = np.zeros(mask.shape, bool)
    x, y = start
    need(mask[y, x], "Flood seed does not match")
    result[y, x] = True
    q = [start]
    while q:
        x, y = q.pop()
        for xx, yy in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            if (
                0 <= xx < mask.shape[1]
                and 0 <= yy < mask.shape[0]
                and mask[yy, xx]
                and (not result[yy, xx])
            ):
                result[yy, xx] = True
                q.append((xx, yy))
    return result


def glyph_mask(text, font):
    need(
        bool(text) and all(c in GLYPH_CODES or c == " " for c in text),
        "Use the supported English letters and punctuation",
    )
    glyph = font_decoder(font)
    columns = []
    height = 12
    for c in text:
        if c == " ":
            columns.append(np.zeros((height, 4), bool))
            continue
        advance, pixels = glyph(GLYPH_CODES[c])
        columns.append(pixels[:, :advance] > 0)
    canvas = np.hstack(columns)
    ys, xs = np.nonzero(canvas)
    need(len(xs) > 0, "No visible letters")
    return canvas[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def translate_sign(data, pal, text, font):
    source = unpack_sign(data)
    need(pack_sign(source) == data, "Sign no-op roundtrip failed")
    need(
        pal[7] == (255, 255, 255) and pal[1] == (49, 49, 49), "Unverified sign palette"
    )
    white = flood(source == 7, (80, 12))
    outside = flood(~white, (0, 0))
    board = ~outside
    ink = board & (source != 7)
    ys, xs = np.nonzero(ink)
    need(int(ink.sum()) == 376, "Original lettering changed")
    need(
        (int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1))
        == (68, 22, 125, 49),
        "Letter bounds mismatch",
    )
    need(
        set(np.unique(source[ink])).issubset({1, 2, 3, 4, 5}),
        "Unexpected board pixel colors",
    )
    result = source.copy()
    result[board] = 7
    letters = glyph_mask(text, font)
    scale = 1.75
    need(letters.shape[1] * scale <= 66, "Text too wide for sign; shorten it")
    angle = math.atan2(11, 70)
    cs = math.cos(angle)
    sn = math.sin(angle)
    cx = 96.5
    cy = 35.5
    grayscale = np.array(pal[1:8], float).mean(axis=1)
    for y, x in np.argwhere(board):
        coverage = 0
        for sy in range(8):
            for sx in range(8):
                dx = x + (sx + 0.5) / 8 - cx
                dy = y + (sy + 0.5) / 8 - cy
                u = (cs * dx + sn * dy) / scale + letters.shape[1] / 2
                v = (-sn * dx + cs * dy) / scale + letters.shape[0] / 2
                if (
                    0 <= u < letters.shape[1]
                    and 0 <= v < letters.shape[0]
                    and letters[int(v), int(u)]
                ):
                    coverage += 1
        if coverage:
            result[y, x] = 1 + int(
                np.abs(grayscale - (255 - (255 - 49) * coverage / 64)).argmin()
            )
    need(np.array_equal(result[~board], source[~board]), "Pixels outside board changed")
    need(np.array_equal(result == 0, source == 0), "Transparency changed")
    need(result.max() < 16, "New palette entry required")
    payload = pack_sign(result)
    need(len(payload) == len(data), "Asset size changed")
    need(np.array_equal(unpack_sign(payload), result), "Edited asset roundtrip failed")
    changed = np.any(np.stack([source != result], axis=0), axis=0)
    return (
        payload,
        source,
        result,
        {
            "native_layout": "six 64x64 4bpp blocks, arranged as three columns by two rows",
            "native_dimensions": [192, 128],
            "file_bytes": len(data),
            "English": text,
            "lettering_original_pixels": int(ink.sum()),
            "changed_pixels": int(changed.sum()),
            "board_mask_pixels": int(board.sum()),
            "all_pixels_outside_board_identical": True,
            "transparency_identical": True,
            "palette_identical": True,
            "source_no_op_roundtrip_identical": True,
            "edited_roundtrip_identical": True,
            "native_font_glyphs": "Existing lowercase bitmaps",
            "scale": scale,
            "rotation_degrees": math.degrees(angle),
        },
    )
