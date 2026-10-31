# Unofficial English translation of Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!

This is a work-in-progress English fan translation of the Nintendo DS game. Use your own legally obtained ROM to build a partially translated copy, or help with a line in the browser editor. The project is unofficial and shared for fans and educational use.

I do not own the original game, Gintama, or their characters, story, artwork, music, text or trademarks. Those rights belong to their respective holders. No affiliation, endorsement or permission is implied. English adaptations are included; see [rights and project limits](RIGHTS.md).

## Choose what you want to do

- [I just want to play](#i-just-want-to-play)
- [I want to help translate (no code)](#i-want-to-help-translate)
- [I want to improve the tools](#i-want-to-improve-the-tools)
- [Check progress](#current-progress)

You do not need to write code to play or help translate. **Suggest on GitHub is the easiest way to contribute.**

### I just want to play

Use Python 3.13 on Windows and your own legally obtained, unmodified ROM of the supported revision. Python 3.11 is also tested; 3.10 is too old for the current dependencies. No ROM is included or linked here. No Python? Follow the [short installation steps](docs/APPLY_PATCH.md#install-python-on-windows).

For this project, supply only a ROM you are lawfully allowed to use and modify. Owning a cartridge or matching a checksum does not prove that permission or how the file was obtained. The checksum checks compatibility only. If you are unsure, check before proceeding. Keep untouched backups of your original ROM and saves.

Do not request ROMs or unauthorized download links here, upload game files, or share the rebuilt `.nds`. See [rights and project limits](RIGHTS.md) for what the project includes and what its license covers.

1. Choose **Code → Download ZIP** and extract it. Rename the extracted folder to `gintama` and keep it somewhere with a short path, such as `C:/Games/gintama`, before running the commands. Long folder paths can stop Python dependencies from installing on Windows.
2. Open a terminal in the folder with `README.md` and `requirements.txt`. On Windows, type `powershell` in that folder’s File Explorer address bar and press Enter.
3. Copy these commands, replacing the example ROM path with yours:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/build_ui.py --rom "C:/Games/Gintama/original.nds" --out local/english.nds
```

Open `local/english.nds` in your emulator. The command applies the bundled English dialogue and graphics on your device and leaves the original unchanged. For another build, choose a new output filename.

GitHub Actions checks the project and builds the website and text exports. It has no game ROM and does not build a playable game.

See [installation](docs/APPLY_PATCH.md) for the supported ROM checksum, existing patch instructions and help with errors.

<details>
<summary>Let a local coding assistant set it up</summary>

You can give Claude Code, Codex or another assistant with local file access this request. A chat-only assistant cannot build the file on your computer.

```text
Set up https://github.com/zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation in a folder I choose. Ask me for the local path to my own legally obtained, unmodified ROM before building. If I am unsure whether I may use and modify that file, stop and let me check. Do not find or download game files or ask anyone else for a ROM.

Use Python 3.13 and a project-local virtual environment with requirements.txt. Run tools/build_ui.py with my ROM path and a new local/english.nds output. Keep the original and saves unchanged, never upload game or private files, and tell me the output path and which checks passed. Do not launch an emulator unless I ask.
```

The assistant must get the ROM path from you. Grant access to the project folder and that file only. For macOS/Linux, see [installation](docs/APPLY_PATCH.md).

</details>

### I want to help translate

**No coding is required.**

Start with one line. You only need the browser editor, your legally obtained ROM and a GitHub account. No Python, Git, fork or file upload is needed.

1. Open the [dialogue editor](https://zthegin.github.io/) and select your own legally obtained ROM. It stays on your computer.
2. Choose a batch and a line, then write the English. Keep the page count shown above the text box; type `\f` for a page break.
3. Click **Suggest on GitHub**, sign in if needed, check the prepared suggestion and submit the issue.

That submits one record for review. I check the wording and local build before accepting it; submitting an issue does not publish the edit. Accepted suggestions are credited to the issue's GitHub account, with a link to the contribution.

Maintainers can follow [Review and accept a website suggestion](docs/REVIEW_SUGGESTIONS.md) to take an issue through review, credit and publication.

Use [Opening](https://zthegin.github.io/cutscenes.html) for the indexed first-cutscene entries, [Battle](https://zthegin.github.io/battle.html) for battle text, or [Images](https://zthegin.github.io/graphics.html) for name labels. These pages also use **Suggest on GitHub**. Other adventure cutscenes are not available yet. To send several field lines or image labels together, use the [batch walkthrough](docs/START_HERE.md#submit-a-batch-or-image-label).

Download from `main` to play. Send translation pull requests to `staging`. Two approvals on the current version put a valid translation PR in the reviewed queue; I still check and merge it myself. See the [contribution rules](CONTRIBUTING.md) for details and credits.

### I want to improve the tools

Keep tool changes separate from translation edits. The [testing guide](docs/TESTING.md) covers the checks, including optional local tests with your own legally obtained ROM.

Tool contributors need Git, Node.js 22 and the Python dependencies. Players only need the Python setup above. Run this on Windows:

```powershell
.\.venv\Scripts\python.exe tools/verify.py --out ../verification-run
```

On macOS/Linux, use `.venv/bin/python` in the same command. Choose a new output folder each time. This checks the data, Python and browser code, website, exports and source ZIPs. The tests include randomized patch cases and checks that invalid inputs cannot replace existing files. GitHub runs the same verifier on Windows and Linux; it does not receive your game file.

## Current progress

These counts measure text records, not hours of gameplay.

| Category | Translated / indexed | Progress |
| --- | ---: | ---: |
| Field dialogue | 8,424 / 22,480 entries | 37.47% |
| Field batches | 42 / 71 complete | 59.15% |
| Battle dialogue | 406 / 142,242 records | 0.29% |
| Opening cutscene | 520 entries | Full cutscene total not catalogued |
| Graphical variants | 649 | Total not catalogued |
| Native UI text | 122 slots | Total not catalogued |

Indexed totals include records the current writers cannot edit. Repeated records and graphical variants are counted separately. These figures are not a percentage of the whole game. New text passes offline build checks; complete in-game playtesting is still pending.

## Further docs

- [Installation and troubleshooting](docs/APPLY_PATCH.md)
- [First contribution walkthrough](docs/START_HERE.md)
- [Review and accept a website suggestion](docs/REVIEW_SUGGESTIONS.md)
- [Translation wording and names](docs/TRANSLATION_GUIDE.md)
- [Fonts and supported characters](docs/FONT.md)
- [Image workflow](docs/IMAGE_WORKFLOW.md)
- [Translators and contribution totals](TRANSLATORS.md)
- [Repository setup and automation](docs/MAINTAINER_SETUP.md)
- [Website source](https://github.com/zthegin/zthegin.github.io)

## Background

Banpresto released this single-player Nintendo DS adventure in Japan on 14 December 2006. Choose Gintoki or Hijikata to follow events in Kabukicho from their different viewpoints. Collectible **Gin Tama** are used in battles: some deliver verbal attacks, while others deal physical damage. Completing the collection is an optional goal. See [Nintendo's original listing](https://www.nintendo.co.jp/ds/software/avgj/index.html).

The game draws on Hideaki Sorachi's *Gintama* manga and anime, with the Yorozuya odd-jobs crew, samurai, aliens and absurd comedy. Read the [game and anime background](docs/ABOUT_THE_GAME.md) for more.

## Piracy and rights-holder requests

I do not support piracy and discourage it. Use only your own legally obtained ROM. Do not share game files or link to unauthorized downloads.

I take rights concerns seriously. If Bandai Namco, Hideaki Sorachi or another rights holder or authorized representative contacts me, I will promptly review the request and verify the sender's authority and the material concerned. For a verified request, I will remove or disable the affected material I control and stop the related work. If the concern covers the project as a whole, this may mean taking it offline. I will follow GitHub's takedown process and applicable legal requirements.

That response covers material I control. Other people's forks, clones and cached copies may remain. Removal does not resolve any earlier rights issue, and fan or educational intent does not establish permission.

## Rights and project limits

I do not own the game or any original Gintama content. Keep ROMs, rebuilt copies, extracted assets, source-script dumps, saves and game captures on your own computer. Do not attach them to issues or pull requests.

[Apache 2.0](LICENSE) covers the project’s code, original documentation and original lettering. It grants no rights to the game or franchise. Third-party terms and contribution details are in [RIGHTS.md](RIGHTS.md).
