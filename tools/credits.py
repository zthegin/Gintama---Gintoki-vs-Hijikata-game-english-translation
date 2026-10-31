#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from validate_pr import check_text, load, unique_keys
from field_markup import strip_colors

FORMAT = "gintama-translation-credits-v2"
ROOT = Path(__file__).resolve().parents[1]
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
RECORD_ID = re.compile(
    r"(?:[A-Za-z0-9_]{1,100}|battle:battle/script/(?:character|interrupt|item|message)/"
    r"[a-z0-9_]+\.msb:[0-9a-f]{8})\Z"
)
BATCH_PATH = re.compile(r"translations/(?:ready|graphics)/[a-z][a-z0-9_]{0,79}\.json\Z")
REFERENCE_PATHS = {"reference/opening_scene.json", "reference/battle.json"}
REPOSITORY_URL = "https://github.com/zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation"
WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")


def github(path: str, token: str, repo: str):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository identifier")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gintama-credit-bot",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read(4_000_001)
    if len(payload) > 4_000_000:
        raise ValueError("GitHub response exceeds credits review limit")
    return json.loads(payload, object_pairs_hook=unique_keys)


def pull_files(number: int, token: str, repo: str) -> list[dict]:
    files = []
    for page in range(1, 11):
        entries = github(f"pulls/{number}/files?per_page=100&page={page}", token, repo)
        files.extend(entries)
        if len(entries) < 100:
            return files
    raise ValueError("PR file list exceeds credits review limit")


def valid_entry(item: dict):
    required = {
        "number",
        "login",
        "merged_at",
        "base_sha",
        "head_sha",
        "records",
    }
    if not isinstance(item, dict) or set(item) not in (required, required | {"user_id"}):
        raise ValueError("Unexpected credit entry fields")
    if "user_id" in item and (type(item["user_id"]) is not int or item["user_id"] <= 0):
        raise ValueError("Invalid contributor account ID")
    if type(item["number"]) is not int or item["number"] <= 0:
        raise ValueError("Invalid PR number")
    if not isinstance(item["login"], str) or not LOGIN.fullmatch(item["login"]):
        raise ValueError("Invalid contributor account name")
    if not isinstance(item["merged_at"], str):
        raise ValueError("Invalid merge time")
    merged = datetime.fromisoformat(item["merged_at"].replace("Z", "+00:00"))
    if merged.tzinfo is None:
        raise ValueError("Merge time needs a timezone")
    for name in ("base_sha", "head_sha"):
        if not isinstance(item[name], str) or not SHA.fullmatch(item[name]):
            raise ValueError("Invalid immutable credits revision")
    records = item["records"]
    if not isinstance(records, list) or not 1 <= len(records) <= 30000:
        raise ValueError("Invalid credited-record count")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "id",
            "kind",
            "words",
            "characters",
        }:
            raise ValueError("Unexpected credited record fields")
        if not isinstance(record["id"], str) or not RECORD_ID.fullmatch(record["id"]):
            raise ValueError("Invalid credited record ID")
        if record["id"] in seen:
            raise ValueError("Duplicate credited record ID")
        seen.add(record["id"])
        if record["kind"] not in {"new", "revision"}:
            raise ValueError("Invalid translation contribution kind")
        if type(record["words"]) is not int or not 0 <= record["words"] <= 2500:
            raise ValueError("Invalid English word count")
        if (
            type(record["characters"]) is not int
            or not 1 <= record["characters"] <= 2500
        ):
            raise ValueError("Invalid English character count")
        if record["words"] > record["characters"]:
            raise ValueError("Word count exceeds character count")
    if records != sorted(records, key=lambda row: row["id"]):
        raise ValueError("Credited records must be sorted by ID")


def read_ledger(path: Path) -> dict:
    ledger = load(path, 20_000_000)
    if not isinstance(ledger, dict) or set(ledger) != {"format", "entries"}:
        raise ValueError("Invalid credits ledger")
    if ledger == {"format": "gintama-translation-credits-v1", "entries": []}:
        return {"format": FORMAT, "entries": []}
    if ledger["format"] != FORMAT or not isinstance(ledger["entries"], list):
        raise ValueError(
            "Invalid credits ledger; older nonempty ledgers need an audited migration"
        )
    seen = set()
    for entry in ledger["entries"]:
        valid_entry(entry)
        if entry["number"] in seen:
            raise ValueError("Duplicate credited PR")
        seen.add(entry["number"])
    if ledger["entries"] != sorted(ledger["entries"], key=lambda row: row["number"]):
        raise ValueError("Credit entries must be sorted by PR number")
    return ledger


