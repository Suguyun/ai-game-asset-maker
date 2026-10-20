import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))
import common  # noqa: E402

PRESETS = {
    "icon": {"width": 256, "height": 256, "scales": [1, 2], "padding": 8, "trim": True, "anchor": "center", "transparent": True},
    "sprite": {"cell": 64, "columns": 4, "scales": [1], "gap": 0, "padding": 0, "trim": False, "anchor": "bottom-center", "transparent": True},
}
PROJECT = {"sizes": {"icon": {"width": 128, "scales": [1, 4]}}, "defaults": {"mode": "ai-image", "padding": 2}}


class SizeTest(unittest.TestCase):
    def test_project_override_beats_preset(self):
        asset = {"id": "p", "type": "icon", "size": {"preset": "icon"}}
        size = common.resolve_size(asset, PROJECT, PRESETS, 1)
        self.assertEqual((size["width"], size["height"]), (128, 256))
        self.assertEqual(size["scales"], [1, 4])
        self.assertEqual(size["padding"], 8)

    def test_asset_object_beats_project(self):
        asset = {"id": "p", "type": "icon", "size": {"preset": "icon", "width": 64, "height": 64, "scales": [1]}}
        size = common.resolve_size(asset, PROJECT, PRESETS, 1)
        self.assertEqual((size["width"], size["height"], size["scales"]), (64, 64, [1]))

    def test_sprite_rows_from_frames(self):
        asset = {"id": "k", "type": "sprite", "size": {"preset": "sprite", "columns": 4}, "frames": ["a", "b", "c", "d", "e"]}
        size = common.resolve_size(asset, PROJECT, PRESETS, 5)
        self.assertEqual((size["width"], size["height"], size["rows"]), (256, 128, 2))

    def test_pixel_follows_style(self):
        asset = {"id": "p", "type": "icon", "size": {"preset": "icon"}}
        size = common.resolve_size(asset, PROJECT, PRESETS, 1, style={"pixelGrid": 16})
        self.assertTrue(size["pixel"])

    def test_output_name(self):
        self.assertEqual(common.output_name("icon", "potion", None, 2), "icon_potion@2x.png")
        self.assertEqual(common.output_name("character", "knight", "walk", 1), "character_knight_walk@1x.png")


if __name__ == "__main__":
    unittest.main()
