# Reading source text

The browser editor reads Japanese dialogue from your own legally obtained, matching `.nds` or extracted `.msb`. Select the file, then choose a batch. Unknown glyphs and controls appear as markers. Game bytes stay local. See [editor help](BROWSER_EDITOR.md).

The public JSON and CSV contain editable English, IDs and hashes, not the original Japanese script:

| File | Purpose |
| --- | --- |
| `translations/ready/batch_0001.json` | Editable batch |
| `csv/ready/batch_0001.csv` | Spreadsheet view of the same batch |
| `reference/record_index.json` | Source IDs, offsets, hashes and decode status |

```sh
python tools/lookup.py --id msb_00000254
python tools/lookup.py --contains "Gin Tama"
python tools/progress.py
```

## Private previews

If you already have a private extraction ZIP containing `all_records.json`, build a Japanese/English view outside the repository:

```powershell
py -3 tools/local_view.py --extraction "..\private-extraction.zip" --batch translations/ready/batch_0001.json --out "..\private-batch.html" --format html
```

Use `--format csv` or `--format md` with a matching output extension for other views. These previews include source text and extra fields. They are not public contribution files. Copy your English edits into the public batch and synchronize its JSON/CSV pair.

## Extracting local assets

`extract_text.py` reads source assets without modifying them. It also needs private source-name decoding tables and their glossary, either in a ZIP or as `source_name_tables.json` beside `glossary.json`. These are research inputs, not supplied game content. For most contributors the browser editor is easier.

```powershell
py -3 extract_text.py --msb "..\root\field\script\fld_scr.msb" --cdb "..\root\field\script\fld_scr.cdb" --tables "..\source_tables.zip" --out "..\private-extraction"
```

`--existing` optionally imports a previous translation database after checking its source spans. Choose a new output folder for each extraction; an existing folder or ZIP is refused. The output includes `all_records.json`, review lists and a ZIP. Keep all of it private. Unresolved glyphs require manual decoding; source-file order does not prove gameplay order, and an extracted draft does not prove in-game fit.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).
