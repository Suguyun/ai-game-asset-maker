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
import export  # noqa: E402

PROJECT = {
    "name": "export-test",
    "style": "style.json",
    "sizes": {},
    "output": {"format": "png", "engine": "generic"},
    "defaults": {},
}
STYLE = {
    "name": "test",
    "palette": ["#FF0000"],
    "paletteLock": False,
    "pixelGrid": 0,
}
ASSETS = [{
    "id": "test_icon",
    "type": "icon",
    "name": "图标",
    "mode": "code-draw",
    "size": {"preset": "icon", "width": 64, "height": 64, "scales": [1]},
    "frames": [],
}]


class DefaultDestTest(unittest.TestCase):
    def test_parent_traversal_is_sanitized(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "proj"
            root.mkdir()
            dest = export.default_dest(root, {"name": "../evil"})
            self.assertNotIn("..", str(dest))
            self.assertEqual(dest.parent.resolve(), (root.parent / "outputs").resolve())


class ExportGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "工程"
        self.root.mkdir()
        (self.root / "presets").mkdir()
        shutil.copy(REPO / "library" / "presets" / "sizes.json", self.root / "presets" / "sizes.json")
        (self.root / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
        (self.root / "style.json").write_text(json.dumps(STYLE), encoding="utf-8")
        (self.root / "assets.yaml").write_text(yaml.safe_dump({"assets": ASSETS}), encoding="utf-8")
        out_icon = self.root / "out" / "assets" / "icon"
        out_icon.mkdir(parents=True)
        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        im.paste((255, 0, 0, 255), (8, 8, 56, 56))
        im.save(out_icon / "icon_test_icon@1x.png")
        (self.root / "out" / "sheet.jpg").write_bytes(b"fake")
        self.dest = Path(self._tmp.name) / "交付"
        self._write_report(0)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_report(self, errors):
        (self.root / "out" / "check_report.json").write_text(json.dumps({
            "summary": {"ERROR": errors, "WARN": 0, "OK": 0},
        }), encoding="utf-8")

    def test_export_passes_with_zero_error_report(self):
        code = export.export(self.root, self.dest)
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "manifest.json").exists())
        self.assertTrue((self.dest / "assets/icon/icon_test_icon@1x.png").exists())

    def test_export_refuses_when_report_has_error(self):
        self._write_report(1)
        self.assertEqual(export.export(self.root, self.dest), 1)
        self.assertFalse((self.dest / "manifest.json").exists())

    def test_export_refuses_without_report(self):
        (self.root / "out" / "check_report.json").unlink()
        self.assertEqual(export.export(self.root, self.dest), 1)

    def test_skip_check_allows_missing_report(self):
        (self.root / "out" / "check_report.json").unlink()
        self.assertEqual(export.export(self.root, self.dest, skip_check=True), 0)

    def test_export_refuses_missing_output(self):
        (self.root / "out/assets/icon/icon_test_icon@1x.png").unlink()
        self.assertEqual(export.export(self.root, self.dest), 1)

    def test_export_refuses_stale_report(self):
        import os
        import time

        report = self.root / "out" / "check_report.json"
        old = time.time() - 10
        os.utime(report, (old, old))
        self.assertEqual(export.export(self.root, self.dest), 1)

    def test_copy_to_requires_force_when_target_has_files(self):
        target = Path(self._tmp.name) / "游戏工程"
        (target / "assets").mkdir(parents=True)
        (target / "assets" / "old.png").write_bytes(b"x")
        self.assertEqual(export.export(self.root, self.dest, copy_to=target), 1)
        self.assertEqual(export.export(self.root, self.dest, copy_to=target, force=True), 0)
        self.assertTrue((target / "assets" / "icon" / "icon_test_icon@1x.png").exists())
        self.assertTrue((target / "assets" / "old.png").exists())


if __name__ == "__main__":
    unittest.main()
