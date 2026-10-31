# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IgnoreTests(unittest.TestCase):
    def test_private_payloads_and_reviewed_screenshots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
            (root / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
            blocked = [
                "game.nds",
                "GAME.NDS",
                "game.NdS",
                "game.Ml9",
                "asset.NCGR",
                "font.BIN",
                "export.BPS",
                "recording.MP4",
                "private/data.json",
                "local/game.nds",
                "notes.private.json",
                ".env",
                ".env.production",
                "credentials.json",
                "secret.pem",
                "node_modules/example/index.js",
                "run.log",
                "screenshots/full-game.png",
                "docs/screenshots/gameplay.png",
            ]
            allowed = [
                "README.md",
                "tools/build_web.py",
                "translations/ready/batch_0001.json",
                "docs/screenshots/image-label.png",
                "docs/screenshots/two-line-label.png",
                "docs/screenshots/dialogue-editor.png",
            ]
            for name in blocked + allowed:
                with self.subTest(path=name):
                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(root),
                            "check-ignore",
                            "--no-index",
                            "-q",
                            name,
                        ],
                        capture_output=True,
                    )
                    self.assertEqual(result.returncode, 0 if name in blocked else 1)


if __name__ == "__main__":
    unittest.main()
