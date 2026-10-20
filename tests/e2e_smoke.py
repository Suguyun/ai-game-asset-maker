"""端到端自检：复制 template → 写合成素材 → render/process/check/sheet/export。

用标准库 + Pillow 合成素材，不依赖任何外部生图能力。
    python3 tests/e2e_smoke.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import playwright  # noqa: F401
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "template"

ASSETS_YAML = """assets:
  - id: knight
    type: character
    name: 骑士
    mode: code-draw
    size: { preset: character, width: 64, height: 64, scales: [1, 2] }
    frames: [idle, walk]
  - id: grass
    type: tile
    name: 草地
    mode: code-draw
    size: { preset: tile, width: 32, height: 32, scales: [1, 2] }
    frames: []
  - id: gem_blue
    type: icon
    name: 蓝宝石
    mode: code-draw
    size: { preset: icon, width: 128, height: 128, scales: [1, 2] }
    frames: []
  - id: panel
    type: ui
    name: 面板
    mode: code-draw
    size:
      preset: ui
      width: 128
      height: 64
      scales: [1]
      transparent: false
      nineSlice: { left: 16, right: 16, top: 16, bottom: 16 }
    frames: []
"""

KNIGHT = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <g shape-rendering="crispEdges">
    <rect x="24" y="8" width="16" height="16" fill="#F4F4F4"/>
    <rect x="22" y="24" width="20" height="22" fill="#3B5DC9"/>
    <rect x="18" y="26" width="4" height="16" fill="#29366F"/>
    <rect x="42" y="26" width="4" height="16" fill="#29366F"/>
    <rect x="26" y="46" width="5" height="14" fill="#1A1C2C"/>
    <rect x="34" y="46" width="5" height="14" fill="#1A1C2C"/>
    <rect x="26" y="12" width="4" height="4" fill="#1A1C2C"/>
    <rect x="36" y="12" width="4" height="4" fill="#1A1C2C"/>
  </g>
</svg>
"""

KNIGHT_WALK = KNIGHT.replace(
    '<rect x="26" y="46" width="5" height="14" fill="#1A1C2C"/>',
    '<rect x="22" y="46" width="5" height="14" fill="#1A1C2C"/>',
).replace(
    '<rect x="34" y="46" width="5" height="14" fill="#1A1C2C"/>',
    '<rect x="38" y="46" width="5" height="14" fill="#1A1C2C"/>',
)

GRASS = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <g shape-rendering="crispEdges">
    <rect width="32" height="32" fill="#38B764"/>
    <rect x="14" y="14" width="4" height="4" fill="#A7F070"/>
  </g>
</svg>
"""

PANEL = """<svg xmlns="http://www.w3.org/2000/svg" width="128" height="64" viewBox="0 0 128 64">
  <g shape-rendering="crispEdges">
    <rect width="128" height="64" fill="#29366F"/>
    <rect x="6" y="6" width="116" height="52" fill="#1A1C2C"/>
    <rect x="10" y="10" width="108" height="2" fill="#73EFF7"/>
  </g>
</svg>
"""

GEM_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<style>html,body{margin:0;padding:0;background:transparent;overflow:hidden}canvas{display:block;image-rendering:pixelated}</style>
</head><body><canvas id="c"></canvas><script>
const p = new URLSearchParams(location.search);
const w = Number(p.get('w') || 128), h = Number(p.get('h') || 128);
const c = document.getElementById('c');
c.width = w; c.height = h;
const x = c.getContext('2d');
x.imageSmoothingEnabled = false;
const u = w / 32;
x.fillStyle = '#1A1C2C';
x.fillRect(6*u, 6*u, 20*u, 20*u);
x.fillStyle = '#41A6F6';
x.beginPath();
x.moveTo(16*u, 4*u); x.lineTo(28*u, 16*u); x.lineTo(16*u, 28*u); x.lineTo(4*u, 16*u);
x.closePath(); x.fill();
x.fillStyle = '#73EFF7';
x.fillRect(12*u, 10*u, 4*u, 4*u);
x.fillStyle = '#F4F4F4';
x.fillRect(11*u, 9*u, 2*u, 2*u);
</script></body></html>
"""


