#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from check_peer_reviews import REQUIRED_APPROVALS, eligible_reviews
from check_issue_import import import_number, validate as validate_issue_import
from check_public_tree import MAX_FILES, MAX_TOTAL_BYTES, MAX_TRACKED_FILE
from text_policy import check_safe_text
from validate_pr import validate

BRANCH = "staging"
LABEL = "reviewed-translation"
WORKFLOWS = ("translation-pr.yml", "peer-reviews.yml")
SHA = re.compile(r"[0-9a-f]{40}\Z")


class GitHub:
    def __init__(self, repository, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or any(
            part in {".", ".."} for part in repository.split("/")
        ):
            raise ValueError("Invalid repository identifier")
        self.repository = repository
        self.token = token

    def __call__(self, path, *, method="GET", data=None):
        if method != "GET":
            label_path = re.fullmatch(
                r"issues/[1-9][0-9]*/labels(?:/reviewed-translation)?", path
            )
            allowed = label_path and (
                (
                    method == "POST"
                    and path.endswith("/labels")
                    and data == {"labels": [LABEL]}
                )
                or (method == "DELETE" and path.endswith("/" + LABEL) and data is None)
            )
            if not allowed:
                raise ValueError("Review automation may only change its advisory label")
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}/{path}",
            data=json.dumps(data).encode() if data is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "gintama-review-queue",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(4_000_001)
        if len(payload) > 4_000_000:
            raise ValueError("GitHub response exceeds the review limit")
        return json.loads(payload) if payload else None


def validate_checkout(api, number, base, head):
    # Candidate files are never imported. Git ignores machine config, hooks,
    # credentials, LFS filters and submodules, including during checkout.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GIT_", "GITHUB_", "GH_"))
    }
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_LFS_SKIP_SMUDGE="1",
        GIT_ASKPASS="",
        SSH_ASKPASS="",
    )
    with tempfile.TemporaryDirectory(prefix="gintama-community-") as temporary:
        directory = Path(temporary)
        empty = directory / "empty"
        empty.mkdir()
        command = [
            "git",
            "-c",
            f"core.hooksPath={empty}",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "credential.helper=",
            "-c",
            "protocol.file.allow=never",
            "-c",
            "protocol.ext.allow=never",
            "-c",
            "protocol.ssh.allow=never",
            "-c",
            "http.followRedirects=false",
            "-c",
            "submodule.recurse=false",
            "-c",
            "filter.lfs.process=",
            "-c",
            "filter.lfs.smudge=",
            "-c",
            "filter.lfs.required=false",
        ]

        def git(*arguments, cwd=None):
            result = subprocess.run(
                command + list(arguments),
                cwd=cwd,
                env=environment,
                check=True,
                capture_output=True,
                timeout=180,
            )
            return result.stdout

        roots = []
        modes = []
        for name, revision, ref in (
            ("base", base, base),
            ("candidate", head, f"refs/pull/{number}/head"),
        ):
            root = directory / name
            git("init", f"--template={empty}", str(root))
            git(
                "remote",
                "add",
                "origin",
                f"https://github.com/{api.repository}.git",
                cwd=root,
            )
            git(
                "fetch",
                "--depth=1",
                "--no-tags",
                "--no-recurse-submodules",
                "origin",
                ref,
                cwd=root,
            )
            if git("rev-parse", "FETCH_HEAD", cwd=root).decode().strip() != revision:
                raise ValueError("Pull request changed during fetch")
            tree = git("ls-tree", "-r", "--long", "-z", "FETCH_HEAD", cwd=root).split(
                b"\0"
            )
            total = 0
            manifest = {}
            for count, entry in enumerate(filter(None, tree), 1):
                header, name = entry.split(b"\t", 1)
                mode, kind, _oid, size = header.split()
                manifest[name] = mode
                if mode not in {b"100644", b"100755"} or kind != b"blob":
                    raise ValueError("Symlinks and submodules cannot be merged")
                total += int(size)
                if (
                    int(size) > MAX_TRACKED_FILE
                    or total > MAX_TOTAL_BYTES
                    or count > MAX_FILES
                ):
                    raise ValueError("Proposed checkout exceeds publication limits")
            modes.append(manifest)
            if len(modes) == 2 and modes[0] != modes[1]:
                raise ValueError("File paths or executable modes changed")
            git("checkout", "--detach", "--force", "FETCH_HEAD", cwd=root)
            roots.append(root)
        proposal = api(f"pulls/{number}")
        issue = import_number(
            proposal.get("head", {}).get("ref", ""),
            (proposal.get("head", {}).get("repo") or {}).get("full_name", ""),
            api.repository,
        )
        if issue is not None:
            result = validate_issue_import(
                *roots, token=api.token, expected_number=issue,
                fetch=lambda issue_number, token=None: api(f"issues/{issue_number}"),
            )
        else:
            result = validate(*roots)
        if result["english_changes"] < 1:
            raise ValueError("No English translation changes")
        return result


