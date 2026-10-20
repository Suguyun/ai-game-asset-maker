"""代码绘制渲染：把 codegen/src 下的 SVG / HTML 渲染成 PNG。

约定：
- 单帧：codegen/src/<id>.svg 或 <id>.html
- 多帧：优先 codegen/src/<id>__<frame>.svg，其次同一个 <id>.svg / <id>.html
- HTML 页面会收到查询参数 ?frame=<frame>&scale=<scale>&w=<w>&h=<h>
- 输出尺寸 = 素材单帧尺寸 × 最大导出倍数，写到 raw/<type>/<id>/<frame>.png

用法：
    python3 scripts/render.py
    python3 scripts/render.py --id sample_icon
    python3 scripts/render.py --scale 4 --force
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def find_source(root, asset_id, frame):
    src_dir = common.project_root(root) / "codegen" / "src"
    names = []
    if frame:
        names += [f"{asset_id}__{frame}.svg", f"{asset_id}__{frame}.html"]
    names += [f"{asset_id}.svg", f"{asset_id}.html"]
    for name in names:
        path = src_dir / name
        if path.exists():
            return path
    return None


def render_svg(src, dst, width, height, pixel):
    magick = shutil.which("magick") or shutil.which("convert")
    if not magick:
        raise RuntimeError("缺少 ImageMagick：brew install imagemagick")
    cmd = [magick, "-background", "none", "-density", "384", str(src)]
    if pixel:
        cmd += ["-filter", "point"]
    cmd += ["-resize", f"{width}x{height}!", "-gravity", "center", "-extent", f"{width}x{height}", f"png:{dst}"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ImageMagick 渲染失败：{' '.join(cmd)}\n{proc.stderr.strip()}")


def render_html(src, dst, width, height, scale, frame):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("缺少 Playwright：pip install playwright && playwright install chromium") from exc

    query = f"?frame={quote(str(frame or ''))}&scale={scale}&w={width}&h={height}"
    url = src.resolve().as_uri() + query
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=max(1, scale),
        )
        page.goto(url, wait_until="load")
        page.wait_for_timeout(120)
        page.screenshot(path=str(dst), omit_background=True)
        browser.close()


def render_asset(root, project, style, asset, presets, scale_override=None, force=False):
    frames = common.frames_of(asset)
    size = common.resolve_size(asset, project, presets, len(frames), style=style)
    max_scale = int(scale_override or max(size["scales"]))
    cell = size.get("cell")
    body_w = int(cell or size["width"])
    body_h = int(cell or size["height"])
    pixel = bool(size.get("pixel"))
    done, skipped = [], []

    for frame in frames:
        src = find_source(root, asset["id"], frame)
        if not src:
            raise RuntimeError(
                f"{asset['id']}：找不到绘制源文件。请在 "
                f"codegen/src/{asset['id']}.svg 或 .html（多帧用 {asset['id']}__<frame>.svg）"
            )
        dst = common.raw_path(root, size, frame)
        common.ensure_dir(dst.parent)
        if dst.exists() and not force:
            skipped.append(str(dst))
            continue
        if src.suffix.lower() == ".svg":
            render_svg(src, dst, body_w * max_scale, body_h * max_scale, pixel)
        else:
            render_html(src, dst, body_w, body_h, max_scale, frame)
        done.append(str(dst))
    return done, skipped


def main():
    ap = argparse.ArgumentParser(description="渲染 code-draw 素材")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--id", help="只渲染指定素材")
    ap.add_argument("--scale", type=int, help="覆盖最大渲染倍数")
    ap.add_argument("--force", action="store_true", help="覆盖已有原始图")
    args = ap.parse_args()

    try:
        project = common.load_project(args.project)
        style = common.load_style(project, args.project)
        assets = common.load_assets(project, args.project)
        presets = common.load_presets(project, args.project)
    except common.ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2

    targets = [a for a in assets if a.get("mode") == "code-draw"]
    if args.id:
        targets = [a for a in targets if a.get("id") == args.id]
        if not targets:
            print(f"没有找到 code-draw 素材：{args.id}", file=sys.stderr)
            return 1

    failed = 0
    for asset in targets:
        try:
            done, skipped = render_asset(args.project, project, style, asset, presets, args.scale, args.force)
        except Exception as exc:
            failed += 1
            print(f"ERROR {asset.get('id')}：{exc}", file=sys.stderr)
            continue
        print(f"{asset['id']}：渲染 {len(done)} 张，跳过 {len(skipped)} 张")
        for path in done:
            print(f"  -> {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
