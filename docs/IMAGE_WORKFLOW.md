# Translating graphics and UI

The full local builder reproduces **649 graphical variants and 122 native UI text slots** from the supported original ROM. The browser editor handles the 193 Gin Tama name images; the other formats use the checked recipes in `graphics/ui_recipes.json`. No extracted artwork, native font records or palettes are bundled.

## Full UI build

```sh
python -m pip install -r requirements.txt
python tools/build_ui.py --rom "/path/to/original.nds" --validate-only
python tools/build_ui.py --rom "/path/to/original.nds" --out local/gintama-ui.nds --patch local/gintama-ui.bps
```

Use your own legally obtained, matching ROM. Both outputs are optional individually. Builds refuse existing paths and preserve the original ROM. The patch is applied with `tools/rom_patch.py`; see [installation](APPLY_PATCH.md).

The builder reads the original graphics, palettes and Latin glyphs from that ROM. It adds the project-created English alphabet while retaining every native font record. It rebuilds verified tilemaps, draws within reviewed text regions, checks compressed capacities and writes fixed-size UI text slots. The normal build also applies the bundled dialogue. It preserves message END positions and CDB bytes; add `--ui-only` to leave the dialogue MSB files unchanged.

`graphics/ui_recipes.json` contains English wording, source hashes, geometry and source-slot metadata. It includes menu graphics, two signs, nameplates, place names, chapter cards, item labels and UI text. You can edit English fields in a local copy and pass `--recipes`. Changes to recipes or tooling need maintainer review; ordinary translation PRs still use the existing JSON/CSV batches.

Variants include selected/unselected and packed/loose copies. The total is not a whole-game translation percentage. Unresolved names and unhandled screens remain Japanese. Offline checks establish placement and data integrity; they do not verify every screen in-game.

## Browser

Open **Images** on the project website. Supply your own legally obtained matching original ROM to see the source image and palette. The ROM stays in the browser tab. Edit the English label and an optional note; the editor checks the pixel width, line count and original compressed capacity. One or two lines fit. Review both native-size and enlarged previews.

Export JSON and CSV. Replace `translations/graphics/gin_tama_names.json` and `csv/graphics/gin_tama_names.csv` together, then open a PR to `staging`. Do not submit an image. Two current account approvals can mark image translation PRs for owner review too; the maintainer records contributor credits from merged PRs. Full terminology is in the English glossary; fitted display labels may be shorter, but must preserve meaning.

## Python 3

Only the standard library is required. Run from the repository folder:

```sh
python tools/image_workflow.py inspect --rom "/path/to/original.nds" --out local/image-review
python tools/image_workflow.py build --rom "/path/to/original.nds" --validate-only
python tools/image_workflow.py build --rom "/path/to/original.nds" --out local/images-english.nds
```

On Windows, `py -3` can replace `python`. Quote paths with spaces. Each output path must be new. The legally obtained original ROM is never overwritten. `inspect` creates local source/English PNGs and a private report; do not publish those files. `--validate-only` writes no ROM or previews.

Use `--translations /path/to/gin_tama_names.json` to build an exported batch. Use `--base-rom /path/to/existing-translation.nds` to add these image edits to an existing compatible translated copy of your legally obtained ROM. The tool verifies the clean source separately, resolves both filesystems and protects all base-ROM bytes outside the selected image container. The base container must still have the original primary pictures, palette and unedited regions. Fonts, script files and FAT entries are not edited by this image step.

The workflow does not require the private project or its fonts. The public pixel alphabet is project-created lettering. Source art and palettes are read from the user's legally obtained ROM. Each source image is hash-checked; original and edited OBJ pixels roundtrip; new streams use backreferences of distance at least two and are decoded through both ordinary byte and DS-style halfword paths. The output keeps the original slot sizes and container layout. A decoded preview establishes placement and compression, not actual game-screen verification.

## Metadata and new formats

`graphics/catalog.json` contains IDs, source hashes, offsets, capacities, geometry, palette location, English terminology and background choices. It contains no original pixels, palette values, font records or Japanese text. `source_words_sha256` retains the existing batch schema name; for graphics it hashes the **decompressed 512-byte image**, not script words. The record index marks these entries as `kind: graphic`.

Ordinary translation PRs cannot change that metadata, code or the pixel alphabet. A maintainer must separately review new formats and source fingerprints. Add a lossless source roundtrip, protected-region checks, an edited decode, size guards and synthetic tests before enabling a new asset family. Never guess tile order or reuse an unrelated palette merely because a preview looks plausible.

The ordinary English text exporter keeps image translations separate in `gin_tama_names.json`. Image builds can be packaged with the existing local BPS tools, but a ROM-free patch is not automatically rights-cleared. Read [the rights policy](../RIGHTS.md) before distributing a build.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).
