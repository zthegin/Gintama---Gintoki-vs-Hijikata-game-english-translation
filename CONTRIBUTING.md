# Contributing

The repository was recreated on 31 October 2026. If you cloned before that date, save your work privately and make a fresh clone. Copy over only your intended edits; do not merge or push the old history.

You can help translate without writing code. The easiest route is [one suggestion in the editor](docs/START_HERE.md#suggest-one-dialogue-line). Choose your legally obtained original ROM, edit a record, then use **Suggest on GitHub**. Sign in, check the prepared issue and submit it. No Python, Git, fork or file upload is needed.

Dialogue, opening-cutscene, battle and image-label suggestions each cover one record. A maintainer reviews the wording and validates the edit locally before accepting it. An issue is a suggestion, not an automatic change to the game.

For several field-dialogue lines or image labels, export both JSON and CSV and open a pull request to **staging**. See the [batch walkthrough](docs/START_HERE.md#submit-a-batch-or-image-label).

## What to change

Edit `english` and, if needed, `translator_note`. Keep IDs, hashes, record order and page counts unchanged. Retain **Yorozuya** and **Gin Tama**; check the [translation notes](docs/TRANSLATION_GUIDE.md) for names and character voice.

If you edit files directly, synchronize the other format:

```sh
python tools/sync_csv.py --from json --batch batch_0001
```

Use `--from csv` for CSV edits, or replace the batch name with `gin_tama_names` for image labels. Submit both resulting files. The [testing guide](docs/TESTING.md) covers local checks and their dependencies.

## Review and credit

Anyone with a GitHub account may review a translation PR; no reviewer list or repository role is needed. Two other accounts approving the current revision add a `reviewed-translation` label after the translation-only checks. This puts it in the [reviewed queue](https://github.com/zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation/pulls?q=is%3Apr+is%3Aopen+base%3Astaging+label%3Areviewed-translation+sort%3Aupdated-desc) for the owner's attention. It does not reorder GitHub's default list or merge anything.

Only `zthegin` merges into `staging` and `main`. The owner still checks the wording, diff and test results. Update the same branch when changes are requested; new commits need fresh approvals. Author reviews, bots, duplicate accounts, old approvals and comments do not count toward the label. Two accounts are not proof of two different people.

The [translators page](TRANSLATORS.md) counts accepted issue suggestions and merged translation PRs, including entries, words and characters added or revised. Issue credit uses the account that actually opened the issue, verified through GitHub; a name written in the issue body is not proof of identity. Accepted records link back to their issue or PR. You do not need to edit the credits files yourself.

New entries and revisions are counted separately. Counts describe the accepted wording, not sole authorship of every word; a revision may include words from earlier contributors. An imported issue is not counted again as a new translation when its maintainer PR merges. The maintainer reviews the import and publishes it through the normal staging/main process. The issue stays open until the accepted change is published. Optional PR credits automation only proposes a separate PR for owner review.

Keep code, workflow and graphics-recipe changes in separate maintainer-reviewed PRs. Ordinary translation PRs accept only English/note changes and their matching CSV files.

## Before your first Git commit

Use a repository-local GitHub noreply email if you want to keep your email private. A fresh clone can inherit your global Git identity. See [setting your commit email](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address) and [blocking pushes that expose a private email](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/blocking-command-line-pushes-that-expose-your-personal-email-address). Issue suggestions are public under your GitHub account; remove private paths and contact details before submitting.

## Contribution terms

The maintainer does not own Gintama or any original game content. All game rights remain with their respective holders. Share only material you have the rights to contribute. Code and original documentation use [Apache 2.0](LICENSE); the game's rights are separate. Use your legally obtained ROM locally and keep game files, source dumps and game captures out of submissions. See [RIGHTS.md](RIGHTS.md). Report security issues as described in [SECURITY.md](SECURITY.md).

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](RIGHTS.md).
