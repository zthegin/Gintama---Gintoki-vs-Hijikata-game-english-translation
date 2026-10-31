# Building a patch

Keep your legally obtained original ROM and all local builds private. For the full graphics/UI build and its `--patch` option, use [the installation guide](APPLY_PATCH.md).

## Package a tested build

Once a local builder has produced a translated copy that you have checked in-game:

```powershell
py -3 tools/rom_patch.py create --source "C:\Games\original.nds" --target "C:\Games\translated.nds" --patch "local/translation.bps" --scope "tested build"
py -3 tools/rom_patch.py apply --source "C:\Games\original.nds" --patch "local/translation.bps" --manifest "local/translation.json" --output "local/roundtrip.nds"
py -3 tools/pack_patch.py --patch "local/translation.bps" --manifest "local/translation.json" --output "local/translation-kit.zip"
```

Compare `roundtrip.nds` with the translated build. The six-file kit contains the patch, manifest, applier, guide, LICENSE and RIGHTS.md. Existing output ZIPs are never overwritten.

The encoder uses BPS SourceRead and TargetRead actions. The included decoder supports patches created by this project, not every BPS variant. A patch can contain original game bytes; inspect its payload and resolve distribution rights before sharing it. See [RIGHTS.md](../RIGHTS.md).

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).
