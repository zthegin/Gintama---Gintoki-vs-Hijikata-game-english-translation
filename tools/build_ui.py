# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import dialogue_writer as dialogue
import cutscene_writer as cutscene
import battle_writer as battle
import image_workflow as images
import numpy as np
import ui_render as render
import ui_tiles as tiles
from english_font import GLYPH_CODES, append_font, encode_text
from rom_patch import apply, create

ROOT = Path(__file__).resolve().parents[1]


class Resource:
    def __init__(self, rom, files, path, dimensions=None):
        self.rom, self.files = rom, files
        self.path = PurePosixPath(path)
        self.dimensions = dimensions

    @property
    def name(self):
        return self.path.name

    @property
    def parent(self):
        return self.path.parent

    @property
    def stem(self):
        return self.path.stem

    def exists(self):
        return self.path.as_posix() in self.files

    def read_bytes(self):
        left, right = self.files[self.path.as_posix()]
        return self.rom[left:right]

    def with_suffix(self, suffix):
        return Resource(self.rom, self.files, self.path.with_suffix(suffix))

    def stat(self):
        left, right = self.files[self.path.as_posix()]
        return SimpleNamespace(st_size=right - left)

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        return isinstance(other, Resource) and self.path == other.path


def crc16(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xA001 if value & 1 else 0)
    return value


def allocate_fonts(source, fonts):
    files = images.nds_files(source)
    fat, fat_size = struct.unpack_from("<II", source, 0x48)
    spans = [
        struct.unpack_from("<II", source, at) for at in range(fat, fat + fat_size, 8)
    ]
    used = struct.unpack_from("<I", source, 0x80)[0]
    images.require(
        used == max(end for start, end in spans), "Unexpected allocation boundary"
    )
    images.require(
        crc16(source[:0x15E]) == struct.unpack_from("<H", source, 0x15E)[0],
        "Invalid header CRC",
    )
    target = bytearray(source)
    allowed = []
    position = (used + 511) & ~511
    for path, font in fonts.items():
        end = position + len(font)
        images.require(
            end <= len(source) and not any(source[position:end]),
            "Font allocation requires unused zero padding",
        )
        images.require(
            all(end <= left or position >= right for left, right in spans),
            "Font allocation overlaps game data",
        )
        matches = [i for i, span in enumerate(spans) if tuple(span) == files[path]]
        images.require(len(matches) == 1, "Ambiguous font FAT entry")
        fat_entry = fat + matches[0] * 8
        target[position:end] = font
        struct.pack_into("<II", target, fat_entry, position, end)
        allowed.extend([(position, end), (fat_entry, fat_entry + 8)])
        position = (end + 511) & ~511
    struct.pack_into("<I", target, 0x80, end)
    struct.pack_into("<H", target, 0x15E, crc16(target[:0x15E]))
    allowed.extend([(0x80, 0x84), (0x15E, 0x160)])
    return target, allowed


def compress_slot(payload, capacity, *, vram=False):
    packed = images.compress(payload) if vram else compress_greedy(payload)
    images.require(
        len(packed) <= capacity, "Translated image exceeds its compressed slot"
    )
    images.require(
        images.lz10(packed, vram=vram)[0] == payload,
        "Compressed image does not roundtrip",
    )
    return packed + bytes(capacity - len(packed))


def compress_greedy(data):
    output = bytearray(b"\x10" + len(data).to_bytes(3, "little"))
    position = 0
    positions = {}
    while position < len(data):
        flag_at = len(output)
        output.append(0)
        flags = 0
        for bit in range(7, -1, -1):
            if position >= len(data):
                break
            start = position
            best = 0
            distance = 0
            for previous in reversed(positions.get(data[position : position + 3], [])):
                if position - previous > 4096:
                    break
                length = 0
                while (
                    length < 18
                    and position + length < len(data)
                    and data[previous + length] == data[position + length]
                ):
                    length += 1
                if length > best:
                    best = length
                    distance = position - previous
                if best == 18:
                    break
            if best >= 3:
                flags |= 1 << bit
                word = ((best - 3) << 12) | (distance - 1)
                output.extend([word >> 8, word & 255])
                position += best
            else:
                output.append(data[position])
                position += 1
            for at in range(start, position):
                positions.setdefault(data[at : at + 3], []).append(at)
        output[flag_at] = flags
    return bytes(output)


