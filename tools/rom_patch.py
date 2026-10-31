#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import tempfile
import zlib
from pathlib import Path

MAX_ROM_BYTES = 512 * 1024 * 1024
MAX_PATCH_BYTES = 512 * 1024 * 1024
MAGIC = b"BPS1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _number(value: int) -> bytes:
    if value < 0:
        raise ValueError("Negative BPS value")
    out = bytearray()
    while True:
        part = value & 127
        value >>= 7
        if value == 0:
            out.append(part | 128)
            return bytes(out)
        out.append(part)
        value -= 1


def _read_number(data: bytes, position: int, end: int) -> tuple[int, int]:
    number, shift = 0, 1
    for _ in range(11):
        if position >= end:
            raise ValueError("Truncated BPS integer")
        part = data[position]
        position += 1
        number += (part & 127) * shift
        if number > MAX_ROM_BYTES * 8:
            raise ValueError("BPS integer exceeds size limit")
        if part & 128:
            return number, position
        shift <<= 7
        number += shift
    raise ValueError("Invalid BPS integer")


def _crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _read_limited(path: Path, limit: int) -> bytes:
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError(f"File missing or too large: {path}")
    return path.read_bytes()


def create(source: bytes, target: bytes) -> bytes:
    if (
        not source
        or not target
        or len(source) > MAX_ROM_BYTES
        or len(target) > MAX_ROM_BYTES
    ):
        raise ValueError("Empty or oversized ROM")
    if source == target:
        raise ValueError("No differences to patch")
    out = bytearray(MAGIC)
    out.extend(_number(len(source)))
    out.extend(_number(len(target)))
    out.extend(_number(0))  # metadata length
    position = 0
    while position < len(target):
        same = position < len(source) and source[position] == target[position]
        start = position
        position += 1
        while position < len(target):
            next_same = position < len(source) and source[position] == target[position]
            if next_same != same:
                break
            position += 1
        out.extend(_number(((position - start - 1) << 2) | (0 if same else 1)))
        if not same:
            out.extend(target[start:position])
    out.extend(struct.pack("<II", _crc(source), _crc(target)))
    out.extend(struct.pack("<I", _crc(out)))
    return bytes(out)


def header(patch: bytes) -> dict:
    if len(patch) < 16 or not patch.startswith(MAGIC) or len(patch) > MAX_PATCH_BYTES:
        raise ValueError("Not a supported BPS patch")
    if _crc(patch[:-4]) != struct.unpack_from("<I", patch, len(patch) - 4)[0]:
        raise ValueError("Patch checksum mismatch")
    stop = len(patch) - 12
    position = 4
    original_size, position = _read_number(patch, position, stop)
    target_size, position = _read_number(patch, position, stop)
    metadata_size, position = _read_number(patch, position, stop)
    if metadata_size > stop - position:
        raise ValueError("Truncated BPS metadata")
    position += metadata_size
    if original_size > MAX_ROM_BYTES or target_size > MAX_ROM_BYTES:
        raise ValueError("ROM size exceeds limit")
    original_crc, target_crc = struct.unpack_from("<II", patch, stop)
    return {
        "source_size": original_size,
        "target_size": target_size,
        "source_crc32": original_crc,
        "target_crc32": target_crc,
        "actions_start": position,
        "actions_end": stop,
    }


def apply(source: bytes, patch: bytes) -> bytes:
    info = header(patch)
    if len(source) != info["source_size"] or _crc(source) != info["source_crc32"]:
        raise ValueError("Wrong source ROM (size or checksum does not match)")
    output = bytearray()
    position = info["actions_start"]
    end = info["actions_end"]
    while len(output) < info["target_size"]:
        action, position = _read_number(patch, position, end)
        operation, count = action & 3, (action >> 2) + 1
        if count > info["target_size"] - len(output):
            raise ValueError("BPS action exceeds target size")
        if operation == 0:
            start = len(output)
            if start + count > len(source):
                raise ValueError("BPS source read exceeds source ROM")
            output.extend(source[start : start + count])
        elif operation == 1:
            if position + count > end:
                raise ValueError("Truncated BPS target data")
            output.extend(patch[position : position + count])
            position += count
        else:
            raise ValueError(
                "Unsupported BPS copy operation (only patches made by this tool are accepted)"
            )
    if position != end or _crc(output) != info["target_crc32"]:
        raise ValueError("Malformed BPS actions or output checksum mismatch")
    return bytes(output)


