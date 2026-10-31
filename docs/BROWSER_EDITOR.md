# Browser editor

For the complete beginner walkthrough, read [How to contribute](START_HERE.md). For applying a release or building image edits on your own legally obtained ROM, read [Installation](APPLY_PATCH.md).

The website has Dialogue, Opening, Battle and Images pages. It works without installation when GitHub Pages is deployed. It is a static site with no account system, analytics, external fonts or game-file uploads. Suggest on GitHub opens a prepared issue only when you choose that action; you review and submit it yourself. If the popup is blocked, use the prepared-suggestion link shown below the button.

## Local source files and drafts

Choose your own legally obtained matching, unmodified `.nds` game file. Dialogue also accepts a matching extracted `fld_scr.msb` from that legally obtained ROM. The browser reads bytes locally, verifies SHA-256 and record hashes, then shows Japanese or source images. The website does not include the original script, game font or game palettes.

English and notes are stored in that browser, keyed by game hash and record ID. Source bytes and Japanese are not retained. Select your legally obtained game file again after a reload. Download both JSON and CSV before closing the editor or clearing browser data. Drafts do not move between browsers or devices. If storage is unavailable, your edits stay in the open tab until you export them.

## Submission and testing

For one record, use **Suggest on GitHub** from Dialogue, Opening, Battle or Images. Sign in, check the English and note in the prepared issue, then submit it. The issue identifies the record and the version you edited; do not change those details. A maintainer reviews the suggestion, checks it against the current files and validates its fit locally before accepting it. It does not merge or publish itself.

Accepted suggestions are credited to the issue's actual GitHub account, with a record link in [Translators](../TRANSLATORS.md). Remove private paths and contact details before submitting: issues are public. Keep game files, original Japanese dumps and captures private.

For a field-dialogue or image-label batch, upload both matching JSON and CSV files to a branch of your GitHub fork, then open a PR to upstream `staging`. Leave IDs, hashes and order unchanged. Two current account approvals mark valid translation edits for owner review. The owner merges manually. See the [beginner guide](START_HERE.md) for each GitHub step.

The Images editor covers 193 Gin Tama name labels. The small name-label builder uses the standard library; the [full UI builder](APPLY_PATCH.md) adds the broader 649-variant/122-slot translation and needs the rendering packages. The normal builder applies the bundled English dialogue and opening cutscene. To test a downloaded dialogue JSON batch, use `--dialogue` as shown in [installation](APPLY_PATCH.md#apply-your-own-dialogue-edits). Each dialogue page needs text and must keep its original page count. The editor checks page breaks and submission rules; the Python build checks the font, line wrapping and fixed-size slot. If that build says the text is too long, shorten it in the editor and download both files again. Most later dialogue remains untranslated.

## Opening cutscene

Open [Opening](https://zthegin.github.io/cutscenes.html) and select your own legally obtained original ROM to read the source. This page covers indexed entries in the `s01` script, including the Yorozuya opening and Hijikata introduction. See [current progress](../README.md#current-progress) for the entry count. Other cutscenes are not indexed here yet.

Each message has one or more English parts. Keep their order and count: those boundaries preserve the game's formatting controls. You only edit the words. Some source characters are still unmapped and appear as explicit glyph codes; check those in your own game before translating rather than guessing.

Use **Suggest on GitHub** for one English-only record. For several edits, download the opening JSON, test it with `--cutscene`, then replace `reference/opening_scene.json` in a branch of your fork and open a PR to `staging`. Load your own original ROM to reveal supported untranslated s01 entries. Keep existing entries and all source metadata. CI checks added entries against a trusted offset/hash/part-count index; it does not receive your ROM. The local Python build checks bubble width, controls and fixed-size slots. A browser export alone does not prove that it fits. Other cutscene scripts remain unsupported.

The field and image editors have been tested with private source files, exports, persistence and privacy checks. The opening editor also has record-hash, part-boundary and export tests. These checks do not replace checking the wording in the game. See [testing](TESTING.md).

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).

## Battle dialogue (no code)

Open [Battle](https://zthegin.github.io/battle.html), choose a script and select your own legally obtained original ROM. Choose an entry, write the English and click **Suggest on GitHub**. The Japanese is decoded locally and is never included in the issue or downloaded JSON. Unknown glyphs are marked, so check those in your own game before translating.

The editor supports END-terminated messages in 90 battle scripts. Records with embedded tables or page controls, and trailing null-terminated labels, remain unchanged. A script's entry count includes untranslated records and repeated variants; it is not a translation percentage.

Download `battle_translations.json` to try several edits locally with `--battle`. It contains the selected script. For a batch PR, merge that script's exported messages into `reference/battle.json`, keeping every other script, existing entry and source field. Open the PR to `staging`; trusted checks verify each record against the source index. No CSV accompanies opening or battle packs. For one no-code suggestion, **Suggest on GitHub** remains the easier route. Only the owner merges.
