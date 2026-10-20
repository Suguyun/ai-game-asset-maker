"""环境体检：只检查、不安装。

用法：
    python3 scripts/doctor.py
    python3 scripts/doctor.py --project /path/to/工程
"""
from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

OK, WARN, MISSING = "OK", "WARN", "MISSING"
rows = []


def add(level, item, detail):
    rows.append((level, item, detail))


def check_python():
    if sys.version_info >= (3, 9):
        add(OK, "Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    else:
        add(MISSING, "Python", "需要 3.9 及以上")


def check_modules():
    for name, pkg in (("PIL", "Pillow"), ("numpy", "numpy"), ("yaml", "PyYAML")):
        try:
            mod = importlib.import_module(name)
            version = getattr(mod, "__version__", "")
            add(OK, pkg, version)
        except ImportError:
            add(MISSING, pkg, "pip install -r requirements.txt")


def check_imagemagick():
    binary = shutil.which("magick") or shutil.which("convert")
    if not binary:
        add(WARN, "ImageMagick", "code-draw 渲染 SVG 需要；brew install imagemagick")
        return
    try:
        out = subprocess.run([binary, "-version"], capture_output=True, text=True, timeout=10).stdout
        add(OK, "ImageMagick", out.splitlines()[0] if out else binary)
    except Exception as exc:  # pragma: no cover
        add(WARN, "ImageMagick", f"无法执行：{exc}")


def check_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        add(WARN, "Playwright", "code-draw 渲染 HTML 需要；pip install playwright && playwright install chromium")
        return
    try:
        with sync_playwright() as p:
            path = Path(p.chromium.executable_path)
        if path.exists():
            add(OK, "Playwright chromium", str(path))
        else:
            add(WARN, "Playwright chromium", "playwright install chromium")
    except Exception as exc:
        add(WARN, "Playwright chromium", f"未就绪：{exc}")


def check_font():
    for path in common._FONT_CANDIDATES:
        if Path(path).exists():
            add(OK, "中文字体", path)
            return
    add(WARN, "中文字体", "联系表中文标签会退回默认字体")


def check_configs(root):
    required = ("project.json", "style.json", "assets.yaml")
    for name in required:
        path = root / name
        if path.exists():
            add(OK, "配置", str(path))
        else:
            add(MISSING, "配置", f"缺少 {path}；从 template 复制一份工程")


def check_project_files(root):
    try:
        project = common.load_project(root)
        common.load_style(project, root)
        assets = common.load_assets(project, root)
        presets = common.load_presets(project, root)
        for asset in assets:
            common.resolve_size(asset, project, presets, len(common.frames_of(asset)),
                                style=common.load_style(project, root))
        add(OK, "素材清单", f"{len(assets)} 个素材，尺寸全部可解析")
    except Exception as exc:
        add(WARN, "素材清单", f"{exc}")


def main():
    ap = argparse.ArgumentParser(description="游戏素材工程环境体检")
    ap.add_argument("--project", help="工程根目录；默认使用当前脚本所在工程")
    args = ap.parse_args()
    root = common.project_root(args.project)

    check_python()
    check_modules()
    check_imagemagick()
    check_playwright()
    check_font()
    check_configs(root)
    if (root / "project.json").exists():
        check_project_files(root)

    width = max(len(item) for _, item, _ in rows) + 2
    for level, item, detail in rows:
        print(f"{level:<8}{item:<{width}}{detail}")

    missing = [r for r in rows if r[0] == MISSING]
    warned = [r for r in rows if r[0] == WARN]
    print(f"\n{len(rows)} 项检查：{len(missing)} MISSING，{len(warned)} WARN")
    if missing:
        print("先补齐 MISSING 项再开工。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
