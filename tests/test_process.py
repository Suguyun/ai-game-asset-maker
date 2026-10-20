import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))
import process  # noqa: E402


def solid(w, h, rgba):
    return Image.new("RGBA", (w, h), rgba)


class ProcessTest(unittest.TestCase):
    def test_remove_solid_bg(self):
        im = solid(10, 10, (255, 255, 255, 255))
        im.putpixel((5, 5), (255, 0, 0, 255))
        out = process.remove_solid_bg(im)
        self.assertEqual(out.getpixel((0, 0))[3], 0)
        self.assertEqual(out.getpixel((5, 5))[3], 255)

    def test_remove_solid_bg_keeps_existing_alpha(self):
        im = solid(10, 10, (255, 255, 255, 0))
        out = process.remove_solid_bg(im)
        self.assertEqual(out.getpixel((0, 0)), (255, 255, 255, 0))

    def test_remove_solid_bg_ignores_stray_semi_transparent_pixel(self):
        im = solid(10, 10, (255, 255, 255, 255))
        im.putpixel((0, 0), (255, 255, 255, 200))
        im.putpixel((5, 5), (255, 0, 0, 255))
        out = process.remove_solid_bg(im)
        self.assertEqual(out.getpixel((9, 9))[3], 0)
        self.assertEqual(out.getpixel((5, 5))[3], 255)

    def test_remove_solid_bg_leaves_complex_background(self):
        im = Image.new("RGBA", (10, 10), (255, 255, 255, 255))
        for y in range(10):
            for x in range(10):
                im.putpixel((x, y), (x * 20, y * 20, 128, 255))
        out = process.remove_solid_bg(im)
        self.assertEqual(out.getpixel((0, 0))[3], 255)

    def test_trim_alpha(self):
        im = solid(10, 10, (0, 0, 0, 0))
        im.paste((255, 0, 0, 255), (3, 4, 6, 7))
        out = process.trim_alpha(im, padding=1)
        self.assertEqual(out.size, (5, 5))

    def test_fit_canvas_center(self):
        im = solid(4, 2, (255, 0, 0, 255))
        out = process.fit_canvas(im, 8, 8, 0, "center", nearest=True)
        self.assertEqual(out.size, (8, 8))
        self.assertEqual(out.getpixel((0, 0))[3], 0)
        self.assertEqual(out.getpixel((4, 4))[3], 255)

    def test_fit_canvas_cover_opaque(self):
        im = solid(4, 2, (255, 0, 0, 255))
        out = process.fit_canvas(im, 8, 8, 0, "center", nearest=True, cover=True)
        self.assertEqual(out.size, (8, 8))
        self.assertEqual(out.getpixel((0, 0))[3], 255)

    def test_fit_canvas_cover_ignores_padding(self):
        im = solid(4, 2, (255, 0, 0, 255))
        out = process.fit_canvas(im, 8, 8, 2, "center", nearest=True, cover=True)
        self.assertEqual(out.getpixel((0, 0))[3], 255)
        self.assertEqual(out.getpixel((7, 7))[3], 255)

    def test_harden_alpha(self):
        im = Image.new("RGBA", (3, 1))
        im.putpixel((0, 0), (255, 0, 0, 0))
        im.putpixel((1, 0), (255, 0, 0, 128))
        im.putpixel((2, 0), (255, 0, 0, 255))
        out = process.harden_alpha(im)
        self.assertEqual([out.getpixel((x, 0))[3] for x in range(3)], [0, 255, 255])

    def test_fit_canvas_bottom_center(self):
        im = solid(4, 2, (255, 0, 0, 255))
        out = process.fit_canvas(im, 8, 8, 1, "bottom-center", nearest=True)
        self.assertEqual(out.getpixel((4, 6))[3], 255)
        self.assertEqual(out.getpixel((4, 3))[3], 0)
        self.assertEqual(out.getpixel((4, 7))[3], 0)

    def test_quantize_to_palette(self):
        im = Image.new("RGBA", (2, 1), (250, 10, 10, 255))
        im.putpixel((1, 0), (10, 250, 10, 255))
        out = process.quantize_to_palette(im, ["#FF0000", "#00FF00"])
        self.assertEqual(out.getpixel((0, 0))[:3], (255, 0, 0))
        self.assertEqual(out.getpixel((1, 0))[:3], (0, 255, 0))

    def test_quantize_keeps_alpha(self):
        im = Image.new("RGBA", (2, 1), (250, 10, 10, 255))
        im.putpixel((1, 0), (0, 0, 0, 0))
        out = process.quantize_to_palette(im, ["#FF0000", "#00FF00"])
        self.assertEqual(out.getpixel((1, 0))[3], 0)


if __name__ == "__main__":
    unittest.main()
