# Field batches

The numbered batches cover editable field records, not every line of the game. Battle and opening scripts have separate workflows.

- `translations/ready/batch_0072.json` through `batch_0089.json`: 3,443 newly available records in 18 editable batches. Their CSV views are in `csv/ready/`.
- `review/field/batch_0090.json` through `batch_0114.json`: 4,814 records in 25 research batches. These are not ready for translation or patching and do not appear in the editor.
- `reference/field_batch_coverage.json`: the assignment of every previously unbatched record, its review blockers and any exact match to an existing translated entry.

All new English fields start empty. Creating a template does not count as translating it. The 71 earlier numbered batches and their English remain unchanged. There are now 89 editable numbered batches, with 71 complete.

## Translate an editable batch

Use the [browser editor](BROWSER_EDITOR.md), or edit the English column in its CSV. Select your own legally obtained, matching ROM locally to read the Japanese. Do not upload the ROM or extracted game files. Follow the normal [contribution guide](../CONTRIBUTING.md); keep source IDs, hashes, page breaks and color controls unchanged.

Some new entries repeat an already translated message exactly. The coverage file links these by full source hash. Check the target source and layout before reusing its English. No translations have been copied automatically.

## Research batches

Review records contain unresolved glyphs, unsupported script controls, or both. Their source hashes and IDs are retained for local investigation. The review format is deliberately different from editable batches. Do not copy these files into `translations/ready/` or submit their entries through the normal editor until their source and writer support have been verified.

The coverage test checks that every indexed field record is assigned once across the editable and review queues. It does not establish that every indexed record is shown during gameplay. Templates contain functional metadata, not original Japanese dialogue or binary resources. This remains an unofficial fan project; see [RIGHTS.md](../RIGHTS.md).