def _write_new(path: Path, payload: bytes, overwrite: bool = False) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise ValueError(f"Output exists: {path} (use --force to replace it)")
    fd, name = tempfile.mkstemp(prefix=".patch-", dir=path.parent)
    reserved = False
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if not overwrite:
            with path.open("xb"):
                pass
            reserved = True
        os.replace(name, path)
        reserved = False
    finally:
        if reserved:
            path.unlink(missing_ok=True)
        if os.path.exists(name):
            os.unlink(name)


def _different(paths: list[Path]) -> None:
    resolved = [path.resolve() for path in paths]
    if len(resolved) != len(set(resolved)):
        raise ValueError("Input and output paths must all be different")


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Create and apply BPS patches using SourceRead and TargetRead actions"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser(
        "create", help="Make a BPS delta from two local ROM files"
    )
    make.add_argument("--source", type=Path, required=True)
    make.add_argument("--target", type=Path, required=True)
    make.add_argument("--patch", type=Path, required=True)
    make.add_argument(
        "--scope", default="test-build", help="Descriptive build scope for the manifest"
    )
    make.add_argument("--force", action="store_true")
    install = commands.add_parser(
        "apply", help="Apply a patch to your legally obtained original ROM"
    )
    install.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Your legally obtained, matching unmodified ROM (read only)",
    )
    install.add_argument("--patch", type=Path, required=True)
    install.add_argument("--output", type=Path, required=True)
    install.add_argument(
        "--manifest", type=Path, help="Optional matching .json manifest"
    )
    install.add_argument("--force", action="store_true")
    inspect = commands.add_parser(
        "inspect", help="Read the BPS header and verify its checksum"
    )
    inspect.add_argument("--patch", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "create":
            manifest_path = args.patch.with_suffix(".json")
            _different([args.source, args.target, args.patch, manifest_path])
            if (args.patch.exists() or manifest_path.exists()) and not args.force:
                raise ValueError("Patch or manifest already exists; use --force")
            source = _read_limited(args.source, MAX_ROM_BYTES)
            target = _read_limited(args.target, MAX_ROM_BYTES)
            patch = create(source, target)
            assert apply(source, patch) == target
            manifest = {
                "format": "gintama-bps-release-v1",
                "scope": args.scope,
                "source_size": len(source),
                "target_size": len(target),
                "source_sha256": sha256(source),
                "target_sha256": sha256(target),
                "patch_sha256": sha256(patch),
                "patch_filename": args.patch.name,
                "note": "No game file is included. Use your matching, legally obtained original ROM.",
            }
            _write_new(args.patch, patch, args.force)
            _write_new(
                manifest_path,
                (json.dumps(manifest, indent=2) + "\n").encode(),
                args.force,
            )
            print(
                f"Created {args.patch} and {manifest_path} ({len(patch)} patch bytes)"
            )
        elif args.command == "inspect":
            patch = _read_limited(args.patch, MAX_PATCH_BYTES)
            print(json.dumps(header(patch), indent=2))
        else:
            _different([args.source, args.patch, args.output])
            if args.manifest:
                _different([args.output, args.manifest])
            if args.output.exists() and not args.force:
                raise ValueError("Output exists; use --force to overwrite")
            source = _read_limited(args.source, MAX_ROM_BYTES)
            patch = _read_limited(args.patch, MAX_PATCH_BYTES)
            if args.manifest:
                manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
                if (
                    manifest.get("format") != "gintama-bps-release-v1"
                    or sha256(source) != manifest["source_sha256"]
                    or sha256(patch) != manifest["patch_sha256"]
                    or args.patch.name != manifest["patch_filename"]
                ):
                    raise ValueError(
                        "Original ROM or patch does not match the release manifest"
                    )
            target = apply(source, patch)
            if args.manifest and sha256(target) != manifest["target_sha256"]:
                raise ValueError("Patched ROM does not match the release manifest")
            _write_new(args.output, target, args.force)
            print(f"Patched ROM written to {args.output} (SHA-256 {sha256(target)})")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    cli()
