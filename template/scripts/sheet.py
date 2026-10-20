"""联系表：把所有成品拼成带文件名和尺寸的预览图，便于逐张审图。

用法：
    python3 scripts/sheet.py
    python3 scripts/sheet.py --columns 4 --out out/sheet.jpg
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

TYPE_NAMES = {
    "character": "角色",
    "sprite": "精灵",
    "icon": "图标",
    "background": "场景背景",
    "tile": "地形 / 平铺",
    "ui": "界面元素",
    "vfx": "特效",
}

TILE_W, TILE_H = 240, 220
LABEL_H = 34
HEADER_H = 38
PAD = 12
SCALE_RE = re.compile(r"@(\d+)x$")


def collect(root):
    assets_dir = common.project_root(root) / "out" / "assets"
    if not assets_dir.exists():
        return []
    groups = []
    for type_dir in sorted(assets_dir.iterdir()):
        if not type_dir.is_dir():
            continue
        best = {}
        for path in sorted(type_dir.glob("*.png")):
            match = SCALE_RE.search(path.stem)
            scale = int(match.group(1)) if match else 1
            key = path.stem[: match.start()] if match else path.stem
            if key not in best or scale < best[key][0]:
                best[key] = (scale, path)
        files = [item[1] for item in sorted(best.values(), key=lambda value: value[1].name)]
        if files:
            groups.append((TYPE_NAMES.get(type_dir.name, type_dir.name), files))
    return groups


def checkerboard(draw, x, y, width, height, cell=16):
    for yy in range(0, height, cell):
        for xx in range(0, width, cell):
            color = "#2A2E36" if ((xx // cell + yy // cell) % 2 == 0) else "#22262D"
            draw.rectangle(
                [x + xx, y + yy, x + min(xx + cell, width) - 1, y + min(yy + cell, height) - 1],
                fill=color,
            )


def draw_group(title, files, columns):
    columns = max(1, min(int(columns), len(files)))
    rows = math.ceil(len(files) / columns)
    width = columns * (TILE_W + PAD) + PAD
    height = HEADER_H + rows * (TILE_H + LABEL_H + PAD) + PAD
    sheet = Image.new("RGB", (width, height), "#111318")
    draw = ImageDraw.Draw(sheet)
    draw.text((PAD, 8), title, font=common.font(18), fill="#F2F5FF")

    for index, path in enumerate(files):
        row, col = divmod(index, columns)
        x = PAD + col * (TILE_W + PAD)
        y = HEADER_H + PAD + row * (TILE_H + LABEL_H + PAD)
        checkerboard(draw, x, y, TILE_W, TILE_H)
        try:
            image = Image.open(path).convert("RGBA")
        except Exception as exc:  # pragma: no cover
            draw.text((x + 6, y + 6), f"读取失败：{exc}", font=common.font(11), fill="#FF6B6B")
            continue
        original = image.size
        image.thumbnail((TILE_W - 8, TILE_H - 8), Image.LANCZOS)
        sheet.paste(image, (x + (TILE_W - image.width) // 2, y + (TILE_H - image.height) // 2), image)
        draw.text(
            (x, y + TILE_H + 4),
            f"{path.name}  {original[0]}x{original[1]}",
            font=common.font(11),
            fill="#FFD166",
        )
    return sheet


def build_sheet(groups, columns=5):
    blocks = [draw_group(title, files, columns) for title, files in groups]
    if not blocks:
        raise ValueError("没有可预览的成品；先运行 process.py")
    width = max(block.width for block in blocks)
    height = sum(block.height for block in blocks) + PAD * (len(blocks) - 1)
    sheet = Image.new("RGB", (width, height), "#0D0F13")
    y = 0
    for block in blocks:
        sheet.paste(block, (0, y))
        y += block.height + PAD
    return sheet


def main():
    ap = argparse.ArgumentParser(description="生成素材联系表")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--columns", type=int, default=5)
    ap.add_argument("--out", help="总览输出路径；分类图写到同目录 sheets/")
    args = ap.parse_args()

    root = common.project_root(args.project)
    groups = collect(root)
    if not groups:
        print("没有可预览的成品；先运行 process.py", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else root / "out" / "sheet.jpg"
    common.ensure_dir(out.parent)
    for title, files in groups:
        block = draw_group(title, files, args.columns)
        block_path = common.ensure_dir(out.parent / "sheets") / f"{files[0].parent.name}.jpg"
        block.save(block_path, quality=90)
        print(f"分类预览 {block_path}  {len(files)} 张")

    sheet = build_sheet(groups, args.columns)
    sheet.save(out, quality=90)
    print(f"总览 {out}  {sheet.size[0]}x{sheet.size[1]}  {sum(len(f) for _, f in groups)} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
