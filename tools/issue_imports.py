# Unofficial fan translation of Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!
# I do not own the game. Use only a legally obtained ROM; piracy is discouraged. See RIGHTS.md.
from __future__ import annotations

import copy
import hashlib
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

from text_policy import strict_json
from validate_pr import check_text, load
from check_public_tree import JAPANESE_PROSE, private_contact
from field_markup import check_record_controls

REPOSITORY = "zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation"
ISSUE_FORMAT = "gintama-issue-imports-v1"
HASH = re.compile(r"[a-f0-9]{64}\Z")
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
SCRIPT = re.compile(r"battle/script/(?:character|interrupt|item|message)/[a-z0-9_]+\.msb\Z")
RECORD_PATH = re.compile(r"(?:translations/(?:ready|graphics)/[a-z][a-z0-9_]{0,79}|reference/(?:opening_scene|battle))\.json\Z")
LEDGER = "credits/issue_imports.json"


class ImportProblem(ValueError):
    """An actionable import error whose message contains no submitted payload."""


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def english_hash(value):
    raw = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ImportProblem("Invalid issue timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ImportProblem("Issue timestamp needs a timezone")
    return result


def safe_path(root, name):
    root = Path(root).absolute()
    path = root / name
    for item in (path, *path.parents):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ImportProblem("Linked import paths are refused")
        try:
            attributes = getattr(item.lstat(), "st_file_attributes", 0)
        except FileNotFoundError:
            attributes = 0
        if attributes & 0x400:
            raise ImportProblem("Reparse points are refused for imports")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ImportProblem("Import path escapes the checkout")
    return path


def read_issue_ledger(path):
    if not path.exists():
        return {"format": ISSUE_FORMAT, "entries": []}
    data = load(path, 20_000_000)
    if not isinstance(data, dict) or set(data) != {"format", "entries"} or data["format"] != ISSUE_FORMAT:
        raise ImportProblem("Invalid issue credit ledger")
    if not isinstance(data["entries"], list) or len(data["entries"]) > 30000:
        raise ImportProblem("Invalid issue credit entries")
    seen, texts = set(), set()
    for entry in data["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"number", "login", "user_id", "updated_at", "body_sha256", "record"}:
            raise ImportProblem("Invalid accepted issue fields")
        if type(entry["number"]) is not int or entry["number"] <= 0 or entry["number"] in seen:
            raise ImportProblem("Invalid or repeated issue number")
        seen.add(entry["number"])
        if type(entry["user_id"]) is not int or entry["user_id"] <= 0 or not isinstance(entry["login"], str) or not LOGIN.fullmatch(entry["login"]):
            raise ImportProblem("Invalid issue account")
        timestamp(entry["updated_at"])
        if not isinstance(entry["body_sha256"], str) or not HASH.fullmatch(entry["body_sha256"]):
            raise ImportProblem("Invalid issue body hash")
        row = entry["record"]
        if not isinstance(row, dict) or set(row) != {"path", "id", "source_words_sha256", "english_sha256", "kind", "words", "characters"}:
            raise ImportProblem("Invalid issue record credit")
        if not isinstance(row["path"], str) or not RECORD_PATH.fullmatch(row["path"]):
            raise ImportProblem("Invalid issue record path")
        if not isinstance(row["id"], str) or not re.fullmatch(r"[A-Za-z0-9_]+|battle:battle/script/(?:character|interrupt|item|message)/[a-z0-9_]+\.msb:[a-f0-9]{8}", row["id"]):
            raise ImportProblem("Invalid issue record ID")
        if any(not isinstance(row[k], str) or not HASH.fullmatch(row[k]) for k in ("source_words_sha256", "english_sha256")):
            raise ImportProblem("Invalid issue translation hash")
        if row["kind"] not in {"new", "revision"} or type(row["words"]) is not int or type(row["characters"]) is not int or not 0 <= row["words"] <= row["characters"] <= 2500 or row["characters"] == 0:
            raise ImportProblem("Invalid issue translation counts")
        key = (row["path"], row["id"], row["english_sha256"])
        if key in texts:
            raise ImportProblem("The same accepted wording cannot earn issue credit twice")
        texts.add(key)
    if data["entries"] != sorted(data["entries"], key=lambda e: e["number"]):
        raise ImportProblem("Issue credits must be sorted by number")
    return data


def validate_issue(issue, number=None):
    if not isinstance(issue, dict) or "pull_request" in issue:
        raise ImportProblem("Expected an issue, not a pull request")
    n = issue.get("number")
    if type(n) is not int or n <= 0 or (number is not None and n != number):
        raise ImportProblem("Issue number does not match")
    if issue.get("repository_url") != f"https://api.github.com/repos/{REPOSITORY}" or issue.get("html_url") != f"https://github.com/{REPOSITORY}/issues/{n}":
        raise ImportProblem("Issue belongs to another repository")
    user = issue.get("user", {})
    if user.get("type") != "User" or type(user.get("id")) is not int or user["id"] <= 0 or not isinstance(user.get("login"), str) or not LOGIN.fullmatch(user["login"]):
        raise ImportProblem("Issue must have an identifiable GitHub user")
    if not isinstance(issue.get("body"), str) or not 0 < len(issue["body"].encode("utf-8")) <= 16000:
        raise ImportProblem("Issue body is empty or too large")
    timestamp(issue.get("updated_at"))
    return issue


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ImportProblem("GitHub API redirect refused; check the repository address")


def fetch_issue(number, token=None):
    if type(number) is not int or number <= 0:
        raise ImportProblem("Use a positive issue number")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "gintama-issue-import", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(f"https://api.github.com/repos/{REPOSITORY}/issues/{number}", headers=headers)
    with urllib.request.build_opener(NoRedirects()).open(request, timeout=20) as response:
        raw = response.read(1000001)
    if len(raw) > 1000000:
        raise ImportProblem("Issue API response is too large")
    return validate_issue(strict_json(raw.decode("utf-8")), number)


def parse_suggestion(body):
    text = body.replace("\r\n", "\n").strip()
    field = re.fullmatch(r'Translation suggestion\n\nID: ([A-Za-z0-9_]+)\nSource SHA-256: ([a-f0-9]{64})\nEnglish \(JSON escaped\):\n([^\n]+)\nNote: ([\s\S]*)\n\nNo source game text is included\.', text)
    if field:
        identifier, digest, raw, note = field.groups()
        value = strict_json(raw)
        if not isinstance(value, str):
            raise ImportProblem("English must be a JSON string")
        check_text(value, "Suggested English")
        note = None if note == "(none)" else note
        check_text(note, "Translator note", 500)
        if JAPANESE_PROSE.search(value) or (note is not None and JAPANESE_PROSE.search(note)):
            raise ImportProblem("Keep source Japanese dialogue local; submit English only")
        if private_contact(value) or (note is not None and private_contact(note)):
            raise ImportProblem("Remove personal contacts and home-directory paths")
        return {"kind": "batch", "id": identifier, "hash": digest, "value": value, "note": note}
    scene = re.fullmatch(r'Opening cutscene translation suggestion\n\nID: (s01_([a-f0-9]{8}))\nScript: (adventure/script/s01\.msb)\nSource SHA-256: ([a-f0-9]{64})\nEnglish parts \(JSON\):\n([^\n]+)\n\nKeep the parts in this order\. No source game text is included\.\nThis suggestion needs maintainer review and a local ROM build\.', text)
    battle = re.fullmatch(r'Battle translation suggestion\n\nID: ([a-z0-9_]+)\nScript: (battle/script/(?:character|interrupt|item|message)/[a-z0-9_]+\.msb)\nOffset: ([0-9]+)\nSource SHA-256: ([a-f0-9]{64})\nEnglish parts \(JSON\):\n([^\n]+)\n\nKeep the parts in order\. No source game text is included\.\nA maintainer must review the English and test a local build\.', text)
    if scene:
        identifier, offset, script, digest, raw = scene.groups()
        offset = int(offset, 16)
        kind = "opening"
    elif battle:
        identifier, script, offset, digest, raw = battle.groups()
        offset = int(offset)
        if identifier != script[14:-4].replace("/", "_") + f"_{offset:08x}":
            raise ImportProblem("Battle ID and offset disagree")
        identifier, kind = f"battle:{script}:{offset:08x}", "battle"
    else:
        raise ImportProblem("Use an unchanged suggestion generated by the website")
    parts = strict_json(raw)
    if not isinstance(parts, list) or not 1 <= len(parts) <= 64 or not all(isinstance(p, str) and p.isascii() and "\r" not in p and "\f" not in p for p in parts) or not any(p.strip() for p in parts) or sum(map(len, parts)) > 2500:
        raise ImportProblem("Invalid English parts")
    for part in parts:
        if part:
            check_text(part, "Suggested part")
    check_text("".join(parts), "Suggested message")
    if any(private_contact(part) for part in parts) or private_contact("".join(parts)):
        raise ImportProblem("Remove personal contacts and home-directory paths")
    return {"kind": kind, "id": identifier, "script": script, "offset": offset, "hash": digest, "value": parts}


def battle_records(root):
    index = load(safe_path(root, "reference/battle_index.json"), 10000000)
    if not isinstance(index, dict) or set(index) != {"format", "source_rom_sha256", "scripts"} or index["format"] != "gintama-battle-index-v1" or not isinstance(index["scripts"], list):
        raise ImportProblem("Invalid battle record index")
    recipe = load(safe_path(root, "graphics/ui_recipes.json"), 10000000)
    if index["source_rom_sha256"] != recipe["source_rom_sha256"]:
        raise ImportProblem("Battle index belongs to another ROM revision")
    result = {}
    for script in index["scripts"]:
        if not isinstance(script, dict) or set(script) != {"script", "source_msb_sha256", "records"} or not isinstance(script["script"], str) or not SCRIPT.fullmatch(script["script"]) or script["script"] in result or not isinstance(script["records"], list) or not isinstance(script["source_msb_sha256"], str) or not HASH.fullmatch(script["source_msb_sha256"]):
            raise ImportProblem("Invalid battle index script")
        rows = {}
        for row in script["records"]:
            if not isinstance(row, list) or len(row) != 4:
                raise ImportProblem("Invalid battle index row")
            start, end, digest, parts = row
            if type(start) is not int or type(end) is not int or start < 4 or start % 2 or end <= start or end % 2 or not isinstance(digest, str) or not HASH.fullmatch(digest) or type(parts) is not int or not 1 <= parts <= 64 or start in rows:
                raise ImportProblem("Invalid battle index record")
            rows[start] = (digest, parts)
        result[script["script"]] = (script["source_msb_sha256"], rows)
    return result


def opening_records(root):
    index = load(safe_path(root, "reference/opening_index.json"), 1000000)
    fields = {"format", "source_rom_sha256", "script", "source_msb_sha256", "source_cdb_sha256", "records"}
    if (not isinstance(index, dict) or set(index) != fields
            or index["format"] != "gintama-opening-index-v1"
            or index["script"] != "adventure/script/s01.msb"
            or not isinstance(index["records"], list) or not 0 < len(index["records"]) <= 2000
            or any(not isinstance(index[k], str) or not HASH.fullmatch(index[k])
                   for k in ("source_rom_sha256", "source_msb_sha256", "source_cdb_sha256"))):
        raise ImportProblem("Invalid opening record index")
    recipe = load(safe_path(root, "graphics/ui_recipes.json"), 10000000)
    if index["source_rom_sha256"] != recipe["source_rom_sha256"]:
        raise ImportProblem("Opening index belongs to another ROM revision")
    records = {}
    previous_end = 16
    for row in index["records"]:
        if not isinstance(row, list) or len(row) != 4:
            raise ImportProblem("Invalid opening index record")
        start, end, digest, count = row
        if (type(start) is not int or type(end) is not int or start < previous_end
                or start % 2 or end <= start or end % 2 or start in records
                or not isinstance(digest, str) or not HASH.fullmatch(digest)
                or type(count) is not int or not 1 <= count <= 64):
            raise ImportProblem("Invalid opening index record")
        records[start] = (digest, count)
        previous_end = end
    return index, records


def validate_script_changes(path, before, after, *, root):
    if path == "reference/opening_scene.json":
        if {k: v for k, v in before.items() if k != "messages"} != {k: v for k, v in after.items() if k != "messages"}:
            raise ImportProblem("Opening inventory changed")
        previous = {row["offset"]: row for row in before["messages"]}
        if Path(root, "reference/opening_index.json").is_file():
            index, records = opening_records(root)
            if any(before[k] != index[k] for k in ("script", "source_msb_sha256", "source_cdb_sha256")):
                raise ImportProblem("Opening script differs from the trusted index")
        else:
            # Older checkouts can revise existing rows, but cannot invent new ones.
            records = {offset: (row["source_words_sha256"], len(row["parts"])) for offset, row in previous.items()}
        offsets = [row["offset"] for row in after["messages"]]
        if (offsets != sorted(set(offsets)) or not previous.keys() <= set(offsets)):
            raise ImportProblem("Opening messages cannot be removed, repeated or reordered")
        for new in after["messages"]:
            if (set(new) != {"offset", "source_words_sha256", "parts"}
                    or type(new["offset"]) is not int or new["offset"] < 16
                    or not isinstance(new["parts"], list)
                    or records.get(new["offset"]) != (new["source_words_sha256"], len(new["parts"]))):
                raise ImportProblem("Opening source metadata changed")
            parts = new["parts"]
            if not isinstance(parts, list) or not 1 <= len(parts) <= 64 or not all(isinstance(p, str) and p.isascii() and "\r" not in p and "\f" not in p for p in parts) or not any(p.strip() for p in parts) or sum(map(len, parts)) > 2500:
                raise ImportProblem("Invalid opening English parts")
            for part in parts:
                if part:
                    check_text(part, "Opening part")
            check_text("".join(parts), "Opening message")
    elif path == "reference/battle.json":
        from battle_writer import validate_pack
        validate_pack(after)
        if {k: v for k, v in before.items() if k != "scripts"} != {k: v for k, v in after.items() if k != "scripts"} or len(before["scripts"]) != len(after["scripts"]):
            raise ImportProblem("Battle inventory changed")
        index = battle_records(root)
        for old, new in zip(before["scripts"], after["scripts"]):
            if {k: v for k, v in old.items() if k != "messages"} != {k: v for k, v in new.items() if k != "messages"}:
                raise ImportProblem("Battle source metadata changed")
            known_sha, rows = index[old["script"]]
            if known_sha != old["source_msb_sha256"] or [r["offset"] for r in new["messages"]] != sorted(r["offset"] for r in new["messages"]):
                raise ImportProblem("Battle script index differs")
            if not {r["offset"] for r in old["messages"]} <= {r["offset"] for r in new["messages"]}:
                raise ImportProblem("Battle messages cannot be removed")
            for row in new["messages"]:
                if rows.get(row["offset"]) != (row["source_words_sha256"], len(row["parts"])):
                    raise ImportProblem("Battle record differs from trusted index")
    else:
        raise ImportProblem("Unsupported script translation file")


def propose(root, issue):
    from credits import read_ledger, render, text_measurement
    from sync_csv import csv_path, render as render_csv
    root = Path(root)
    validate_issue(issue)
    suggested = parse_suggestion(issue["body"])
    ledger = read_issue_ledger(safe_path(root, LEDGER))
    if any(e["number"] == issue["number"] for e in ledger["entries"]):
        raise ImportProblem("This issue has already been accepted")
    outputs = {}
    if suggested["kind"] == "batch":
        found = []
        for path in sorted((root / "translations").glob("*/*.json")):
            rel = path.relative_to(root).as_posix()
            if not RECORD_PATH.fullmatch(rel):
                raise ImportProblem("Unexpected translation file")
            data = load(safe_path(root, rel))
            for row in data["records"]:
                if row["id"] == suggested["id"]:
                    found.append((rel, data, row))
        if len(found) != 1:
            raise ImportProblem("Unknown or repeated translation ID")
        path, data, row = found[0]
        index = load(safe_path(root, "reference/record_index.json"), 20000000)
        indexed = [r for r in index["records"] if r["id"] == row["id"]]
        if len(indexed) != 1 or row["source_words_sha256"] != suggested["hash"] or indexed[0]["source_words_sha256"] != suggested["hash"]:
            raise ImportProblem("Suggested source hash differs from the index")
        if suggested["value"].count("\f") != indexed[0]["page_breaks"]:
            raise ImportProblem("Keep the original page-break count")
        try:
            check_record_controls(suggested["value"], indexed[0])
        except ValueError as error:
            raise ImportProblem(str(error)) from error
        previous = row["english"]
        row["english"], row["translator_note"] = suggested["value"], suggested["note"]
        outputs[csv_path(root / path, root).relative_to(root).as_posix()] = render_csv(data).encode("utf-8")
    else:
        path = "reference/opening_scene.json" if suggested["kind"] == "opening" else "reference/battle.json"
        before = load(safe_path(root, path), 10000000)
        data = copy.deepcopy(before)
        if suggested["kind"] == "opening":
            rows = data["messages"]
        else:
            scripts = [s for s in data["scripts"] if s["script"] == suggested["script"]]
            if len(scripts) != 1:
                raise ImportProblem("Unknown battle script")
            rows = scripts[0]["messages"]
        matches = [r for r in rows if r["offset"] == suggested["offset"]]
        if matches:
            row = matches[0]
            if row["source_words_sha256"] != suggested["hash"] or len(row["parts"]) != len(suggested["value"]):
                raise ImportProblem("Source hash or text-part count changed")
            previous = row["parts"]
            row["parts"] = suggested["value"]
        else:
            previous = None
            rows.append({"offset": suggested["offset"], "source_words_sha256": suggested["hash"], "parts": suggested["value"]})
            rows.sort(key=lambda r: r["offset"])
        validate_script_changes(path, before, data, root=root)
    measurement = text_measurement(previous, suggested["value"], suggested["id"])
    if measurement is None:
        raise ImportProblem("No new English wording to accept")
    record = {"path": path, **measurement, "source_words_sha256": suggested["hash"], "english_sha256": english_hash(suggested["value"])}
    entry = {"number": issue["number"], "login": issue["user"]["login"], "user_id": issue["user"]["id"], "updated_at": issue["updated_at"], "body_sha256": hashlib.sha256(issue["body"].encode("utf-8")).hexdigest(), "record": record}
    for old in ledger["entries"]:
        if (old["record"]["path"], old["record"]["id"], old["record"]["english_sha256"]) == (path, record["id"], record["english_sha256"]):
            raise ImportProblem("This wording has already received issue credit")
    ledger["entries"].append(entry)
    ledger["entries"].sort(key=lambda e: e["number"])
    outputs[path] = encoded(data)
    outputs[LEDGER] = encoded(ledger)
    outputs["TRANSLATORS.md"] = render(read_ledger(safe_path(root, "credits/merged_prs.json")), ledger).encode("utf-8")
    return outputs, entry
