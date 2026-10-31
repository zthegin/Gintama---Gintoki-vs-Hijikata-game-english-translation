#!/usr/bin/env python3
# Unofficial fan translation of Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!
# I do not own the game. Use only a legally obtained ROM; piracy is discouraged. See RIGHTS.md.
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import URLError

from issue_imports import ImportProblem, fetch_issue, propose, safe_path

ROOT = Path(__file__).resolve().parents[1]


def checkout_state(root):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, env=env, stderr=subprocess.DEVNULL).decode().strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise ImportProblem("Choose the repository checkout root")
    branch = git("branch", "--show-current")
    if not branch or branch in {"main", "master"}:
        raise ImportProblem("Apply on staging or a review branch, not main or detached HEAD")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ImportProblem("Commit or save existing edits before importing an issue")
    return branch, git("rev-parse", "HEAD")


def validate_fit(root, outputs, entry, rom_path):
    import image_workflow as images
    import build_ui as ui
    import cutscene_writer as scene
    import dialogue_writer as dialogue
    from text_policy import strict_json
    from english_font import append_font
    source = images.read_rom(Path(rom_path))
    recipe = images.read_json(root / "graphics/ui_recipes.json")
    if images.sha(source) != recipe["source_rom_sha256"]:
        raise ImportProblem("Use the supported, unmodified, legally obtained original ROM")
    files = images.nds_files(source)
    read = lambda name: source[slice(*files[name])]
    letters = images.read_json(root / "graphics/lowercase_font.json")["letters"]
    fonts = [(append_font(read("font/dfgb12.bin"), 52, letters), 52), (append_font(read("font/dfgb10.bin"), 44, letters), 44)]
    record = entry["record"]
    data = strict_json(outputs[record["path"]].decode("utf-8"))
    if record["path"].startswith("translations/ready/"):
        row = next(r for r in data["records"] if r["id"] == record["id"])
        clusters = scene.DialogueClusters(fonts)
        dialogue.patch(read(dialogue.FIELD), read(dialogue.CDB), [row], dialogue.read_json(root / "reference/record_index.json"), clusters.fonts, recipe["latin_glyphs"], packer=clusters)
    elif record["path"].startswith("translations/graphics/"):
        catalog, _, alphabet = images.validate_graphic_translations(root)
        ui.build(source, recipe, catalog, data, alphabet, letters, dialogue_records=[], cutscene_scene=False, battle_pack=False)
    else:
        if record["path"] == "reference/opening_scene.json":
            script = data["script"]
            offset = int(record["id"].split("_")[-1], 16)
            metadata = data
            minimum = 16
        else:
            _, script, raw_offset = record["id"].split(":")
            offset = int(raw_offset, 16)
            metadata = next(s for s in data["scripts"] if s["script"] == script)
            minimum = 4
        if images.sha(read(script)) != metadata["source_msb_sha256"] or images.sha(read(script[:-3] + "cdb")) != metadata["source_cdb_sha256"]:
            raise ImportProblem("Original script hashes differ")
        one = {**metadata, "messages": [r for r in metadata["messages"] if r["offset"] == offset]}
        scene.prepare(read(script), read(script[:-3] + "cdb"), one, fonts, recipe["latin_glyphs"], minimum_offset=minimum)
    return {"source_rom_sha256": images.sha(source), "record_fit_checked": True, "rom_written": False}


def write_changes(root, outputs, expected_state):
    paths = {name: safe_path(root, name) for name in outputs}
    if any(not p.is_file() for p in paths.values()):
        raise ImportProblem("Import may only update existing project files")
    originals = {name: path.read_bytes() for name, path in paths.items()}
    staged, backups, published, retained = {}, {}, [], set()
    try:
        if checkout_state(root) != expected_state:
            raise ImportProblem("Checkout changed during import")
        for name, path in paths.items():
            for contents, mapping in [(outputs[name], staged), (originals[name], backups)]:
                with tempfile.NamedTemporaryFile(prefix=".issue-import-", suffix=".tmp", dir=path.parent, delete=False) as stream:
                    mapping[name] = Path(stream.name)
                    stream.write(contents)
                    stream.flush()
                    os.fsync(stream.fileno())
        for name, path in paths.items():
            safe_path(root, name)
            if path.read_bytes() != originals[name]:
                raise ImportProblem("A destination changed during import")
        # Recheck the branch/HEAD without treating our own reserved files as user edits.
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, env=env).decode().strip()
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, env=env).decode().strip()
        if (branch, head) != expected_state:
            raise ImportProblem("Checkout changed before writing")
        for name, path in paths.items():
            safe_path(root, name)
            if path.read_bytes() != originals[name]:
                raise ImportProblem("A destination changed before writing")
            os.replace(staged[name], path)
            published.append(name)
    except BaseException:
        for name in reversed(published):
            path = paths[name]
            try:
                safe_path(root, name)
                if path.read_bytes() != outputs[name]:
                    raise ImportProblem("Concurrent edit prevents rollback")
                os.replace(backups[name], path)
            except (OSError, ValueError):
                retained.add(name)
        if retained:
            raise ImportProblem("Rollback incomplete; original .issue-import-*.tmp backups were retained beside the affected files. Review the checkout") from None
        raise
    finally:
        cleanup = [*staged.values(), *(path for name, path in backups.items() if name not in retained)]
        for path in cleanup:
            path.unlink(missing_ok=True)


def import_one(root, number, *, apply=False, rom=None, fetch=fetch_issue, fit=validate_fit):
    root = Path(root).absolute()
    safe_path(root, "README.md")
    state = checkout_state(root) if apply else None
    if apply and state[0] not in {"staging", f"codex/issue-{number}"}:
        raise ImportProblem("Use staging or the matching codex/issue-N review branch")
    if apply and rom is None:
        raise ImportProblem("--apply requires --rom with your own legally obtained original ROM")
    token = os.environ.get("GITHUB_TOKEN")
    issue = fetch(number, token=token)
    outputs, entry = propose(root, issue)
    result = {"issue": number, "contributor": "@" + entry["login"], "user_id": entry["user_id"], "record": entry["record"], "changed_files": sorted(outputs), "applied": False}
    if not apply:
        from issue_imports import parse_suggestion
        result["english"] = parse_suggestion(issue["body"])["value"]
        return result
    result["fit"] = fit(root, outputs, entry, rom)
    latest = fetch(number, token=token)
    if latest["user"]["id"] != entry["user_id"] or latest["user"]["login"] != entry["login"] or hashlib.sha256(latest["body"].encode("utf-8")).hexdigest() != entry["body_sha256"]:
        raise ImportProblem("Issue wording or account changed; preview it again")
    write_changes(root, outputs, state)
    result["applied"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description="Preview or locally apply one website suggestion, with issue-author credit")
    parser.add_argument("number", type=int)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true", help="Validate against your ROM and prepare local files for review")
    parser.add_argument("--rom", type=Path, help="Your legally obtained original ROM; required with --apply")
    args = parser.parse_args()
    try:
        result = import_one(args.root, args.number, apply=args.apply, rom=args.rom)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, URLError) as error:
        reason = str(error) if isinstance(error, ImportProblem) else "Check the suggestion format, safety rules and local ROM fit."
        parser.exit(1, f"Issue import stopped: {reason} No remote action was taken.\n")
    print(json.dumps(result, ensure_ascii=True, indent=2))
    print("Review git diff, commit on your review branch, and open a PR to staging. Nothing was committed, pushed, merged or closed." if args.apply else "Preview only. Add --rom PATH --apply on staging or a clean review branch to prepare the files.")


if __name__ == "__main__":
    main()
