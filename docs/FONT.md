# English font

The UI builder appends the same English bank to DFGB12 and DFGB10, preserving all 6,953 original records.

| Characters | Codes |
| --- | --- |
| a–z | 6954–6979, unchanged |
| A–Z | 6980–7005 |
| ? | 7006 |
| . | 7007 |
| English space | 7008, three-pixel advance |
| , | 7009 |
| ! | 7010 |

The capitals are seven pixels tall and share the lowercase baseline. Edit their rows and advances in `graphics/extended_font.json`. This is original project lettering; game font records are read from your legally obtained matching ROM.

`tools/english_font.py` packs the records. The UI text encoder and sign renderer use the new codes. English word spaces use the appended blank record. Native code 1 stays unchanged for fixed-slot padding; commas and exclamation marks use matching project-created glyphs. Other baked graphics keep their existing lettering. Rebuild using the normal installation command.

Dialogue writers must use this mapping and respect the existing message and page limits. Fixed-size dialogue insertion does not support arbitrary script growth or alter the browser's separate 4×7 image-label alphabet.

All 57 English glyphs leave a blank column after their ink. This protects the right edge of packed dialogue tiles without changing letter advances or removing strokes. Both font sizes pass pixel-decoding, record-preservation and ROM/patch checks. An earlier DFGB12 bank passed fourteen real melonDS captures covering every capital, question marks and periods; this alignment change still needs an in-game visual check. DFGB10 has not been checked separately in-game. Offline previews are labelled as such.

Oversized field lines can use the same packed-letter technique as the cutscene writer. Page controls stay separate, and the script keeps its original byte size. The four scripted menu/reward labels are hash-checked separately, preserving colour controls and null terminators.

The normal builder now inserts bundled English dialogue through `tools/dialogue_writer.py`. It preserves original message sizes, END positions, separators, CDB bytes and all original font records. Field colors use `[blue]text[/color]` or `[red]text[/color]`; keep the source colors in the same order and on the same pages. Extra colors, oversized text, changed page counts and other complex inline controls are rejected. All 128 speaker nameplates use an unscaled seven-pixel capital alphabet with a thin, opaque dark outline and the existing palettes. Names are never shrunk to fit. Dialogue uses three-pixel word spaces for clearer separation.

The opening cutscene uses `tools/cutscene_writer.py` and `reference/opening_scene.json`. It packs adjacent English letters into appended records using the existing letter pixels and advances. This fits natural English without moving message END positions or changing the CDB. Formatting controls retain their order; their positions within a message can move. All original font records remain intact.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).

Battle dialogue uses the same English pixels and cluster packing. `tools/battle_writer.py` reads the four-byte battle header, verifies supported records against `reference/battle.json` and preserves the original CDB bytecode and message END positions. The opening reader keeps its existing minimum offset; battle offset 4 is enabled only by the battle workflow.
