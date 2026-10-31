#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

from check_public_tree import check, public_names

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "__pycache__", ".pytest_cache", "local", "private", "site"}


def package(root, out):
    if (
        root.is_symlink()
        or out.is_symlink()
        or any(p.is_symlink() for p in out.parents)
    ):
        raise ValueError("Symlink source/output refused")
    root = root.resolve()
    out = out.resolve()
    if out.is_relative_to(root):
        raise ValueError("Write the source ZIP outside the repository")
    if out.exists():
        raise ValueError("Output already exists")
    preflight = check(root)
    if preflight:
        raise ValueError("\n".join(preflight))
    names = [
        p for p in public_names(root) if p.as_posix() != "PUBLIC_PACKAGE_AUDIT.json"
    ]
    issues = check(root, names)
    if issues:
        raise ValueError("\n".join(issues))
    items = [(p.as_posix(), (root / p).read_bytes()) for p in names]
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in items}
    audit = {
        "format": "gintama-public-source-package-v1",
        "files": len(items),
        "file_sha256": hashes,
        "excluded": "ROMs, extracted source resources, game fonts, audio, saves, Japanese script dumps, game captures, local builds, caches and Git history",
        "check_scope": "Approved UTF-8 source/data types and three exact hash-allowlisted editor images. English adaptations of game text are bundled. This technical audit does not establish permission for the text or images; no legal clearance is claimed.",
    }
    items.append(
        ("PUBLIC_PACKAGE_AUDIT.json", (json.dumps(audit, indent=2) + "\n").encode())
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    # Fixed metadata makes repeated builds identical and avoids local user/timestamp fields.
    handle, temporary = tempfile.mkstemp(
        prefix=".source-", suffix=".zip", dir=out.parent
    )
    os.close(handle)
    temporary = Path(temporary)
    reserved = False
    try:
        with zipfile.ZipFile(
            temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name, data in items:
                info = zipfile.ZipInfo(
                    "gintama-community-translation/" + name, (1980, 1, 1, 0, 0, 0)
                )
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compresslevel=9)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or len(archive.infolist()) != len(items):
                raise ValueError("Archive integrity failed")
            for name, data in items:
                if archive.read("gintama-community-translation/" + name) != data:
                    raise ValueError("Archive differs from audited source")
        # Reserve exclusively so another process's output is never overwritten.
        with out.open("xb"):
            pass
        reserved = True
        os.replace(temporary, out)
        reserved = False
    finally:
        temporary.unlink(missing_ok=True)
        if reserved:
            out.unlink(missing_ok=True)
    return {
        "files": len(items),
        "bytes": out.stat().st_size,
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "output": str(out),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Package reviewed source/translation files; exclude all local game material"
    )
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        print(json.dumps(package(ROOT, a.out)))
    except (ValueError, OSError) as e:
        p.exit(1, str(e) + "\n")
