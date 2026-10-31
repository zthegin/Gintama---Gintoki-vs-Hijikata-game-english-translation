# Maintainer setup

The source repository holds tools and translation files. The separate [website repository](https://github.com/zthegin/zthegin.github.io) serves the editor. I do not own Gintama or its original content; see [RIGHTS.md](../RIGHTS.md). Keep game files and private QA outside both repositories.

## Branches

- `main` is the published version. Players download from here.
- `staging` receives translation PRs. Contributors start their branch from current upstream staging.

Only `zthegin` merges or pushes into `staging` and `main`. Reviews are advisory: two other accounts approving the current revision mark valid translation-only PRs with `reviewed-translation`. The owner still decides whether to merge. Nothing merges automatically, including after two approvals.

Open the [reviewed translations queue](https://github.com/zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation/pulls?q=is%3Apr+is%3Aopen+base%3Astaging+label%3Areviewed-translation+sort%3Aupdated-desc) to see those PRs first. Labels do not change the order of GitHub's ordinary PR list. Two accounts may belong to one person; read the wording and diff before merging.

## Enforce owner-only updates

Workflow files cannot restrict who may merge. The [complete rules JSON](branch-rules.json) describes both repositories. It is a reference bundle, not a single GitHub import. Import the four small files separately in **Settings → Rules → Rulesets → New ruleset → Import a ruleset**:

| Repository | Import both files |
| --- | --- |
| Source, `main` and `staging` | [Owner updates](rulesets/source-owner-updates.json) and [history protection](rulesets/source-history.json) |
| Website, `main` | [Owner updates](rulesets/website-owner-updates.json) and [history protection](rulesets/website-history.json) |

Check that each imported ruleset is **Active**. The update rule names only the individual `zthegin` account, GitHub user ID `344322420`, as its Always allow bypass. GitHub supports [individual user bypass](https://github.blog/changelog/2026-05-07-repository-rulesets-user-bypass-and-branch-renaming/). Do not substitute Repository admins, write/maintain roles, an Actions bot or an App. This keeps direct owner pushes and manual merges available while excluding other writers.

History protection is a separate ruleset with no bypass. It blocks force pushes and deletion even for the owner during ordinary use. Administrators can still change repository rules, so keep administration access to your own account.

The files do not install themselves, and this project does not silently apply them. After importing, check the active rules on each branch. Public reviews remain advisory; the JSON does not turn two approvals into an automatic merge. For stricter maintenance later, require PRs, resolved conversations and the `Translation validation` check from GitHub Actions. That is a separate choice from allowing direct owner pushes.

Under **Settings → General → Pull Requests**, turn **Allow auto-merge** off and do not enable merge queues. Under **Settings → Moderation options → Code review limits**, leave restrictions to explicitly granted users off so public accounts can review.

Verify the saved rules on both branches. See [GitHub’s bypass settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#granting-bypass-permissions-for-your-branch-or-tag-ruleset). If a token cannot edit Administration settings, configure them in GitHub yourself; pushing source files does not install these settings.

## Review automation

`Staging peer-review gate` counts current-head public approvals. Its count is advisory: fewer than two approvals does not fail the check or prevent the owner's merge. Author reviews, bots, dismissed or stale approvals do not count. A later submitted review replaces that account's previous review. No reviewer allowlist or repository role is required.

`Update reviewed translations queue` executes trusted tools from `main` and only adds or removes its advisory label. It independently checks translation JSON and synchronized CSV, immutable metadata, code changes, file modes and current reviews. Code, workflow, recipe and credits PRs do not receive this label. Wrong-base, draft, closed or changed proposals lose it. Failed validation/review runs also refresh the queue; manual and daily scans cover missed events. The label does not certify translation accuracy or replace checking CI.

The queue job has Contents read, Issues read for suggestion checks and Pull requests write permission for labels. It has no merge operation, Contents write permission, personal token or Actions write permission. Keep the default branch as `main`. Approve outside-contributor workflow runs only after inspecting their diff; candidate code is never executed by translation validation.

## Import one issue suggestion

For a short walkthrough, see [Accept a website suggestion](REVIEW_SUGGESTIONS.md). The steps below cover the importer in more detail.

Contributors use **Suggest on GitHub** in the browser, then submit the prepared issue. The local importer supports one record from a field batch, the opening scene, battle dialogue or an image-label batch. It does not run from the issue or publish anything automatically.

Start from a clean checkout with current `origin/staging`, then make a branch for this issue:

```sh
git fetch origin
git switch -c codex/issue-123 origin/staging
```

The importer refuses to apply on `main` and does not create a branch for you. Read the issue and preview it first, using the Python interpreter from your project environment:

```sh
python tools/import_issue.py 123
```

The preview fetches the issue from GitHub, verifies its creator account and compares the record with the current canonical files. A username claimed in the body is not used for credit. Check the proposed wording against the Japanese from your own legally obtained, matching original ROM.

To validate the fit and apply an accepted suggestion locally:

```sh
python tools/import_issue.py 123 --rom "C:/Games/original.nds" --apply
```

This uses your ROM locally; it is not uploaded. Validation rejects stale record hashes, invalid page or part structure, text that does not fit, unchanged wording and an issue already imported. Fix a stale suggestion with its contributor rather than silently applying it to a different record.

The apply step updates the canonical English, matching CSV where the batch uses one, `credits/issue_imports.json` and `TRANSLATORS.md`. It does not commit, push, merge or close the issue. Review `git diff`, run the relevant checks, commit to your review branch and open a PR to `staging`. Recheck the issue's wording before merging: a later issue edit may not rerun a passed check. Only the owner merges it and later promotes the accepted changes to `main`. Close the issue with a publication link after the change reaches the published version.

GitHub checks the import data and issue provenance without a game file. The local `--apply` command checks the ROM layout and fit; never upload a ROM to CI.

Issue imports include their credit ledger, so keep them separate from ordinary contributor JSON/CSV-only PRs. Review them as maintainer changes; two public approvals cannot publish an import or bypass owner review.

## Publication and credits

Review and test staging, then open a same-repository `staging` → `main` PR when ready. `validate_promotion.py` accepts translation data and append-only credits. Only you merge the promotion. Test tooling changes separately and synchronize them into staging without overwriting contributions.

The published editor may contain older batches than staging. Contributors should compare **Files changed** and carry over only their own edits if an exported batch is stale.

`credits/merged_prs.json` records merged staging PRs, immutable base/head revisions and measured English changes; `python tools/credits.py` renders `TRANSLATORS.md`. Optional credits automation runs after a staging push when `CREDITS_AUTOMATION_ENABLED=true`, using a dedicated repository-scoped App with Contents and Pull requests write permission. It proposes a separate credits PR; it never merges it. Without that App, prepare a credits PR using the same verified GitHub data. The credits check recomputes every new entry remotely before accepting it.

The translators page combines accepted issue imports with merged translation PRs. `credits/issue_imports.json` records verified issue accounts and accepted record changes; `credits/merged_prs.json` records the PR route. Each accepted record links back to its issue or PR. A later maintainer PR importing an issue does not earn the same text credit again.

Newly filled entries and revisions are shown separately, with word and character counts. Unique record IDs are counted per contributor, not files. Notes, unchanged wording, layout-only changes, deleted English and code changes earn no text count. Revision totals describe the accepted passage and may overlap earlier contributions; they do not claim that the submitting account wrote every word. Word counts keep internal apostrophes together; characters exclude whitespace.

Keep `PAGES_PUBLISHING_ENABLED` off for this two-repository arrangement. The source workflow still builds and audits the editor. Follow [Two repositories](TWO_REPOSITORIES.md) to copy it to the website repository. `TRANSLATION_EXPORTS_ENABLED=true` enables English-only exports from main. Public Actions never receive a ROM or build a playable game.

## Other settings

| Setting | Recommended value |
| --- | --- |
| Actions default permissions | Read contents; grant writes only to jobs that need them |
| Fork workflow approvals | Require approval for all outside contributors |
| Actions creating/approving PRs | Off; optional credits use their own narrow App |
| Secret scanning and push protection | On where available; inspect alerts |
| Dependabot alerts and security updates | On; review dependency changes as owner tooling changes |
| Private vulnerability reporting | On for both repositories |
| Website Pages | Branch main, root folder, HTTPS enforced |

## Check an update

```sh
python -m pip install -r requirements.txt
python tools/verify.py --out ../verification-run
```

Use a new private output folder. The verifier needs Git, Node.js 22 or newer and the Python dependencies. It checks translation pairs, regressions, publication outputs and reproducible source ZIPs. GitHub repeats game-free checks on Windows and Ubuntu with Python 3.11 and 3.13. Inspect the actual results after pushing. Code and dependency PRs are deliberately outside the ordinary translation route; test them separately as owner changes.

A clean current tree does not remove old files from Git history or establish legal permission. See [Testing](TESTING.md) and [Publishing](PUBLISHING.md).

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).
