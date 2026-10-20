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

    def test_rejects_non_list_frames(self):
        with self.assertRaises(common.ConfigError):
            self._load("assets:\n  - id: knight\n    type: character\n    frames: 4\n")

    def test_rejects_duplicate_ids(self):
        text = "assets:\n  - id: potion\n    type: icon\n  - id: potion\n    type: icon\n"
        with self.assertRaises(common.ConfigError):
            self._load(text)

    def test_rejects_non_dict_size(self):
        asset = {"id": "x", "type": "icon", "size": [1]}
        with self.assertRaises(common.ConfigError):
            common.resolve_size(asset, {"sizes": {}, "defaults": {}}, common.BUILTIN_PRESETS, 1)

    def test_rejects_non_list_scales(self):
        asset = {"id": "x", "type": "icon", "size": {"preset": "icon", "scales": 2}}
        with self.assertRaises(common.ConfigError):
            common.resolve_size(asset, {"sizes": {}, "defaults": {}}, common.BUILTIN_PRESETS, 1)

    def test_rejects_non_list_palette(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "style.json").write_text('{"palette": "red"}', encoding="utf-8")
            with self.assertRaises(common.ConfigError):
                common.load_style({"style": "style.json"}, folder)

    def test_find_raw_accepts_jpg(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "raw/icon/potion").mkdir(parents=True)
            (root / "raw/icon/potion/potion.jpg").write_bytes(b"x")
            size = {"type": "icon", "id": "potion"}
            self.assertEqual(common.find_raw(root, size, None).resolve(), (root / "raw/icon/potion/potion.jpg").resolve())

    def test_find_raw_accepts_frame_jpg(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "raw/character/knight").mkdir(parents=True)
            (root / "raw/character/knight/walk.jpg").write_bytes(b"x")
            size = {"type": "character", "id": "knight"}
            self.assertEqual(common.find_raw(root, size, "walk").resolve(), (root / "raw/character/knight/walk.jpg").resolve())


if __name__ == "__main__":
    unittest.main()
