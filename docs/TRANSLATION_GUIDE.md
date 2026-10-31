# Translation guide

## Get the Japanese text locally

Start with the website's Dialogue editor and your own legally obtained, matching game file; it decodes the source locally. The public repository excludes the Japanese script. Follow [the beginner tutorial](START_HERE.md) for editing and submission. Private extraction tools are an optional advanced route described in [Text access](TEXT_ACCESS.md); that route needs private decoding tables or an existing extraction. Check the scene in-game where possible: neighboring MSB records are not always neighboring dialogue.

## Find a record

Open a batch in `translations/ready/` or `csv/ready/`. The `id` and `source_words_sha256` identify the source entry; don't change either. `english: null` marks an untranslated line. The `field_dialogue.json` batch includes the bundled field-dialogue examples; its remaining entries are untranslated.

## Write the English

Aim for spoken English, not a word-for-word gloss. Keep jokes, deliberate misnamings, levels of politeness and character voices. Leave `translator_note` blank unless it explains a joke, an abbreviation or an uncertain reading. Put shared scene context on its first row rather than copying it to every line. The build checks page counts and slot limits, so notes do not need to repeat those rules. Check `reference/glossary.json` before settling on a name: **Gin Tama** refers to the collectibles and **Gintama** to the series. The Dragon Balls joke is separate.

For example, an English field can contain:

```json
"english": "Did someone take my pudding again?"
```

Use `\n` for a line break and `\f` for a page break in the JSON source. Keep the original number of page breaks. Don't shorten a natural-language draft simply to fit a game text slot; that comes during patch testing.

## Using CSV

The CSV has four columns: `id`, `source_words_sha256`, `english`, `translator_note`. Keep the columns and record order, including an empty `translator_note` column when there is no note. Do not add comment rows above the header. Write literal `\n` or `\f` inside a cell, then save as UTF-8 comma-separated CSV. Do not commit `.xlsx` files.

If you changed CSV, import it into JSON:

```sh
python3 tools/sync_csv.py --from csv --batch batch_0001
```

If you changed JSON, refresh the CSV:

```sh
python3 tools/sync_csv.py --from json --batch batch_0001
```

## Check and submit

```sh
python3 tools/sync_csv.py --from json --check
python3 -m unittest discover -s tests -v
```

Open a PR against `staging` with both synchronized files. Include the scene, any uncertain readings and anything you'd like reviewers to check. A translation PR must change English text; note-only or formatting-only submissions are not accepted as translation PRs.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).