def linear_pixels(data, width, height):
    packed = np.frombuffer(data, np.uint8)
    return np.stack((packed & 15, packed >> 4), axis=1).reshape(height, width)


def pack_linear(pixels):
    flat = pixels.ravel()
    return (flat[::2] | flat[1::2] << 4).tobytes()


def draw_base(row, resource, font, palette):
    kind = row["kind"]
    data = resource.read_bytes()
    if kind in {"packed-nameplate", "inventory-label", "packed-title-prompt"}:
        offset = row["offset"]
        colors = tiles.palette(
            data[row["palette_offset"] : row["palette_offset"] + row["palette_size"]]
        )
        if kind == "packed-nameplate":
            raw = data[offset : offset + row["size"]]
            before = linear_pixels(raw, *row["dimensions"])
            mask = render.name_mask(row["English_UI"], *row["dimensions"])
            after = render.outlined_name(mask, colors)
            payload = pack_linear(after)
            images.require(
                np.array_equal(linear_pixels(payload, *row["dimensions"]), after),
                "Nameplate roundtrip failed",
            )
            return offset, offset + len(raw), payload
        if kind == "inventory-label":
            raw = data[offset : offset + row["size"]]
            head, tile_data = tiles.decode(raw)
            before = tiles.sprite(tile_data, 64, 16)
            images.require(
                tiles.pack_sprite(before, header=head) == raw,
                "Inventory source roundtrip failed",
            )
            mask, _ = render.compact_mask(row["English_UI"], font, 64, 16)
            after = render.light_text(mask, colors, np.unique(before))
            payload = tiles.pack_sprite(after, header=head)
            return offset, offset + len(raw), payload
        raw, end = images.lz10(data, offset)
        images.require(
            end - offset == row["capacity"], "Title compression boundary changed"
        )
        head, tile_data = tiles.decode(raw)
        mask, _ = render.lettering(row["English_UI"], font, 240, 32, maxscale=1.7)
        mask = np.pad(mask, ((0, 0), (8, 8)))
        visible = mask > 48
        rgb = np.array(colors)
        red = int(np.square(rgb - np.array([255, 49, 0])).sum(axis=1).argmin())
        gold = int(np.square(rgb - np.array([255, 255, 0])).sum(axis=1).argmin())
        shadow = int(np.square(rgb - np.array([90, 74, 0])).sum(axis=1).argmin())
        after = np.zeros((32, 256), np.uint8)
        edge = render.dilate(render.dilate(visible))
        shifted = np.pad(edge, ((1, 0), (1, 0)))[:-1, :-1]
        after[shifted] = shadow
        after[edge] = gold
        after[visible] = red
        payload = tiles.pack_sprite(after, header=head)
        return (
            offset,
            offset + row["capacity"],
            compress_slot(payload, row["capacity"], vram=True),
        )
    before, head, tile_data, map_data, _ = render.load_indices(resource)
    colors = tiles.palette(palette)
    if kind in {"option", "dark", "start", "profile", "white", "chapter", "summer"}:
        after, _ = render.extra_render(before, kind, row["English_UI"], font, colors)
    elif kind in {"cyan", "stat", "place-name"}:
        after, _ = render.draw_title(
            before.shape,
            row["English_UI"],
            font,
            "cyan" if kind == "place-name" else kind,
        )
    else:
        x0, y0, x1, y1 = row["rect"]
        after = render.erase_gold(before, row["rect"], [1, 2, 3, 4, 5, 6, 7])
        mask, _ = render.lettering(row["English_UI"], font, x1 - x0, y1 - y0)
        roi = after[y0:y1, x0:x1]
        visible = mask > 32
        roi[visible] = np.clip(3 - np.floor(mask[visible] / 86), 1, 3).astype(np.uint8)
        outside = np.ones(before.shape, bool)
        outside[y0:y1, x0:x1] = False
        images.require(
            np.array_equal(before[outside], after[outside]),
            "Artwork outside label changed",
        )
    changes, _ = render.encode_indices(resource, after, head, tile_data, map_data)
    return changes


def text_width(codes, font, stride=52):
    current = 0
    maximum = 0
    for code in codes:
        if code == 0xFF70:
            maximum = max(maximum, current)
            current = 0
            continue
        at = (code - 1) * stride
        images.require(
            0 <= at and at + stride <= len(font), "Text refers to a missing glyph"
        )
        current += int.from_bytes(font[at : at + 4], "little") + 1
    return max(maximum, current)


