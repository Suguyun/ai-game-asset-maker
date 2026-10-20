"""精灵图集：把多张同尺寸帧拼成一张图并输出坐标元数据。

用法：
    # 用同一倍率的帧（通常是 1x），不要把 @1x 和 @2x 混在一起
    python3 scripts/atlas.py build out/assets/character/character_knight_*@1x.png \
        -o out/atlas/knight.png --columns 4 --gap 0
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def build_atlas(images, columns=4, gap=0, names=None):
    """拼装图集，返回 (RGBA 图, 元数据)。单元格取所有帧的最大宽高。"""
    if not images:
        raise ValueError("没有可拼装的帧")
    columns = max(1, int(columns))
    gap = max(0, int(gap))
    names = list(names or [])
    images = [im.convert("RGBA") for im in images]
    cell_w = max(im.width for im in images)
    cell_h = max(im.height for im in images)
    rows = math.ceil(len(images) / columns)
    width = columns * cell_w + gap * (columns - 1)
    height = rows * cell_h + gap * (rows - 1)
    atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    frames = []
    for index, im in enumerate(images):
        row, col = divmod(index, columns)
        x = col * (cell_w + gap)
        y = row * (cell_h + gap)
        atlas.alpha_composite(im, (x, y))
        frames.append({
            "index": index,
            "name": names[index] if index < len(names) and names[index] else str(index),
            "x": x,
            "y": y,
            "w": im.width,
            "h": im.height,
        })

    meta = {
        "cell": [cell_w, cell_h],
        "columns": columns,
        "rows": rows,
        "gap": gap,
        "image_size": [width, height],
        "frames": frames,
    }
    return atlas, meta


def main():
    ap = argparse.ArgumentParser(description="拼装精灵图集")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("files", nargs="+")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--columns", type=int, default=4)
    p.add_argument("--gap", type=int, default=0)
    args = ap.parse_args()

    files = [Path(f) for f in args.files]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        print(f"找不到文件：{', '.join(missing)}", file=sys.stderr)
        return 1

    images = [Image.open(f) for f in files]
    names = [f.stem for f in files]
    atlas, meta = build_atlas(images, args.columns, args.gap, names)
    out = Path(args.out)
    common.ensure_dir(out.parent)
    atlas.save(out)
    meta_path = out.with_suffix(".json")
    meta["source"] = [str(f) for f in files]
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{out}  {atlas.size[0]}x{atlas.size[1]}  {len(images)} 帧")
    print(f"{meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
