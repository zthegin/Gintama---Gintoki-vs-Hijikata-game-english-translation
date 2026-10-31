# Project and website repositories

- [Project source](https://github.com/zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation): tools, documentation, translation templates, contribution issues and pull requests.
- [Website repository](https://github.com/zthegin/zthegin.github.io): generated website files only.
- [Public website](https://zthegin.github.io/): available after Pages is enabled and its deployment succeeds.

## Source repository

Upload the contents of `gintama-community-translation`, including its hidden `.github`, `.gitignore` and `.gitattributes` entries, to the project repository root. Do not upload the outer working folder, private QA directory, ZIP archives, game files or private research. Create `staging` and configure owner-only update rules for both branches as described in [Maintainer setup](MAINTAINER_SETUP.md).

Leave `PAGES_PUBLISHING_ENABLED` unset in the project repository if the website will be served from the separate website repository. The supplied source workflow otherwise deploys a project site in its own repository; it does not synchronize a second repository. Approved export publication is independently opt-in.

## Build the website

From the source folder:

```sh
python tools/build_web.py --out ../website-build --repository zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation
```

The explicit repository argument ensures that Suggest on GitHub opens a contribution in the project repository, even when building in another GitHub workflow. It accepts an `owner/name` identifier, not a URL. The default for a local build is the project repository above; `GITHUB_REPOSITORY` may supply a workflow default.

Copy only the contents of the audited website build into the root of `zthegin.github.io`. Include `assets`, `screenshots`, the license and rights files, and `.nojekyll`. Do not copy source translation folders, private logs, game files or a second complete source repository there. The prepared website ZIP already adds a site-specific `.gitignore` and a README linking back to the project.

In the website repository, select **Settings > Pages > Deploy from a branch**, branch `main`, folder `/ (root)`. GitHub then builds the static files using its Pages deployment. No cross-repository write token or synchronization bot is required for this manual update process. When refreshing an existing website, review deleted as well as changed files so stale output is removed.

## Check the first deployment

Open the public website, check the footer links, select your own legally obtained matching ROM and edit one entry locally. Test both exports, then check that a suggestion targets the project repository. No game file should be uploaded. The live Pages address and GitHub settings are not verified merely by building the ZIP.

Keep both `.gitignore` files. They prevent accidental staging; they do not remove tracked files or history, and `git add -f` can bypass them. The publication audit remains a separate required check. The website `.gitignore` permits only the three reviewed editor captures.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).

The website repository also runs an independent publication audit on pushes and pull requests. It checks out a reviewed source commit by its full SHA and uses its read-only auditor; it never runs scripts supplied by a website PR. Refresh that pin only after testing the source revision. Keep the website's `.github` workflow when copying generated pages. The audit reports failures; it does not replace branch protections or gate the separate Pages deployment. No ROM is used by either repository's CI.