def wrap_item(text, font, latin):
    lines = []
    line = ""
    for word in text.split():
        images.require(
            text_width(encode_text(word, latin), font) <= 224,
            "An inventory word exceeds the text box",
        )
        candidate = (line + " " + word).strip()
        if text_width(encode_text(candidate, latin), font) > 224:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    images.require(len(lines) <= 4, "Inventory description exceeds four lines")
    return "\n".join(lines)


def unchanged_outside(before, after, spans):
    images.require(len(before) == len(after), "ROM size changed")
    cursor = 0
    for left, right in sorted(spans):
        images.require(0 <= left <= right <= len(before), "Invalid edited span")
        if left > cursor:
            images.require(
                before[cursor:left] == after[cursor:left],
                "Bytes outside edited spans changed",
            )
        cursor = max(cursor, right)
    images.require(before[cursor:] == after[cursor:], "ROM tail changed")


def unoccupied_script_labels(labels, occupied):
    """A full message translation supersedes contained legacy label patches."""
    pending, skipped = [], []
    for row in labels:
        left, capacity = row["offset"], row["word_capacity"]
        images.require(type(left) is int and left >= 0 and type(capacity) is int
                       and capacity > 0, "Invalid script label span")
        right = left + capacity * 2
        overlaps = [(a, b) for a, b in occupied.get(row["script"], [])
                    if left < b and a < right]
        if not overlaps:
            pending.append(row)
        elif len(overlaps) == 1 and overlaps[0][0] <= left and right <= overlaps[0][1]:
            skipped.append(row["id"])
        else:
            raise ValueError("Script label partially overlaps a translated message")
    return pending, skipped


