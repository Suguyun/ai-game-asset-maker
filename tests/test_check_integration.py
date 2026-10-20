import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "template" / "scripts"))
import check_assets  # noqa: E402
import common  # noqa: E402


class CheckIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "presets").mkdir()
        shutil.copy(REPO / "library" / "presets" / "sizes.json", self.root / "presets" / "sizes.json")
        (self.root / "out" / "assets" / "icon").mkdir(parents=True)
        (self.root / "out" / "assets" / "tile").mkdir(parents=True)
        (self.root / "out" / "assets" / "ui").mkdir(parents=True)
        (self.root / "project.json").write_text(json.dumps({
            "name": "check-test",
            "style": "style.json",
            "sizes": {},
            "output": {"format": "png", "engine": "generic"},
            "defaults": {},
        }), encoding="utf-8")
        (self.root / "style.json").write_text(json.dumps({
            "name": "test",
            "palette": ["#FF0000", "#00FF00"],
            "paletteLock": False,
            "pixelGrid": 0,
        }), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _assets(self, assets):
        (self.root / "assets.yaml").write_text(yaml.safe_dump({"assets": assets}), encoding="utf-8")

    def _run(self):
        return check_assets.run(self.root)

    def test_missing_output_is_error(self):
        self._assets([{"id": "test_icon", "type": "icon", "size": {"preset": "icon", "width": 64, "height": 64, "scales": [1]}}])
        code, report = self._run()
        self.assertEqual(code, 1)
        self.assertEqual(report["summary"]["ERROR"], 1)  # 缺文件

    def test_wrong_size_is_error(self):
        self._assets([{"id": "test_icon", "type": "icon", "size": {"preset": "icon", "width": 64, "height": 64, "scales": [1]}}])
        im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        im.paste((255, 0, 0, 255), (4, 4, 28, 28))
        im.save(self.root / "out/assets/icon/icon_test_icon@1x.png")
        code, report = self._run()
        self.assertEqual(code, 1)
        messages = [c["message"] for asset in report["assets"] for c in asset["checks"]]
        self.assertTrue(any("尺寸" in message for message in messages), messages)

    def test_valid_icon_passes(self):
        self._assets([{"id": "test_icon", "type": "icon", "size": {"preset": "icon", "width": 64, "height": 64, "scales": [1]}}])
        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        im.paste((255, 0, 0, 255), (8, 8, 56, 56))
        im.save(self.root / "out/assets/icon/icon_test_icon@1x.png")
        code, report = self._run()
        self.assertEqual(code, 0, report)

    def test_transparent_tile_is_error(self):
        self._assets([{"id": "test_tile", "type": "tile", "size": {"preset": "tile", "width": 32, "height": 32, "scales": [1]}}])
        Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(self.root / "out/assets/tile/tile_test_tile@1x.png")
        code, report = self._run()
        self.assertEqual(code, 1)
        messages = [c["message"] for asset in report["assets"] for c in asset["checks"]]
        self.assertTrue(any("全透明" in message for message in messages), messages)

    def test_nine_slice_overflow_is_error(self):
        self._assets([{
            "id": "test_panel",
            "type": "ui",
            "size": {"preset": "ui", "width": 32, "height": 32, "scales": [1], "transparent": False,
                     "nineSlice": {"left": 20, "right": 20, "top": 8, "bottom": 8}},
        }])
        Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(self.root / "out/assets/ui/ui_test_panel@1x.png")
        code, report = self._run()
        self.assertEqual(code, 1)
        messages = [c["message"] for asset in report["assets"] for c in asset["checks"]]
        self.assertTrue(any("九宫格" in message for message in messages), messages)


if __name__ == "__main__":
    unittest.main()
