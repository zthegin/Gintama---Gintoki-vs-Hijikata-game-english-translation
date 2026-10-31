# Accept a website suggestion

An issue is a proposal, not a change to the game. Review it, import the accepted wording, then merge the resulting PR. Only the owner merges into `staging` and `main`.

## 1. Review the issue

Open the issue from **Issues** in the source repository. Read the English against the Japanese shown locally in the editor with your own legally obtained ROM. Check the meaning, character voice, page breaks and any highlighted words. Do not copy Japanese source text or game captures into the discussion.

In the prepared issue, `\n` means a line break and `\f` a new dialogue page. You do not need to edit that generated format.

Issues have no **Approve** button. Leave a comment with your decision or requested changes. Comments help the discussion; they do not count as PR approvals. Keep the generated suggestion body intact unless the contributor is correcting the translation.

If you submitted the suggestion yourself, describe this as a maintainer check. It is not an independent review. GitHub also prevents approving your own PR.

## 2. Preview and import it locally

This is the maintainer route; contributors can keep using the website. Use a fresh Git clone of the source repository, rather than a Download ZIP folder, and create its Python environment using [installation](APPLY_PATCH.md). Set a repository-local GitHub noreply email before committing. Replace `123` below with the issue number and the ROM path with yours.

```powershell
git fetch origin
git switch -c codex/issue-123 origin/staging
.\.venv\Scripts\python.exe tools/import_issue.py 123
.\.venv\Scripts\python.exe tools/import_issue.py 123 --rom "C:/Games/Gintama/original.nds" --apply
git diff
```

The first Python command previews the wording and proposed files. The second checks the actual ROM fit before writing. Stop if the wording is wrong or either check fails.

Review the diff. It should contain the accepted text, its matching CSV when used, `credits/issue_imports.json` and `TRANSLATORS.md`. Credit comes from the verified issue account, not a name claimed in the body. The importer does not commit, push or merge anything.

## 3. Open the staging PR

Commit only the files listed by the importer and push your review branch. On GitHub, open a PR with **base: staging** and **compare: codex/issue-123**. Reference the issue, for example `Accepts #123`, and describe the checks you ran.

Read **Files changed** and wait for **Translation validation** to pass. CI checks the imported data and attribution without receiving a ROM; the local importer performs the game-file fit check.

Other people can review a PR through **Files changed → Review changes**; see [GitHub's review steps](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request). Issue comments and PR approvals are different. Public approvals are advisory; they do not merge anything. Issue imports include credit receipts and still need the owner's review.

## 4. Publish and close the issue

As owner, merge the checked PR into `staging`. Then open a separate **staging → main** PR. Put `Closes #123` in that promotion PR's description so GitHub closes the issue when the accepted change reaches `main`. Closing keywords in a PR to `staging` do not close it.

Check the promotion diff and CI, merge it as owner, then verify the English and contributor credit on `main`. Rebuild and synchronize the website so it shows the accepted wording too. If the issue is still open after publication, open it and choose **Close issue**, with a link to the published change.

Before using GitHub's merge button, enable your account's email privacy setting. A local Git email override does not control web merges. Alternatively, merge locally using a repository-local noreply identity and push; confirm GitHub marks the PR as merged.

If an API call to comment or close an issue returns **403**, the token needs the source repository's **Issues: read and write** permission. You can use the signed-in GitHub website instead; do not paste a token into an issue or chat.

See GitHub's [issue-linking instructions](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue) and the [detailed maintainer guide](MAINTAINER_SETUP.md#import-one-issue-suggestion).

Issue and PR numbers restarted when the repository was recreated. The existing translations remain included; new accepted contributions receive new credit receipts.

---

Unofficial fan project. I do not own Gintama or the original game. Use only your own legally obtained ROM and keep game files private. See [rights and project limits](../RIGHTS.md).
