#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prerequisites() -> str:
    programs = {name: shutil.which(name) for name in ("git", "node")}
    missing = [name for name, path in programs.items() if path is None]
    if missing:
        names = ", ".join(
            "Git" if name == "git" else "Node.js 22+" for name in missing
        )
        raise ValueError(
            f"Install {names}, reopen your terminal, then retry the full checks"
        )
    node = programs["node"]
    version = subprocess.run(
        [node, "--version"], capture_output=True, text=True, timeout=10
    )
    match = re.fullmatch(r"v(\d+)\.\d+\.\d+(?:[-+].*)?", version.stdout.strip())
    if version.returncode or match is None or int(match[1]) < 22:
        raise ValueError("Node.js 22 or newer is required for the full checks")
    modules = {"numpy": "NumPy", "PIL": "Pillow", "scipy": "SciPy"}
    missing = [
        label
        for name, label in modules.items()
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        command = f'"{sys.executable}" -m pip install -r "{ROOT / "requirements.txt"}"'
        if os.name == "nt":
            command = "PowerShell: & " + command
        raise ValueError(
            f"Missing {', '.join(missing)}. Install them with this Python:\n{command}"
        )
    return node


def verify(output: Path) -> dict:
    if output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError("Symlink verification output refused")
    output = output.resolve()
    if output == ROOT or output.is_relative_to(ROOT) or ROOT.is_relative_to(output):
        raise ValueError("Choose a new output directory outside the repository")
    if output.exists():
        raise ValueError("Verification output already exists; choose a new directory")
    node = prerequisites()
    output.mkdir(parents=True)
    temporary = output / "temporary"
    temporary.mkdir()
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
        TMP=str(temporary),
        TEMP=str(temporary),
        TMPDIR=str(temporary),
    )
    report = {
        "format": "gintama-verification-v1",
        "steps": [],
        "passed": False,
        "scope": "Offline checks; no emulator, network or publication. Private game inputs are optional. Not legal clearance.",
        "private_input_tests_enabled": bool(
            env.get("GINTAMA_TEST_ROM") or env.get("GINTAMA_TEST_MSB")
        ),
    }
    python = [sys.executable, "-B"]
    commands = [
        ("source-audit", python + ["tools/check_public_tree.py"]),
        ("csv-pairs", python + ["tools/sync_csv.py", "--from", "json", "--check"]),
        ("credits", python + ["tools/credits.py", "--check"]),
        (
            "batch-integrity",
            python + ["tools/validate_pr.py", "--base", ".", "--candidate", "."],
        ),
        ("python-tests", python + ["-m", "unittest", "discover", "-s", "tests", "-v"]),
        (
            "browser-code-tests",
            [node, "--test"]
            + [str(p) for p in sorted((ROOT / "tests/browser").glob("*.test.mjs"))],
        ),
        (
            "website-build",
            python + ["tools/build_web.py", "--out", str(output / "site")],
        ),
        (
            "website-audit",
            python
            + [
                "tools/check_public_tree.py",
                "--repo",
                str(output / "site"),
                "--profile",
                "site",
            ],
        ),
        (
            "website-links-and-notices",
            python + ["tools/check_site.py", "--site", str(output / "site")],
        ),
        (
            "approved-export",
            python
            + [
                "tools/export_approved.py",
                "--repo",
                ".",
                "--out",
                str(output / "approved"),
            ],
        ),
        (
            "export-audit",
            python
            + [
                "tools/check_public_tree.py",
                "--repo",
                str(output / "approved"),
                "--profile",
                "export",
            ],
        ),
        (
            "package-first",
            python
            + ["tools/package_source.py", "--out", str(output / "source-first.zip")],
        ),
        (
            "package-second",
            python
            + ["tools/package_source.py", "--out", str(output / "source-second.zip")],
        ),
    ]
    try:
        for name, command in commands:
            print(f"Checking {name}...", flush=True)
            log = output / (name + ".log")
            with log.open("w", encoding="utf-8") as stream:
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    env=env,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=900,
                )
            report["steps"].append(
                {"name": name, "exit_code": result.returncode, "log": log.name}
            )
            if result.returncode:
                raise ValueError(f"{name} failed; see {log.name}")
        first = (output / "source-first.zip").read_bytes()
        second = (output / "source-second.zip").read_bytes()
        if first != second:
            raise ValueError("Repeated source packages differ")
        report["package_sha256"] = hashlib.sha256(first).hexdigest()
        report["repeatable_package"] = True
        report["passed"] = True
        return report
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        report["error"] = str(error)
        raise
    finally:
        (output / "verification.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check source, tests, website, exports and repeatable packaging without a game file"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="New private output directory outside the repository",
    )
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.out), indent=2))
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, str(error) + "\n")