def approvals(api, pr):
    return eligible_reviews(
        pr["number"],
        pr["head"]["sha"],
        pr["user"]["login"],
        api.token,
        api.repository,
        lambda path, _token, _repo: api(path),
    )


def current(api, pr):
    if (
        pr.get("state") != "open"
        or pr.get("draft")
        or pr.get("base", {}).get("ref") != BRANCH
        or pr.get("base", {}).get("repo", {}).get("full_name", "").casefold()
        != api.repository.casefold()
    ):
        return False
    if not all(SHA.fullmatch(pr[side]["sha"]) for side in ("head", "base")):
        raise ValueError("Invalid pull request revision")
    return pr["base"]["sha"] == api(f"git/ref/heads/{BRANCH}")["object"]["sha"]


def update_one(api, number, validator=validate_checkout):
    pr = api(f"pulls/{number}")
    # Clear first: failure, changed code, dismissed reviews and retargeting
    # must not leave an old priority signal behind.
    if any(item["name"] == LABEL for item in pr.get("labels", [])):
        api(f"issues/{number}/labels/{LABEL}", method="DELETE")
    if not current(api, pr):
        return "not an open current staging proposal"
    for field, maximum in (("title", 300), ("body", 20000)):
        if pr.get(field):
            check_safe_text(pr[field], f"PR {field}", maximum)
    if len(approvals(api, pr)) < REQUIRED_APPROVALS:
        return "awaiting two current account approvals"
    head, base = pr["head"]["sha"], pr["base"]["sha"]
    validator(api, number, base, head)
    fresh = api(f"pulls/{number}")
    if (
        not current(api, fresh)
        or (
            fresh["head"]["sha"],
            fresh["base"]["sha"],
            fresh["title"],
            fresh.get("body"),
        )
        != (head, base, pr["title"], pr.get("body"))
        or len(approvals(api, fresh)) < REQUIRED_APPROVALS
    ):
        return "proposal or reviews changed during validation"
    api(f"issues/{number}/labels", method="POST", data={"labels": [LABEL]})
    return "labelled for owner review; never merged"


def open_prs(api):
    for page in range(1, 11):
        entries = api(f"pulls?state=open&per_page=100&page={page}")
        yield from entries
        if len(entries) < 100:
            return
    raise ValueError("Too many open pull requests for review-queue scan")


def update_queue(api, event, validator=validate_checkout):
    run = event.get("workflow_run")
    if run is not None:
        run_id = run.get("id")
        if type(run_id) is not int or run_id <= 0:
            raise ValueError("Invalid workflow run ID")
        run = api(f"actions/runs/{run_id}")
        expected = {api(f"actions/workflows/{name}")["id"] for name in WORKFLOWS}
        if (
            run.get("workflow_id") not in expected
            or run.get("status") != "completed"
            or run.get("event") not in {"pull_request", "pull_request_review"}
            or run.get("repository", {}).get("full_name", "").casefold()
            != api.repository.casefold()
        ):
            return {"skipped": "unrelated workflow"}
        # Include unsuccessful runs so a rejected edit loses its old label.
        associated = run.get("pull_requests", [])
        numbers = {pr["number"] for pr in associated}
        if not numbers:
            numbers = {pr["number"] for pr in open_prs(api)}
    else:
        numbers = {pr["number"] for pr in open_prs(api)}
    results = {}
    for number in sorted(numbers):
        if type(number) is not int or number <= 0:
            raise ValueError("Invalid pull request number")
        try:
            results[number] = update_one(api, number, validator)
        except ValueError:
            results[number] = "not eligible for the reviewed-translation label"
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Label reviewed staging translations; never merge a PR"
    )
    parser.add_argument(
        "--event", type=Path, default=os.environ.get("GITHUB_EVENT_PATH")
    )
    args = parser.parse_args()
    try:
        if args.event is None or args.event.stat().st_size > 2_000_000:
            raise ValueError("Missing or oversized workflow event")
        event = json.loads(args.event.read_text(encoding="utf-8"))
        api = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
        print(json.dumps(update_queue(api, event), sort_keys=True))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(
            1, f"Review queue stopped ({type(error).__name__}); no PR was merged.\n"
        )


if __name__ == "__main__":
    main()
