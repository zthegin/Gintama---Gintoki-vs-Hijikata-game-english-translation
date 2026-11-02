# Resolving the field research queue

This is an unofficial fan project. Use your own legally obtained ROM and keep original game files local. See [RIGHTS.md](../RIGHTS.md).

## Native glyph order

The stock font contains 6,953 records. Enumerating valid two-byte CP932 pairs in byte order and removing duplicate Unicode characters produces exactly that many entries. It agrees with 1,401 of the previous 1,404 character mappings. The three discrepancies and 24 frequent missing characters were checked against the original font bitmaps locally. The corrected readings are at codes `0x0512`, `0x05F2` and `0x07D3`.

`tools/font_encoding.py` reconstructs the character map using Python's standard codec. No original font records or bitmap samples are distributed. This corrects decoding; it does not automatically revise existing English translations.

## Standalone controls

The original ARM9 dispatcher consumes `FF83`, `FFA1`, `FFA2`, `FFA3`, `FFA5`, `FFB1` and `FFB2` as single words with no following operand. The FFA commands adjust character delay; FFB1/FFB2 set countdowns. FF83 is preserved as a native formatting selector without assigning an unverified color name.

English retains these controls as explicit tags such as `[ctrl:FFA3]`. The exact source control and page order must remain unchanged. Unknown tags are rejected. Ordinary red/blue markup remains balanced; a source line with unusual flat color transitions uses explicit native color tags instead.

## Short choice and UI strings

The old scanner read 86 NUL-terminated strings as though they continued to a later END word. Each actual starting offset has a matching string-load operand in the original CDB. The corrected index hashes only the short string, including its NUL terminator. The writer preserves that terminator at its original position and checks that adjacent bytes remain unchanged.

Three dynamic prefixes have a trailing red selector. That selector stays outside the editable English and at the same absolute position. It is included in the source hash. `reference/field_record_migrations.json` records the old and corrected hashes without source text or game bytes. Old extraction ZIPs with the overlong hashes are intentionally rejected; use a current ROM in the browser or `tools/local_view.py --msb` for a private preview.

This resolves the existing indexed research records. It does not establish that every choice label or dialogue string in the game has an individual index entry. Additional CDB-referenced choice labels remain a separate inventory task. Offline structural checks also do not replace in-game playtesting.
