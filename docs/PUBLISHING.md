# Publishing

Run `python tools/verify.py --out ../verification-run` from a clean source copy. Inspect `verification.json` and the exact source ZIP. Use the source packager rather than archiving a research directory. It generates a fresh checksum manifest inside each ZIP; no old manifest is kept in the repository.

Keep ROMs, source assets, game captures, saves and private logs out of both repositories. The three editor captures listed in `docs/screenshots/PROVENANCE.json` are the only image exceptions, checked against exact hashes. Review any existing Git history, releases, Pages deployments and Actions artifacts separately; the local audit checks the current package only. The project and game's rights are described in [RIGHTS.md](../RIGHTS.md).

## Website

For the separate website repository, upload only the built site and follow [two-repository setup](TWO_REPOSITORIES.md).

To deploy from the source repository instead, select **Settings → Pages → GitHub Actions**. Set `PAGES_PUBLISHING_ENABLED=true` only after reviewing the site. Build checks run without this variable; the deploy job alone receives Pages and identity-token write permissions. Where available, require reviewers and restrict the `github-pages` environment to `main`.

Removing that variable stops future deployments. To remove an existing site, unpublish it in Pages settings too.

## Exports and patches

`TRANSLATION_EXPORTS_ENABLED=true` enables the approved-export workflow. Review the exported material and its publication rights first. Patch building remains local, with no automatic upload. A patch can contain protected bytes even when it contains no full ROM.

## Rights concerns

Pause the affected publication while reviewing the specific files. Keep notices and records private, follow the host's deadlines, and check releases and the deployed site as well. Removing a file does not settle claims about earlier distribution. See [GitHub's procedure](https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy) for formal notices.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).