def run(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"命令失败（{proc.returncode}）：{' '.join(map(str, cmd))}")
    return proc.stdout


def main():
    if not (shutil.which("magick") or shutil.which("convert")):
        print("SKIP: 需要 ImageMagick 渲染 SVG；安装后重跑（brew install imagemagick）")
        return 0
    if not HAS_PLAYWRIGHT:
        print("SKIP: 需要 Playwright 渲染 HTML；安装后重跑（pip install playwright && playwright install chromium）")
        return 0

    work = Path(tempfile.mkdtemp(prefix="game-asset-e2e-"))
    project = work / "工程"
    shutil.copytree(TEMPLATE, project)
    for folder in ("raw", "out", "prompts"):
        shutil.rmtree(project / folder, ignore_errors=True)
        (project / folder).mkdir(parents=True, exist_ok=True)
    (project / "codegen" / "src").mkdir(parents=True, exist_ok=True)
    for path in (project / "codegen" / "src").glob("*"):
        if path.is_file() and path.suffix in (".svg", ".html"):
            path.unlink()

    (project / "assets.yaml").write_text(ASSETS_YAML, encoding="utf-8")
    project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
    project_json["name"] = "E2E 测试"
    (project / "project.json").write_text(json.dumps(project_json, ensure_ascii=False, indent=2), encoding="utf-8")

    src = project / "codegen" / "src"
    (src / "knight__idle.svg").write_text(KNIGHT, encoding="utf-8")
    (src / "knight__walk.svg").write_text(KNIGHT_WALK, encoding="utf-8")
    (src / "grass.svg").write_text(GRASS, encoding="utf-8")
    (src / "gem_blue.html").write_text(GEM_HTML, encoding="utf-8")
    (src / "panel.svg").write_text(PANEL, encoding="utf-8")

    py = sys.executable
    run([py, "scripts/plan.py"], project)
    run([py, "scripts/render.py", "--force"], project)
    run([py, "scripts/process.py"], project)
    run([py, "scripts/check_assets.py"], project)
    run([py, "scripts/sheet.py"], project)
    dest = work / "交付"
    run([py, "scripts/export.py", "--dest", str(dest)], project)

    expected = [
        "assets/character/character_knight_idle@1x.png",
        "assets/character/character_knight_idle@2x.png",
        "assets/character/character_knight_walk@1x.png",
        "assets/character/character_knight_walk@2x.png",
        "assets/tile/tile_grass@1x.png",
        "assets/tile/tile_grass@2x.png",
        "assets/icon/icon_gem_blue@1x.png",
        "assets/icon/icon_gem_blue@2x.png",
        "assets/ui/ui_panel@1x.png",
        "assets/atlas/knight.png",
        "assets/atlas/knight.json",
        "manifest.json",
        "素材清单.md",
        "使用说明.md",
        "预览/联系表.jpg",
    ]
    missing = [name for name in expected if not (dest / name).exists()]
    if missing:
        raise SystemExit(f"缺交付文件：{missing}")

    atlas = json.loads((dest / "assets/atlas/knight.json").read_text(encoding="utf-8"))
    assert len(atlas["frames"]) == 2, atlas
    assert atlas["cell"] == [64, 64], atlas
    assert atlas["frames"][0] == {"index": 0, "name": "idle", "x": 0, "y": 0, "w": 64, "h": 64}, atlas
    assert atlas["frames"][1]["x"] == 64 and atlas["frames"][1]["name"] == "walk", atlas
    assert atlas["frame_names"] == ["idle", "walk"], atlas

    report = json.loads((project / "out/check_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["ERROR"] == 0, report
    assert report["summary"]["WARN"] == 0, report

    sheet = Image.open(dest / "预览/联系表.jpg")
    assert sheet.width > 0 and sheet.height > 0

    print(f"E2E OK  {dest}")
    print(f"临时工程保留在 {project}（可打开预览）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
