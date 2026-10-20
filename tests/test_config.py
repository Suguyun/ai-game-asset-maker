import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))
import common  # noqa: E402


class ConfigTest(unittest.TestCase):
    def _load(self, text, project=None):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "assets.yaml").write_text(text, encoding="utf-8")
            return common.load_assets(project or {"defaults": {"mode": "code-draw"}}, folder)

    def test_loads_assets_and_defaults_mode(self):
        assets = self._load("assets:\n  - id: potion\n    type: icon\n")
        self.assertEqual(assets[0]["mode"], "code-draw")
        self.assertEqual(assets[0]["frames"], [])

    def test_rejects_path_traversal_id(self):
        with self.assertRaises(common.ConfigError):
            self._load("assets:\n  - id: ../evil\n    type: icon\n")

    def test_rejects_uppercase_id(self):
        with self.assertRaises(common.ConfigError):
            self._load("assets:\n  - id: Potion\n    type: icon\n")

    def test_rejects_path_traversal_frame(self):
        with self.assertRaises(common.ConfigError):
            self._load("assets:\n  - id: knight\n    type: character\n    frames: [../evil]\n")

    def test_rejects_empty_assets(self):
        with self.assertRaises(common.ConfigError):
            self._load("assets: []\n")


if __name__ == "__main__":
    unittest.main()
