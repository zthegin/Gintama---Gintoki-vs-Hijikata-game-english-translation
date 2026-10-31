# Verify a working copy

Run these commands from the source folder. Use Python 3.13 or the tested Python 3.11, Git, and Node.js 22. Install the Python dependencies in the same environment that runs the checks. On Windows, a configured `py -3.13` can replace `python`, or use the project virtual environment from installation. No ROM is needed for the standard checks. Git is needed by the isolated repository tests; Node.js runs the browser tests.

```sh
python -m pip install -r requirements.txt
python tools/verify.py --out ../verification-run
```

Choose a new folder each time. The checker stops at the first failure and writes `verification.json` plus a log for every completed step. Logs can contain local paths; keep this output private. The checker does not access the network, launch an emulator or publish files.

It checks the public file boundary, all JSON/CSV pairs, immutable batch data, credits, Python regressions and browser-code tests. It builds and audits the website and approved export, checks local HTML links, anchors, module imports and batch assets, verifies that every page identifies the project as unofficial and links its rights notice, then creates two source ZIPs and requires them to be byte-identical. ZIP entries use fixed timestamps, permissions and no per-file comments or extra metadata. A ZIP is committed to its requested output path only after CRC and member-content verification succeeds.

The patch stress test is kept in `tests/test_patch_integration.py`. It uses 72 deterministic randomized source/target pairs, from 1 byte to 64 KiB, and checks the result with an independent decoder. It does not need a game file. Retiring the old demo builder does not remove this test, the output-overwrite tests, or the filtering and browser-export regressions.

## Preview the website

After a successful run:

```sh
python -m http.server 8000 --bind 127.0.0.1 --directory ../verification-run/site
```

Open `http://127.0.0.1:8000/`. Stop the server with Ctrl+C. Do not copy a legally obtained ROM into the site folder. Select it through the editor's local file chooser instead.

## Smaller checks

```sh
python tools/check_public_tree.py
python tools/sync_csv.py --from json --check
python -B -m unittest discover -s tests -v
node --test tests/browser/*.test.mjs
```

The repository-health workflow runs the full verifier on Windows and Ubuntu with Python 3.11 and 3.13. Each job shows a short results table in its Actions summary and keeps the verification report and logs as a downloadable artifact for seven days, including when a check fails. Those CI runs use public test inputs, without a game file. A local Windows run does not prove that the remote jobs have passed.

Technical checks cannot establish permission, translation quality or correct rendering throughout the game. Use your own legally obtained ROM for separate local playtesting. Follow [the publication checklist](PUBLISHING.md) before sharing an artifact.

The optional full-UI regression reads a private ROM from `GINTAMA_TEST_ROM`. It builds all 649 variants and 122 UI slots, checks font/script preservation and validates a BPS roundtrip. Without that environment variable, the game-file check is skipped; the synthetic geometry, font, compression and output-safety tests still run.

---

This is an unofficial fan and educational translation of *Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!!* for Nintendo DS. I do not own the game or its original content. Use only your own legally obtained ROM. See [rights and project limits](../RIGHTS.md).
