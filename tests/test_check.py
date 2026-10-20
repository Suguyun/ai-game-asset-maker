import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))
import check_assets as c  # noqa: E402


class CheckTest(unittest.TestCase):
    def test_seam_error_zero_for_solid(self):
        im = Image.new("RGBA", (8, 8), (10, 20, 30, 255))
        self.assertLess(c.seam_error(im), 0.001)

    def test_seam_error_detects_mismatch(self):
        im = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
        for y in range(8):
            im.putpixel((0, y), (255, 255, 255, 255))
        self.assertGreater(c.seam_error(im), 0.2)

    def test_alpha_bbox(self):
        im = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        im.paste((255, 0, 0, 255), (2, 2, 8, 8))
        self.assertEqual(c.alpha_bbox(im), (2, 2, 8, 8))

    def test_fill_ratio(self):
        im = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        im.paste((255, 0, 0, 255), (2, 2, 8, 9))
        self.assertAlmostEqual(c.fill_ratio(im), 0.7)

    def test_nine_slice_ok(self):
        nine = {"left": 32, "right": 32, "top": 32, "bottom": 32}
        self.assertTrue(c.nine_slice_ok(128, 128, nine))
        self.assertFalse(c.nine_slice_ok(64, 128, nine))
        self.assertFalse(c.nine_slice_ok(128, 64, nine))

    def test_semi_transparent_ratio(self):
        im = Image.new("RGBA", (4, 1), (255, 0, 0, 255))
        im.putpixel((0, 0), (255, 0, 0, 128))
        self.assertAlmostEqual(c.semi_transparent_ratio(im), 0.25)


if __name__ == "__main__":
    unittest.main()
