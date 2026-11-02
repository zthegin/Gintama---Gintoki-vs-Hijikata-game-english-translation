# Field batches

Every currently indexed field record has an editable template. This measures the index, not every possible game string. Battle and opening scripts use separate workflows.

There are 114 numbered editable batches: `0001-0089` and `0115-0139`. Earlier batch IDs remain stable. The former research batches `0090-0114` were replaced after verified glyph, control and string-boundary research. See [the evidence and limits](FIELD_RESEARCH.md).

The 22,480 indexed field records include 20,066 translated entries. Of the 114 numbered batches, 101 are complete. Adding templates does not translate their text. The source index may still omit other choice labels or dialogue strings.

## Translate a batch

Use the [browser editor](BROWSER_EDITOR.md), or edit the English column in its CSV. JSON files are in `translations/ready/`; matching CSV files are in `csv/ready/`. Select your own legally obtained, matching ROM locally to read the Japanese. Do not upload game files. Follow the normal [contribution guide](../CONTRIBUTING.md).

Keep source IDs, hashes, page breaks and native control tags unchanged. Tags such as `[ctrl:FFA3]` preserve verified rendering commands; do not remove them or invent new tags. Explicit native color tags preserve one unusual source formatting sequence. Three dynamic UI prefixes also have an immutable trailing color selector which the writer preserves automatically.

`reference/field_batch_coverage.json` assigns every originally unbatched record. Exact duplicates link to an existing message by full source hash. Check the target source and layout before reusing its English. Null-terminated choice/UI prefixes use corrected short hashes; old extraction ZIPs with overlong spans are rejected. Read the current source through the browser or `tools/local_view.py --msb`.

Templates contain functional metadata, not original Japanese dialogue or binary resources. This remains an unofficial fan project; see [RIGHTS.md](../RIGHTS.md). Offline verification does not replace in-game playtesting.