def build(
    source,
    recipe,
    catalog,
    batch,
    alphabet,
    letters,
    dialogue_records=None,
    *,
    cutscene_scene=None,
    battle_pack=None,
):
    images.require(
        images.sha(source) == recipe["source_rom_sha256"],
        "ROM SHA-256 does not match. Use the supported, unmodified original ROM; "
        "already patched files and other revisions are unsupported",
    )
    files = images.nds_files(source)
    resource = lambda path, dimensions=None: Resource(source, files, path, dimensions)
    font12 = append_font(resource("font/dfgb12.bin").read_bytes(), 52, letters)
    font10 = append_font(resource("font/dfgb10.bin").read_bytes(), 44, letters)
    scene_report = {"messages": [], "extra_font_records": 0}
    scene_spans = []
    if cutscene_scene is not False:
        scene = cutscene.load_scene() if cutscene_scene is None else cutscene_scene
        scene_path = scene["script"]
        scene_cdb = scene_path[:-3] + "cdb"
        scene_bytes, fonts, scene_spans, scene_report = cutscene.prepare(
            resource(scene_path).read_bytes(),
            resource(scene_cdb).read_bytes(),
            scene,
            [(font12, 52), (font10, 44)],
            recipe["latin_glyphs"],
        )
        (font12, _), (font10, _) = fonts
    records = dialogue.load_records(ROOT) if dialogue_records is None else dialogue_records
    field_left, field_right = files[dialogue.FIELD]
    cdb_left, cdb_right = files[dialogue.CDB]
    field_clusters = cutscene.DialogueClusters([(font12, 52), (font10, 44)])
    patched_field, field_spans, dialogue_report = dialogue.patch(
        source[field_left:field_right], source[cdb_left:cdb_right], records,
        dialogue.read_json(ROOT / "reference/record_index.json"),
        field_clusters.fonts, recipe["latin_glyphs"], packer=field_clusters,
    )
    (font12, _), (font10, _) = field_clusters.fonts
    if battle_pack is None:
        battle_pack = False if cutscene_scene is False else battle.load_pack()
    battle_files = {
        path: resource(path).read_bytes()
        for row in battle_pack["scripts"] if row["messages"]
        for path in (row["script"], row["script"][:-3] + "cdb")
    } if battle_pack is not False else {}
    battle_patches, fonts, battle_report = battle.prepare(
        battle_files, battle_pack, [(font12, 52), (font10, 44)], recipe["latin_glyphs"]
    ) if battle_pack is not False else ({}, [(font12, 52), (font10, 44)], [])
    (font12, _), (font10, _) = fonts
    label_scripts = {
        path: resource(path).read_bytes()
        for path in (dialogue.FIELD, "adventure/script/s01.msb")
    }
    occupied = {"adventure/script/s01.msb": scene_spans, dialogue.FIELD: field_spans}
    labels, skipped_labels = unoccupied_script_labels(
        recipe.get("script_labels", []) if cutscene_scene is not False else [], occupied
    )
    label_patches, fonts = cutscene.prepare_labels(
        label_scripts, labels,
        [(font12, 52), (font10, 44)], recipe["latin_glyphs"],
        occupied,
    )
    (font12, _), (font10, _) = fonts
    target, allowed = allocate_fonts(
        source, {"font/dfgb12.bin": font12, "font/dfgb10.bin": font10}
    )
    if scene_spans:
        scene_left, scene_right = files[scene_path]
        target[scene_left:scene_right] = scene_bytes
        allowed.extend(
            (scene_left + left, scene_left + right) for left, right in scene_spans
        )
    for path, (payload, spans) in battle_patches.items():
        left, right = files[path]
        target[left:right] = payload
        allowed.extend((left + a, left + b) for a, b in spans)
    patches = {}
    counts = {"graphics": 0, "ui_text": 0}

    def replace(path, payload, left=0, right=None):
        original = resource(path).read_bytes()
        right = len(original) if right is None else right
        images.require(
            0 <= left <= right <= len(original) and len(payload) == right - left,
            "Asset replacement changed its size",
        )
        if path not in patches:
            patches[path] = bytearray(original)
        patches[path][left:right] = payload

    def asset_changes(changes, *, duplicates=False, vram=False):
        for file, payload in changes.items():
            replace(file.path.as_posix(), payload)
        if duplicates:
            file = next(iter(changes))
            duplicate = file.with_suffix(file.path.suffix + ".z")
            if duplicate.exists():
                images.require(
                    images.lz10(duplicate.read_bytes())[0] == file.read_bytes(),
                    "Compressed duplicate source differs",
                )
                replace(
                    duplicate.path.as_posix(),
                    compress_slot(changes[file], duplicate.stat().st_size, vram=vram),
                )

    print("Rendering signs and menu graphics...", flush=True)
    for row in recipe["signs"]:
        payload, *_ = render.translate_sign(
            resource(row["asset"]).read_bytes(),
            tiles.palette(resource(row["palette"]).read_bytes()),
            row["english"],
            font12,
        )
        replace(row["asset"], payload)
        counts["graphics"] += 1
    for row in recipe["graphics"]:
        file = resource(row["asset"], row.get("dimensions"))
        palette = resource(row["palette"]).read_bytes() if "palette" in row else None
        result = draw_base(row, file, font12, palette)
        if isinstance(result, dict):
            asset_changes(result, duplicates=True)
        else:
            left, right, payload = result
            replace(row["asset"], payload, left, right)
        counts["graphics"] += 1

    print("Rendering additional UI regions...", flush=True)
    for row in recipe["regions"]:
        file = resource(row["asset"], row.get("dimensions"))
        images.require(
            images.sha(file.read_bytes()) == row["source_SHA256"],
            "UI graphic hash mismatch",
        )
        colors = tiles.palette(resource(row["palette"]).read_bytes())
        if row.get("mapped"):
            before, head, tile_data, map_data, _ = tiles.load_map(file)
        else:
            before, head = tiles.unpack_obj(file.read_bytes(), row)
        if "inventory_English" in row:
            mask, _ = render.compact_mask(row["inventory_English"], font12, 64, 16)
            after = render.light_text(mask, colors, np.unique(before))
        else:
            after, _ = render.draw(before, row, font12, colors)
        if row.get("mapped"):
            changes, _ = tiles.pack_map(file, after, head, tile_data, map_data)
        else:
            payload = tiles.pack_obj(after, row, head)
            images.require(
                np.array_equal(tiles.unpack_obj(payload, row)[0], after),
                "UI sprite roundtrip failed",
            )
            changes = {file: payload}
        asset_changes(changes, duplicates=True, vram=True)
        counts["graphics"] += 1
    for path, payload in patches.items():
        left, right = files[path]
        target[left:right] = payload
        allowed.append((left, right))
    print("Building image-label translations...", flush=True)
    result, _, _, name_report = images.prepare(
        source, catalog, batch, alphabet, base=bytes(target)
    )
    target = bytearray(result)
    allowed.append(files[catalog["source_container"]])
    counts["graphics"] += name_report["images"]

    print("Encoding native UI text...", flush=True)
    arm_start, arm_size = (
        struct.unpack_from("<I", source, 0x20)[0],
        struct.unpack_from("<I", source, 0x2C)[0],
    )
    arm = source[arm_start : arm_start + arm_size]
    images.require(
        images.sha(arm) == recipe["source_arm9_sha256"], "ARM9 hash mismatch"
    )
    for row in recipe["ui_text"] + recipe["item_text"]:
        capacity = row["word_capacity"]
        is_item = "field" in row
        size = capacity * 2 if is_item else (capacity + 1) * 2
        offset = row["offset"]
        original = arm[offset : offset + size]
        images.require(
            images.sha(original) == row["source_sha256"], "UI source slot changed"
        )
        if is_item:
            terminator = 0xFF71 if row["field"] == "description" else 0
            text = (
                wrap_item(row["english"], font12, recipe["latin_glyphs"])
                if row["field"] == "description"
                else row["english"]
            )
            text = text.replace("'", "’").replace("-", "‐")
        else:
            terminator = int(row.get("terminator_hex", "0"), 16)
            text = row["English_UI"]
        codes = encode_text(text, recipe["latin_glyphs"])
        words = size // 2
        images.require(
            len(codes) < words, "UI text exceeds its fixed slot: " + row["id"]
        )
        if not is_item:
            for font, stride in [(font12, 52), (font10, 44)]:
                images.require(
                    text_width(codes, font, stride)
                    <= row.get("maximum_line_width", 248),
                    "UI text is too wide",
                )
        payload = struct.pack(
            "<" + "H" * words, *(codes + [terminator] + [0] * (words - len(codes) - 1))
        )
        at = arm_start + offset
        target[at : at + size] = payload
        allowed.append((at, at + size))
        counts["ui_text"] += 1
    print("Encoding dialogue translations...", flush=True)
    target[field_left:field_right] = patched_field
    allowed.extend(
        (field_left + left, field_left + right) for left, right in field_spans
    )
    for path, left, right, payload in label_patches:
        if path == dialogue.FIELD:
            images.require(
                all(right <= a or left >= z for a, z in field_spans),
                "Label overlaps dialogue translation",
            )
        file_start, _ = files[path]
        target[file_start + left:file_start + right] = payload
        allowed.append((file_start + left, file_start + right))
    unchanged_outside(source, target, allowed)
    result = bytes(target)
    newfiles = images.nds_files(result)
    for path in ["field/script/fld_scr.cdb", "adventure/script/s01.cdb"] + [
        path[:-3] + "cdb" for path in battle_patches
    ]:
        left, right = files[path]
        a, b = newfiles[path]
        images.require(
            source[left:right] == result[a:b], "Dialogue source unexpectedly changed"
        )
    report = {
        "source_rom_sha256": images.sha(source),
        "output_rom_sha256": images.sha(result),
        **counts,
        "dialogue_scripts_unchanged": not bool(
            dialogue_report or scene_report["messages"] or label_patches or battle_patches
        ),
        "dialogue_messages": len(dialogue_report),
        "dialogue_pages": sum(row["pages"] for row in dialogue_report),
        "dialogue": dialogue_report,
        "dialogue_end_offsets_unchanged": True,
        "cdb_unchanged": True,
        "native_font_records_unchanged": True,
        "appended_font_records": len(font12) // 52 - 6953,
        "battle_messages": sum(len(row["messages"]) for row in battle_report),
        "battle_scripts": len(battle_report),
        "battle": battle_report,
        "cutscene_messages": len(scene_report["messages"]),
        "cutscene_font_records": scene_report["extra_font_records"],
        "cutscene": scene_report,
        "script_labels": len(label_patches),
        "script_labels_covered_by_messages": skipped_labels,
        "field_cluster_records": len(field_clusters.codes),
        "custom_font_characters": "".join(GLYPH_CODES),
        "outside_edited_spans_unchanged": True,
        "runtime_verified": False,
        "files": {path: images.sha(payload) for path, payload in patches.items()},
    }
    return result, report