def render(ledger: dict, issues: dict | None = None) -> str:
    issue_entries = (issues or {"entries": []})["entries"]
    if len({item["number"] for item in issue_entries}) != len(issue_entries):
        raise ValueError("Duplicate credited issue")
    totals = {}

    def contributor(item):
        user_id = item.get("user_id")
        key = ("user", user_id) if user_id is not None else ("legacy", item["login"].casefold())
        return totals.setdefault(
            key,
            {
                "login": item["login"],
                "user_id": user_id,
                "prs": 0,
                "issues": 0,
                "new": set(),
                "revision": set(),
                "new_words": 0,
                "revision_words": 0,
                "new_characters": 0,
                "revision_characters": 0,
            },
        )

    def record_totals(row, record):
        kind = record["kind"]
        row[kind].add(record["id"])
        row[f"{kind}_words"] += record["words"]
        row[f"{kind}_characters"] += record["characters"]

    def account_label(item):
        label = f"@{item['login']}"
        if item.get("user_id") is not None:
            label += f" (ID {item['user_id']})"
        return label

    provenance = []
    for item in ledger["entries"]:
        row = contributor(item)
        row["prs"] += 1
        for record in item["records"]:
            record_totals(row, record)
            provenance.append(("PR", item["number"], account_label(item), record))
    for item in issue_entries:
        row = contributor(item)
        row["issues"] += 1
        record_totals(row, item["record"])
        provenance.append(("Issue", item["number"], account_label(item), item["record"]))
    lines = [
        "# Translators",
        "",
        "Thanks to everyone helping translate *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. This page records translation PRs merged into `staging` and accepted website suggestions imported from GitHub issues.",
        "The initial bundled translation is not attributed by these ledgers.",
        "",
        f"**Contributors: {len(totals)} · Merged translation PRs: {len(ledger['entries'])} · Accepted issues: {len(issue_entries)}**",
        "",
        "| GitHub contributor | Merged PRs | Accepted issues | New entries | Revised entries | Words, new / revised | Characters, new / revised |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(totals.values(), key=lambda row: (row["login"].casefold(), row["user_id"] or 0)):
        identity = account_label(row)
        lines.append(
            f"| {identity} | {row['prs']} | {row['issues']} | {len(row['new'])} | {len(row['revision'])} | "
            f"{row['new_words']} / {row['revision_words']} | {row['new_characters']} / {row['revision_characters']} |"
        )
    if not totals:
        lines.append(
            "| *No credited contributions yet* | 0 | 0 | 0 | 0 | 0 / 0 | 0 / 0 |"
        )
    lines += [
        "",
        "New entries were empty before the contribution. Revised entries already had English; their word counts describe the revised passage, not newly translated words. Entry counts use unique IDs per contributor within each column. Words and characters describe each accepted contribution, so repeated revisions can overlap. Characters exclude whitespace; apostrophes within a word stay in that word.",
        "",
        "Numeric GitHub account IDs identify contributors when available. Legacy PR credits without an account ID remain separate from numeric-ID credits; their original handle-based attribution is retained.",
        "",
        "PR counts come from verified base and head revisions. Accepted issue counts come from the verified issue creator and imported record, not the maintainer who applies it. Import PRs are excluded from PR credit so the same import is not counted twice. Unchanged English, notes, metadata, layout-only changes and deletions do not count. Attribution records the submitting account; this is not a claim of sole authorship or translation quality.",
        "",
        "## Contribution provenance",
        "",
        "| Contribution | GitHub contributor | File | Record | Change | Words | Characters |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for kind, number, account, record in sorted(
        provenance, key=lambda item: (item[0], item[1], item[3]["id"])
    ):
        route = "issues" if kind == "Issue" else "pull"
        location = f"[{record['path']}]({REPOSITORY_URL}/blob/main/{record['path']})" if "path" in record else "See PR diff"
        lines.append(
            f"| [{kind} #{number}]({REPOSITORY_URL}/{route}/{number}) | {account} | "
            f"{location} | `{record['id']}` | {record['kind']} | {record['words']} | {record['characters']} |"
        )
    if not provenance:
        lines.append("| *No credited contributions yet* | - | - | - | - | 0 | 0 |")
    lines += [
        "",
        "Updated from `credits/merged_prs.json` and `credits/issue_imports.json`. Please send corrections to the maintainer instead of editing this page.",
        "",
        "Unofficial fan and educational translation of this Nintendo DS game. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](RIGHTS.md).",
        "",
    ]
    return "\n".join(lines)


def text_measurement(before, after, identifier: str) -> dict | None:
    """Measure submitted wording without counting whitespace-only changes."""
    if not isinstance(identifier, str) or not RECORD_ID.fullmatch(identifier):
        raise ValueError("Invalid credited record ID")

    def wording(value):
        if value is None or isinstance(value, str):
            check_text(value, identifier)
            return " ".join(strip_colors(value or "").split())
        if not isinstance(value, list) or not 1 <= len(value) <= 64:
            raise ValueError("Invalid English text parts")
        if not all(isinstance(part, str) for part in value):
            raise ValueError("Invalid English text part")
        joined = " ".join(value)
        check_text("".join(value), identifier)
        # The display text was checked above. Added counting spaces can turn
        # a formatting boundary before a full stop into a false URL match.
        return " ".join(strip_colors(joined).split())

    previous, current = wording(before), wording(after)
    if not current or current == previous:
        return None
    return {
        "id": identifier,
        "kind": "revision" if previous else "new",
        "words": len(WORD.findall(current)),
        "characters": sum(not char.isspace() for char in current),
    }


def measure_records(before: dict, after: dict) -> list[dict]:
    required = {"format", "batch_id", "records"}
    if (
        not isinstance(before, dict)
        or not isinstance(after, dict)
        or set(before) != required
        or set(after) != required
    ):
        raise ValueError("Invalid translation batch for credits")
    if (
        before["format"] != "gintama-community-translation-v1"
        or after["format"] != before["format"]
        or before["batch_id"] != after["batch_id"]
    ):
        raise ValueError("Translation batch header changed")
    if (
        not isinstance(before["records"], list)
        or not isinstance(after["records"], list)
        or len(before["records"]) != len(after["records"])
    ):
        raise ValueError("Translation batch shape changed")
    result, seen = [], set()
    for old, new in zip(before["records"], after["records"]):
        fields = {"id", "source_words_sha256", "english", "translator_note"}
        if (
            not isinstance(old, dict)
            or not isinstance(new, dict)
            or set(old) != fields
            or set(new) != fields
        ):
            raise ValueError("Invalid translation record for credits")
        identifier = old["id"]
        if (
            not isinstance(identifier, str)
            or not RECORD_ID.fullmatch(identifier)
            or identifier in seen
        ):
            raise ValueError("Duplicate or invalid translation record ID")
        seen.add(identifier)
        if (
            identifier != new["id"]
            or old["source_words_sha256"] != new["source_words_sha256"]
        ):
            raise ValueError("Immutable translation metadata changed")
        if not isinstance(old["source_words_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", old["source_words_sha256"]
        ):
            raise ValueError("Invalid source hash")
        for record in (old, new):
            check_text(record["translator_note"], identifier + ".note", 500)
        if not all(record["english"] is None or isinstance(record["english"], str)
                   for record in (old, new)):
            raise ValueError("Invalid translation English")
        measured = text_measurement(old["english"], new["english"], identifier)
        if measured is not None:
            result.append(measured)
    return sorted(result, key=lambda row: row["id"])


def measure_reference_records(path: str, before: dict, after: dict) -> list[dict]:
    """Measure opening or battle wording while keeping every source identity fixed."""
    def indexed(data):
        if not isinstance(data, dict):
            raise ValueError("Invalid reference translation pack")
        if path == "reference/opening_scene.json":
            required = {"format", "script", "scope", "source_msb_sha256",
                        "source_cdb_sha256", "notes", "messages"}
            if (set(data) != required or data["format"] != "gintama-cutscene-v1"
                    or data["script"] != "adventure/script/s01.msb"):
                raise ValueError("Invalid opening translation pack")
            scripts = [data]
        elif path == "reference/battle.json":
            if (set(data) != {"format", "notes", "scripts"}
                    or data["format"] != "gintama-battle-v1"
                    or not isinstance(data["scripts"], list)):
                raise ValueError("Invalid battle translation pack")
            scripts = data["scripts"]
        else:
            raise ValueError("Unsupported reference translation path")
        records, inventory, seen = [], [], set()
        for script in scripts:
            if not isinstance(script, dict):
                raise ValueError("Invalid translation script")
            name = script.get("script")
            if path == "reference/battle.json":
                if (set(script) != {"script", "source_msb_sha256", "source_cdb_sha256",
                                   "record_count", "messages"}
                        or not isinstance(name, str)
                        or not re.fullmatch(
                            r"battle/script/(?:character|interrupt|item|message)/[a-z0-9_]+\.msb", name)):
                    raise ValueError("Invalid battle translation script")
            if not isinstance(script.get("messages"), list):
                raise ValueError("Invalid translation message list")
            identity = {key: value for key, value in script.items() if key != "messages"}
            identity["messages"] = []
            for message in script["messages"]:
                if (not isinstance(message, dict)
                        or set(message) != {"offset", "source_words_sha256", "parts"}
                        or type(message["offset"]) is not int
                        or not 0 <= message["offset"] <= 0xFFFFFFFF
                        or message["offset"] % 2
                        or not isinstance(message["source_words_sha256"], str)
                        or not re.fullmatch(r"[0-9a-f]{64}", message["source_words_sha256"])
                        or not isinstance(message["parts"], list)):
                    raise ValueError("Invalid reference translation message")
                identifier = (f"s01_{message['offset']:08x}" if path == "reference/opening_scene.json"
                              else f"battle:{name}:{message['offset']:08x}")
                if identifier in seen:
                    raise ValueError("Duplicate reference translation record")
                seen.add(identifier)
                identity["messages"].append({
                    **{key: value for key, value in message.items() if key != "parts"},
                    "part_count": len(message["parts"]),
                })
                records.append((identifier, message["parts"]))
            inventory.append(identity)
        header = {key: value for key, value in data.items() if key not in {"messages", "scripts"}}
        return (header, inventory), records

    old_inventory, old_records = indexed(before)
    new_inventory, new_records = indexed(after)
    old_header, old_scripts = old_inventory
    new_header, new_scripts = new_inventory
    if old_header != new_header or len(old_scripts) != len(new_scripts):
        raise ValueError("Immutable reference translation metadata changed")
    for old, new in zip(old_scripts, new_scripts):
        if ({key: value for key, value in old.items() if key != "messages"}
                != {key: value for key, value in new.items() if key != "messages"}):
            raise ValueError("Immutable reference translation metadata changed")
        previous = {row["offset"]: row for row in old["messages"]}
        current = {row["offset"]: row for row in new["messages"]}
        if (any(current.get(offset) != row for offset, row in previous.items())
                or list(current) != sorted(current)):
            raise ValueError("Immutable reference translation metadata changed")
    measured = []
    previous = dict(old_records)
    for identifier, new_parts in new_records:
        record = text_measurement(previous.get(identifier), new_parts, identifier)
        if record is not None:
            measured.append(record)
    return sorted(measured, key=lambda row: row["id"])


def revision_batch(path: str, sha: str, token: str, repo: str) -> dict:
    encoded = urllib.parse.quote(path, safe="/")
    data = github(f"contents/{encoded}?ref={sha}", token, repo)
    if (
        data.get("type") != "file"
        or data.get("encoding") != "base64"
        or data.get("path") != path
    ):
        raise ValueError("GitHub did not return the requested translation file")
    if type(data.get("size")) is not int or not 0 < data["size"] <= 2_000_000:
        raise ValueError("Translation file exceeds credits review limit")
    try:
        raw = base64.b64decode("".join(data["content"].split()), validate=True)
    except (binascii.Error, TypeError) as error:
        raise ValueError("Invalid translation file encoding") from error
    if len(raw) != data["size"]:
        raise ValueError("Translation file size disagrees with GitHub")
    return json.loads(raw, object_pairs_hook=unique_keys)


def merged_entry(
    pr: dict, records: list[dict], base_sha: str | None = None
) -> dict | None:
    if (
        pr.get("merged") is not True
        or not pr.get("merged_at")
        or pr.get("base", {}).get("ref") != "staging"
        or not records
    ):
        return None
    item = {
        "number": pr["number"],
        "login": pr["user"]["login"],
        "merged_at": pr["merged_at"],
        "base_sha": base_sha or pr["base"]["sha"],
        "head_sha": pr["head"]["sha"],
        "records": records,
    }
    if "id" in pr["user"]:
        item["user_id"] = pr["user"]["id"]
    valid_entry(item)
    return item


def verified_entry(pr: dict, token: str, repo: str) -> dict | None:
    if (
        pr.get("merged") is not True
        or not pr.get("merged_at")
        or pr.get("base", {}).get("ref") != "staging"
    ):
        return None
    base_sha, head_sha = pr["base"]["sha"], pr["head"]["sha"]
    if not all(
        isinstance(value, str) and SHA.fullmatch(value)
        for value in (base_sha, head_sha)
    ):
        raise ValueError("Invalid PR revision")
    files = pull_files(pr["number"], token, repo)
    if len({row["filename"] for row in files}) != len(files):
        raise ValueError("Duplicate PR file path")
    if any(row["filename"] == "credits/issue_imports.json" for row in files):
        return None  # The separately verified issue creator receives this credit.
    batches = []
    for row in files:
        name = row["filename"]
        if row.get("status") != "modified":
            return None
        if BATCH_PATH.fullmatch(name) or name in REFERENCE_PATHS:
            batches.append(name)
        elif not re.fullmatch(
            r"csv/(?:ready|graphics)/[a-z][a-z0-9_]{0,79}\.csv", name
        ):
            return None
    if not batches:
        return None
    comparison = github(f"compare/{base_sha}...{head_sha}", token, repo)
    merge_base = comparison["merge_base_commit"]["sha"]
    if not isinstance(merge_base, str) or not SHA.fullmatch(merge_base):
        raise ValueError("Invalid PR merge base")
    records, seen = [], set()
    for name in sorted(batches):
        before = revision_batch(name, merge_base, token, repo)
        after = revision_batch(name, head_sha, token, repo)
        changed = (measure_reference_records(name, before, after) if name in REFERENCE_PATHS
                   else measure_records(before, after))
        if name in REFERENCE_PATHS and any(row["kind"] == "new" for row in changed):
            # This module and its ROM index are from the trusted checkout. The PR
            # cannot change the index within the eligible translation file set.
            from issue_imports import validate_script_changes

            validate_script_changes(name, before, after, root=ROOT)
        for record in changed:
            if record["id"] in seen:
                raise ValueError("Credited record occurs in more than one batch")
            seen.add(record["id"])
            records.append(record)
    return merged_entry(pr, sorted(records, key=lambda row: row["id"]), merge_base)


def add_merged(
    ledger: dict, pr: dict, records: list[dict], base_sha: str | None = None
) -> bool:
    if any(item["number"] == pr["number"] for item in ledger["entries"]):
        return False
    item = merged_entry(pr, records, base_sha)
    if item is None:
        return False
    ledger["entries"].append(item)
    ledger["entries"].sort(key=lambda row: row["number"])
    return True


def collect_push_credits(event: dict, ledger: dict, token: str, repo: str) -> int:
    if event.get("ref") != "refs/heads/staging":
        raise ValueError("Credits workflow must run only for a staging push")
    commits = {entry["id"] for entry in event.get("commits", [])}
    commits.add(event["after"])
    pr_numbers = set()
    for commit_sha in commits:
        if not isinstance(commit_sha, str) or not SHA.fullmatch(commit_sha):
            raise ValueError("Invalid push commit SHA")
        for associated in github(f"commits/{commit_sha}/pulls", token, repo):
            pr_numbers.add(associated["number"])
    additions = 0
    for number in sorted(pr_numbers):
        if any(entry["number"] == number for entry in ledger["entries"]):
            continue
        pr = github(f"pulls/{number}", token, repo)
        entry = verified_entry(pr, token, repo)
        if entry is not None:
            additions += int(
                add_merged(ledger, pr, entry["records"], entry["base_sha"])
            )
    ledger["entries"].sort(key=lambda row: row["number"])
    return additions


def main():
    parser = argparse.ArgumentParser(
        description="Render credits from merged PRs and verified English changes"
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    parser.add_argument(
        "--push-event", type=Path, help="Trusted GitHub push-to-staging event JSON"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    ledger_file, document = root / "credits/merged_prs.json", root / "TRANSLATORS.md"
    ledger = read_ledger(ledger_file)
    from issue_imports import read_issue_ledger

    issues = read_issue_ledger(root / "credits/issue_imports.json")
    if args.push_event:
        event = load(args.push_event)
        token, repo = os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"]
        if collect_push_credits(event, ledger, token, repo):
            ledger_file.write_text(
                json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    text = render(ledger, issues)
    if args.check:
        if document.read_text(encoding="utf-8") != text:
            raise SystemExit("TRANSLATORS.md is not synchronized with credits ledger")
    else:
        document.write_text(text, encoding="utf-8")
    print(f"Credit ledger OK: {len(ledger['entries'])} merged translation PRs, "
          f"{len(issues['entries'])} accepted issues")


if __name__ == "__main__":
    main()
