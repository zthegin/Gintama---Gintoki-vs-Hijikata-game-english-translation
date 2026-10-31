# Install the translation

You do not need to write or edit code. Copy the commands below and replace the example ROM path with yours.

Use Python 3.13 and your own legally obtained, unmodified ROM of the supported revision. Python 3.11 is also tested. No ROM or game resource pack is included.

If you downloaded a patch kit rather than the source project, skip to [Apply an existing patch](#apply-an-existing-patch).

## Before you build

- Supply your own ROM that you are legally entitled to use and modify where you live. The project does not supply game files, ROM-site links or help finding unauthorized copies. If you are unsure about permission, check before proceeding.
- A matching checksum confirms the supported revision. It does not prove that a file was legally obtained or grant rights to modify or distribute the game.
- Back up the original ROM and saves. Build to a new filename, and keep the rebuilt ROM on your own device.
- Do not attach ROMs, rebuilt games, extracted assets or saves to issues and pull requests, even as bug reports. Use entry IDs and a short error description with private paths removed.

See [rights and project limits](../RIGHTS.md). These requirements do not grant rights to the game or its translation.

## Install Python on Windows

1. Get the **Python Install Manager** from [python.org](https://www.python.org/downloads/) and install it. The [official Windows guide](https://docs.python.org/3/using/windows.html) explains the screens.
2. Open PowerShell from the Start menu and run `py install 3.13`. If an older launcher treats `install` as a filename, use `pymanager install 3.13` instead.
3. Run `py -3.13 --version`. Continue when it prints `Python 3.13...`.

If Python 3.13 is already installed, skip the install step. The commands below select it explicitly and keep the project dependencies in `.venv`; you do not need to activate scripts or change PowerShell security settings.

## 1. Open the project folder

Download and extract the project source ZIP. Rename the extracted folder to `gintama` and place it somewhere with a short path, such as `C:/Games/gintama`, before creating `.venv`. Long folder paths can stop Python dependencies from installing on Windows. Open the folder containing `README.md`, `requirements.txt` and `tools`.

On Windows, type `powershell` in File Explorer's address bar and press Enter. On macOS or Linux, open a terminal in that folder.

## 2. Build your translated copy

On Windows, run these commands. Replace `C:/Games/Gintama/original.nds` with your ROM's actual path; keep the quotes if the path contains spaces.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/build_ui.py --rom "C:/Games/Gintama/original.nds" --out local/english.nds
```

On macOS/Linux, use an installed Python 3.13. If you use the tested Python 3.11 instead, replace `python3.13` in the first command with `python3.11`:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/build_ui.py --rom "/path/to/original.nds" --out local/english.nds
```

When it finishes, open `local/english.nds` in your emulator. Start it normally rather than loading an old save state, which can restore earlier graphics.

The build applies the bundled English dialogue, graphics and UI labels. See [current progress](../README.md#current-progress) for the entry and batch counts. Much of the game is still Japanese. The original ROM is not overwritten.

For the extra build commands below, use `.\.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on macOS/Linux wherever an example says `python`.

## Optional: make a local patch

```sh
python tools/build_ui.py --rom "C:/Games/Gintama/original.nds" --patch local/english.bps
```

This creates `local/english.bps` and its matching `local/english.json`. Keep them together. For custom image labels and other build options, see [the graphics guide](https://github.com/zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation/blob/main/docs/IMAGE_WORKFLOW.md).

## Apply an existing patch

Extract the patch kit and open a terminal in its folder. It should contain `rom_patch.py`, a `.bps` patch and its matching `.json` manifest. Use their actual names in this command:

```sh
python rom_patch.py apply --source "C:/Games/Gintama/original.nds" --patch translation.bps --manifest translation.json --output english.nds
```

Open the resulting `english.nds`. A patch changes only the content listed in its release notes; a dialogue demo is not the full UI build. If you are using the source project instead of a patch kit, replace `rom_patch.py` with `tools/rom_patch.py`.

## If something fails

- **Python not found:** follow the Python setup above. On Windows, check `py -3.13 --version`; on macOS/Linux, check `python3.13 --version` (or `python3.11 --version` for that version).
- **Filename too long / WinError 206 during installation:** extract a fresh copy to a shorter folder, such as `C:/Games/gintama`, then run the three setup commands there. Create a new `.venv`; moving an existing one can break its paths.
- **Wrong ROM:** use the supported, unmodified original. Renaming another ROM will not make it compatible.
- **Output exists:** choose a new output name, such as `local/english-2.nds`.
- **English is missing:** start without an old save state and check whether that screen is covered. Most later dialogue is still Japanese.

<details>
<summary>Supported ROM checksum</summary>

SHA-256: `5c0af5854c55f4f812aa9d902c409b4c0320a31097dab7442ea95b7ddc9eb386`.

The checksum identifies the supported revision, not how the ROM was obtained.

</details>

Keep ROMs, builds and game captures out of public submissions. Check [RIGHTS.md](https://github.com/zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation/blob/main/RIGHTS.md) before sharing a generated patch.

The maintainer does not own Gintama or any original game content. All game rights remain with their respective holders.

## Apply your own dialogue edits

The normal build reads non-empty English entries in `translations/ready/`, including `field_dialogue.json`. Leave untranslated entries as `null`. Rebuild to a new output filename after editing.

To try a downloaded dialogue JSON batch without replacing the bundled files:

```sh
python tools/build_ui.py --rom "C:/Games/Gintama/original.nds" --dialogue "C:/Games/Gintama/my-batch.json" --out local/my-dialogue.nds
```

`--dialogue` selects that batch instead of the bundled dialogue, while still building the graphics and UI. The builder wraps text to the proven 176-pixel field window, preserves page counts, and refuses text that exceeds its original word slot or uses unsupported controls. It never truncates text or relocates the CDB. A passing build is not proof that every game context uses the same window size. Use `--validate-only` to check without writing a ROM, or `--ui-only` for graphics and UI alone.

Most game dialogue is not translated yet. The bundled examples are deliberately concise because Japanese and English must share the original fixed-size slots. Longer script allocation and CDB relocation remain separate research.

## Apply your own opening edits

The normal build includes the bundled opening translation. To try English edited in the website's [Opening page](https://zthegin.github.io/cutscenes.html), download its JSON, or copy it and save it as `opening_scene.json`, then run:

```sh
python tools/build_ui.py --rom "C:/Games/Gintama/original.nds" --cutscene "C:/Games/Gintama/opening_scene.json" --out local/my-opening.nds
```

You can combine `--cutscene` and `--dialogue` to test both exports in one ROM. Each option replaces only its own bundled selection. Keep all opening entries, hashes and part boundaries unchanged. The builder refuses changed source hashes, moved controls and text that does not fit. `--ui-only` cannot be combined with `--cutscene`.

Old emulator save states may restore cached Japanese graphics or scripts; test with a normal boot or a compatible state made for your rebuilt ROM. Keep your original state as a backup.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).

## Apply your own battle edits

Use the no-code [Battle editor](https://zthegin.github.io/battle.html). Choose a battle script and load your own legally obtained original ROM, then download your edited English as `battle_translations.json`.

```powershell
.\.venv\Scripts\python.exe tools/build_ui.py --rom "C:/Games/Gintama/original.nds" --battle "C:/Users/you/Downloads/battle_translations.json" --out local/my-battle.nds
```

This keeps the bundled translations and overlays your battle edits. You may combine `--battle`, `--dialogue` and `--cutscene`. The builder verifies the original MSB/CDB hashes, record hashes, English width, original message sizes and untouched bytes. It rejects unsupported controls and overlong messages rather than moving game data. Use a new output path each time; the original stays unchanged.
