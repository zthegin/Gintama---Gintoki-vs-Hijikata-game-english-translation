# Local playtesting

Use your own legally obtained, matching ROM and keep the original unchanged. Back up saves before testing a rebuilt copy.

## Graphics and UI

Follow [the UI build instructions](APPLY_PATCH.md). Check edited labels in the corresponding game screens, including selected and unselected states. Look for clipping, palette errors and unreadable letters. The browser preview checks layout and compressed size, but cannot replace those in-game checks.

## Dialogue

The public builder now applies bundled fixed-size dialogue translations as well as UI graphics. It reads the original font and script data from your legally obtained ROM, so the private research scripts are not needed. See [installation](APPLY_PATCH.md) for the normal build and testing a downloaded JSON batch.

The normal builder accepts downloaded dialogue batches with `--dialogue`. It checks their original fixed-size slots and refuses text that does not fit. Full-game insertion still needs further allocation and layout work. The bundled opening cutscene has offline integrity checks; the first three opening messages have been checked in melonDS, while later pages still need playtesting.

## Reviewed text

```sh
python tools/export_approved.py --repo . --out ../approved-export
```

This exports English JSON/CSV and image tools, not a playable game. Keep local builds, screenshots and source assets out of public submissions. Report issues with entry IDs and a short description instead.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).
