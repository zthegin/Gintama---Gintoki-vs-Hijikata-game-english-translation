#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import json
import os
import urllib.request

REQUIRED_APPROVALS = 2
MAX_REVIEW_PAGES = 20


def api(path: str, token: str, repo: str):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gintama-peer-review-gate",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def eligible_reviews(
    pr_number: int, sha: str, author: str, token: str, repo: str, fetch=api
):
    """Count the latest submitted review per account, for the current head commit.

    Public GitHub users need no repository role or allowlist entry. Bot reviews,
    the author's reviews, dismissed approvals and approvals of older commits
    do not count.
    """
    latest = {}
    for page in range(1, MAX_REVIEW_PAGES + 1):
        reviews = fetch(
            f"pulls/{pr_number}/reviews?per_page=100&page={page}", token, repo
        )
        for review in reviews:
            user = review.get("user") or {}
            login = user.get("login")
            if login and review.get("state") != "PENDING":
                latest[login.casefold()] = review
        if len(reviews) < 100:
            break
    else:
        raise ValueError("Too many reviews for automatic evaluation")

    approved = []
    for review in latest.values():
        user = review["user"]
        login = user["login"]
        if login.casefold() == author.casefold():
            continue
        if user.get("type", "User") != "User" or login.casefold().endswith("[bot]"):
            continue
        if review["state"] == "APPROVED" and review.get("commit_id") == sha:
            approved.append(login)
    return sorted(approved, key=str.casefold)


def main():
    parser = argparse.ArgumentParser(
        description="Check public PR approvals for the staging review queue"
    )
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--author", required=True)
    args = parser.parse_args()
    users = eligible_reviews(
        args.pr,
        args.sha,
        args.author,
        os.environ["GITHUB_TOKEN"],
        os.environ["GITHUB_REPOSITORY"],
    )
    print(
        f"Current account approvals: {len(users)}/{REQUIRED_APPROVALS}: {', '.join(users)}"
    )
    if len(users) < REQUIRED_APPROVALS:
        print("Not in the reviewed priority queue yet. The owner may still review and merge it.")


if __name__ == "__main__":
    main()