def main():
    parser = argparse.ArgumentParser(
        description="Build translated graphics, UI and bundled dialogue from your legally obtained ROM",
        epilog="Unofficial fan tools. I do not own Gintama or the original game; no affiliation or endorsement is implied. See RIGHTS.md."
    )
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="New translated ROM path")
    parser.add_argument("--patch", type=Path, help="Optional local BPS patch path")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--recipes", type=Path, default=ROOT / "graphics/ui_recipes.json"
    )
    parser.add_argument(
        "--translations",
        type=Path,
        default=ROOT / "translations/graphics/gin_tama_names.json",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--dialogue",
        type=Path,
        help="Optional dialogue JSON batch or approved English export; otherwise use bundled batches",
    )
    selection.add_argument(
        "--ui-only",
        action="store_true",
        help="Build graphics and UI without dialogue changes",
    )
    parser.add_argument(
        "--cutscene",
        type=Path,
        help="Opening scene JSON downloaded from the website; otherwise use the bundled opening",
    )
    parser.add_argument("--battle", type=Path,
                        help="Battle JSON from the website; overlays bundled battle translations")
    args = parser.parse_args()
    try:
        images.require(
            not (args.ui_only and (args.cutscene or args.battle)),
            "--cutscene and --battle cannot be used with --ui-only",
        )
        images.require(
            not args.validate_only or not (args.out or args.patch),
            "Validation does not write output files",
        )
        images.require(
            args.validate_only or args.out or args.patch,
            "Choose --out, --patch or --validate-only",
        )
        outputs = {}
        if args.out:
            images.require(
                args.out.suffix.lower() in {".nds", ".srl"},
                "ROM output must end in .nds or .srl",
            )
            args.out = images.private_output(args.out)
            outputs["rom"] = args.out
            outputs["report"] = images.private_output(
                args.out.with_suffix(".report.private.json")
            )
        if args.patch:
            images.require(
                args.patch.suffix.lower() == ".bps", "Patch output must end in .bps"
            )
            args.patch = images.private_output(args.patch)
            outputs["patch"] = args.patch
            outputs["manifest"] = images.private_output(args.patch.with_suffix(".json"))
        images.require(
            len(set(outputs.values())) == len(outputs), "Output paths overlap"
        )
        for path in outputs.values():
            images.require(
                path != args.rom.resolve() and not path.exists(),
                "Choose new output paths, separate from the original ROM",
            )
        source = images.read_rom(args.rom)
        recipe = images.read_json(args.recipes)
        catalog, batch, alphabet = images.validate_graphic_translations(
            ROOT, images.read_json(args.translations)
        )
        letters = images.read_json(ROOT / "graphics/lowercase_font.json")["letters"]
        records = [] if args.ui_only else dialogue.load_records(ROOT, args.dialogue)
        result, report = build(
            source,
            recipe,
            catalog,
            batch,
            alphabet,
            letters,
            records,
            battle_pack=False if args.ui_only else battle.load_pack(args.battle),
            cutscene_scene=(
                False
                if args.ui_only
                else cutscene.load_scene(args.cutscene) if args.cutscene else None
            ),
        )
        images.require(
            images.sha(images.read_rom(args.rom)) == report["source_rom_sha256"],
            "Original ROM changed during build",
        )
        if args.validate_only:
            print(
                json.dumps(
                    {key: value for key, value in report.items() if key != "files"},
                    indent=2,
                )
            )
            return 0
        if args.patch:
            delta = create(source, result)
            images.require(apply(source, delta) == result, "BPS roundtrip failed")
            manifest = {
                "format": "gintama-bps-release-v1",
                "scope": f"Translated graphics, native UI, {report['dialogue_messages']} field messages and {report['cutscene_messages']} opening cutscene entries and {report['battle_messages']} battle messages",
                "source_size": len(source),
                "target_size": len(result),
                "source_sha256": images.sha(source),
                "target_sha256": images.sha(result),
                "patch_sha256": images.sha(delta),
                "patch_filename": args.patch.name,
            }
        payloads = {}
        if args.out:
            payloads[outputs["rom"]] = result
            payloads[outputs["report"]] = (json.dumps(report, indent=2) + "\n").encode(
                "utf-8"
            )
        if args.patch:
            payloads[outputs["patch"]] = delta
            payloads[outputs["manifest"]] = (
                json.dumps(manifest, indent=2) + "\n"
            ).encode("utf-8")
        images.write_outputs(payloads)
        print(
            json.dumps(
                {key: value for key, value in report.items() if key != "files"},
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
