# 游戏素材生成器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 `ai-game-asset-maker` 仓库：AI 按规范把游戏素材需求转成一套风格统一、尺寸正确、可直接进工程的 PNG 素材包。

**Architecture:** 配置驱动 + 双模生成。三份项目配置（`style.json` / `project.json` / `assets.yaml`）描述风格、尺寸与素材清单；Python 脚本承担规划、代码渲染、后处理、校验、打包；AI 只负责问需求、写 prompt、写绘制代码与审图。

**Tech Stack:** Python 3.9+、Pillow、numpy、PyYAML；代码绘制用 SVG + ImageMagick，或 HTML/Canvas + Playwright；测试用标准库 `unittest`。

---

## 文件结构总览

| 文件 | 职责 |
|---|---|
| `template/scripts/common.py` | 配置加载、尺寸合并、路径与字体工具 |
| `template/scripts/doctor.py` | 环境体检，只检查不安装 |
| `template/scripts/plan.py` | 校验清单、输出矩阵、prompt 包导出 |
| `template/scripts/render.py` | code-draw：SVG/HTML → PNG |
| `template/scripts/process.py` | 去底、裁切、补边、缩放、调色锁定、精灵表 |
| `template/scripts/atlas.py` | 图集拼装与元数据 |
| `template/scripts/sheet.py` | 联系表预览 |
| `template/scripts/check_assets.py` | 质量闸门 |
| `template/scripts/export.py` | 打包交付物与 manifest |
| `tests/test_sizes.py` | 尺寸合并与矩阵 |
| `tests/test_process.py` | 后处理像素结果 |
| `tests/test_check.py` | 校验分支 |
| `library/styles/*.json` | 7 张内置风格卡 |
| `library/presets/sizes.json` | 素材类型尺寸预设 |
| `template/presets/sizes.json` | 预设副本（工程独立运行时不依赖工具目录） |
| `references/*.md` | 8 份阶段手册 |
| `AGENTS.md` / `SKILL.md` / `README.md` | 工作规范与入口 |

---

### Task 1: 仓库骨架与基础配置

**Files:**
- Create: `.gitignore`, `LICENSE`, `CLAUDE.md`, `template/requirements.txt`
- Create: `template/{raw,codegen/src,prompts,out}/.gitkeep`
- Create: `outputs/.gitkeep`

- [ ] **Step 1: 写 `.gitignore`**

```gitignore
# 项目产物
outputs/*
!outputs/.gitkeep
template/out/*
!template/out/.gitkeep
template/raw/*
!template/raw/.gitkeep
template/prompts/*
!template/prompts/.gitkeep

# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/

# 系统
.DS_Store
```

- [ ] **Step 2: 写 `LICENSE`（MIT，年份 2026）与 `CLAUDE.md`**

`CLAUDE.md` 内容：`本仓库的工作规范写在 AGENTS.md，开始任何工作前先完整读一遍。` 下一行 `@AGENTS.md`。

- [ ] **Step 3: 写 `template/requirements.txt`**

```
Pillow>=10.0
numpy>=1.24
PyYAML>=6.0
```

- [ ] **Step 4: 创建空目录占位并提交**

```bash
mkdir -p template/{raw,codegen/src,prompts,out} outputs
touch template/{raw,codegen/src,prompts,out}/.gitkeep outputs/.gitkeep
git add .gitignore LICENSE CLAUDE.md template/requirements.txt template outputs
git commit -m "chore: 仓库骨架"
```

---

### Task 2: 尺寸预设与风格库

**Files:**
- Create: `library/presets/sizes.json`
- Create: `template/presets/sizes.json`（内容与上者相同）
- Create: `library/styles/{像素冒险,Q版卡通,暗黑奇幻,赛博霓虹,手绘水彩,扁平矢量,写实厚涂}.json`

- [ ] **Step 1: 写 `library/presets/sizes.json`**

```json
{
  "icon":       { "width": 256, "height": 256, "scales": [1, 2], "padding": 8, "trim": true, "anchor": "center", "transparent": true },
  "character":  { "width": 512, "height": 512, "scales": [1, 2], "padding": 8, "trim": true, "anchor": "bottom-center", "transparent": true },
  "sprite":     { "cell": 64, "columns": 4, "scales": [1], "gap": 0, "padding": 0, "trim": false, "anchor": "bottom-center", "transparent": true },
  "background": { "width": 1920, "height": 1080, "scales": [1], "padding": 0, "trim": false, "anchor": "center", "transparent": false },
  "tile":       { "width": 64, "height": 64, "scales": [1, 2], "padding": 0, "trim": false, "anchor": "center", "transparent": true, "seamless": true },
  "ui":         { "width": 512, "height": 128, "scales": [1, 2], "padding": 0, "trim": false, "anchor": "center", "transparent": true, "nineSlice": { "left": 32, "right": 32, "top": 32, "bottom": 32 } },
  "vfx":        { "cell": 128, "columns": 8, "scales": [1], "gap": 0, "padding": 4, "trim": false, "anchor": "center", "transparent": true }
}
```

- [ ] **Step 2: 写 7 张风格卡**

每张字段固定：`name / keywords / palette / line / lighting / material / referenceImages / avoid / pixelGrid / paletteLock / background`。
色板至少 6 色，`avoid` 至少 4 项。像素冒险 `pixelGrid` 为 16 且 `paletteLock` 为 `true`；其余 `pixelGrid` 为 0。

- [ ] **Step 3: 复制预设并提交**

```bash
mkdir -p template/presets && cp library/presets/sizes.json template/presets/sizes.json
git add library template/presets && git commit -m "feat: 内置风格卡与尺寸预设"
```

---

### Task 3: 项目模板配置

**Files:**
- Create: `template/project.json`
- Create: `template/style.json`
- Create: `template/assets.yaml`

- [ ] **Step 1: 写 `template/project.json`**

```json
{
  "name": "示例游戏",
  "style": "style.json",
  "sizes": {},
  "output": { "format": "png", "engine": "generic" },
  "defaults": { "mode": "ai-image", "padding": 8, "trim": true, "anchor": "center" }
}
```

- [ ] **Step 2: 写 `template/style.json`**（内容为「像素冒险」风格卡的副本，名字改为「示例风格」）

- [ ] **Step 3: 写 `template/assets.yaml`**

```yaml
assets:
  - id: sample_icon
    type: icon
    name: 示例图标
    mode: code-draw
    size: { preset: icon, width: 128, height: 128, scales: [1, 2] }
    notes: "一枚发光药水瓶，透明背景"
```

- [ ] **Step 4: 提交**

```bash
git add template/project.json template/style.json template/assets.yaml
git commit -m "feat: 新项目配置模板"
```

---

### Task 4: `common.py` 配置与尺寸核心

**Files:**
- Create: `template/scripts/common.py`
- Test: `tests/test_sizes.py`

**接口：**
- `load_project(root)` → dict
- `load_style(project, root)` → dict
- `load_assets(project, root)` → list[dict]
- `resolve_size(asset, project, presets, frame_count)` → dict，含 `width/height/cell/columns/rows/scales/padding/anchor/transparent/trim/seamless/nineSlice/pixel`
- `output_name(asset_type, asset_id, frame, scale)` → `str`
- `font(size)` → `ImageFont`

- [ ] **Step 1: 写失败测试 `tests/test_sizes.py`**

```python
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))
import common

PRESETS = {
    "icon": {"width": 256, "height": 256, "scales": [1, 2], "padding": 8, "trim": True, "anchor": "center", "transparent": True},
    "sprite": {"cell": 64, "columns": 4, "scales": [1], "gap": 0, "padding": 0, "trim": False, "anchor": "bottom-center", "transparent": True},
}
PROJECT = {"sizes": {"icon": {"width": 128, "scales": [1, 4]}}, "defaults": {"mode": "ai-image", "padding": 2}}

class SizeTest(unittest.TestCase):
    def test_project_override_beats_preset(self):
        a = {"id": "p", "type": "icon", "size": {"preset": "icon"}}
        s = common.resolve_size(a, PROJECT, PRESETS, 1)
        self.assertEqual((s["width"], s["height"]), (128, 256))
        self.assertEqual(s["scales"], [1, 4])
        self.assertEqual(s["padding"], 8)

    def test_asset_object_beats_project(self):
        a = {"id": "p", "type": "icon", "size": {"preset": "icon", "width": 64, "height": 64, "scales": [1]}}
        s = common.resolve_size(a, PROJECT, PRESETS, 1)
        self.assertEqual((s["width"], s["height"], s["scales"]), (64, 64, [1]))

    def test_sprite_rows_from_frames(self):
        a = {"id": "k", "type": "sprite", "size": {"preset": "sprite", "columns": 4}, "frames": ["a", "b", "c", "d", "e"]}
        s = common.resolve_size(a, PROJECT, PRESETS, 5)
        self.assertEqual((s["width"], s["height"], s["rows"]), (256, 128, 2))

    def test_output_name(self):
        self.assertEqual(common.output_name("icon", "potion", None, 2), "icon_potion@2x.png")
        self.assertEqual(common.output_name("character", "knight", "walk", 1), "character_knight_walk@1x.png")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

```bash
python3 -m unittest tests.test_sizes -v
```

Expected: FAIL（`ModuleNotFoundError: common` 或属性不存在）

- [ ] **Step 3: 实现 `common.py`**

关键逻辑：

```python
def resolve_size(asset, project, presets, frame_count):
    typ = asset["type"]
    merged = dict(presets.get(typ, {}))
    merged.update(project.get("sizes", {}).get(typ, {}))
    spec = asset.get("size", {})
    if isinstance(spec, str):
        spec = {"preset": spec}
    preset_name = spec.get("preset")
    if preset_name and preset_name in presets:
        merged.update(presets[preset_name])
    merged.update({k: v for k, v in spec.items() if k != "preset"})
    defaults = project.get("defaults", {})
    for k in ("padding", "trim", "anchor", "mode"):
        if k in defaults and k not in merged:
            merged[k] = defaults[k]
    columns = int(merged.get("columns", 1) or 1)
    cell = merged.get("cell")
    frames = max(1, frame_count)
    if cell:
        rows = (frames + columns - 1) // columns
        merged["rows"] = rows
        merged.setdefault("width", int(cell) * columns)
        merged.setdefault("height", int(cell) * rows)
    merged["columns"] = columns
    merged.setdefault("scales", [1])
    merged.setdefault("padding", 0)
    merged.setdefault("anchor", "center")
    merged.setdefault("transparent", True)
    merged.setdefault("trim", True)
    merged.setdefault("pixel", bool(style.get("pixelGrid", 0)))
    return merged
```

`pixel` 需要风格信息，因此 `resolve_size` 增加可选参数 `style=None`；测试不传时为 False。`output_name` 用 `@<scale>x.png`，无 frame 时省略。

- [ ] **Step 4: 跑测试**

```bash
python3 -m unittest tests.test_sizes -v
```

Expected: 4 tests PASS

- [ ] **Step 5: 提交**

```bash
git add template/scripts/common.py tests/test_sizes.py
git commit -m "feat: 配置加载与尺寸解析"
```

---

### Task 5: `doctor.py` 环境体检

**Files:**
- Create: `template/scripts/doctor.py`

- [ ] **Step 1: 实现**

检查项与输出：

| 项 | 级别 | 说明 |
|---|---|---|
| Python ≥ 3.9 | MISSING | 当前版本 |
| `PIL` / `numpy` / `yaml` | MISSING | 缺失时给出 `pip install -r requirements.txt` |
| ImageMagick（`magick` 或 `convert`） | WARN | 代码绘制 SVG 时需要 |
| Playwright + chromium | WARN | 代码绘制 HTML 时需要 |
| 字体文件 | WARN | 联系表中文标签需要 |
| 工作目录三份配置 | MISSING | 缺少时提示复制 template |

输出格式 `OK / WARN / MISSING`，存在 MISSING 时退出码 1。

- [ ] **Step 2: 运行验证**

```bash
python3 template/scripts/doctor.py
```

Expected: 打印各项状态；本机应有 WARN（未装 chromium）或全 OK。

- [ ] **Step 3: 提交**

```bash
git add template/scripts/doctor.py && git commit -m "feat: 环境体检脚本"
```

---

### Task 6: `plan.py` 规划与 prompt 导出

**Files:**
- Create: `template/scripts/plan.py`

- [ ] **Step 1: 实现校验**

规则：`id` 唯一且匹配 `^[a-z][a-z0-9_]*$`；`type` 在 7 类预设内；`mode` 在 `ai-image|code-draw`；`character`/`vfx` 必须有 `frames`；`icon`/`ui`/`background`/`tile` 默认单帧；尺寸必须在解析后 > 0；`scales` 为正整数。

- [ ] **Step 2: 实现输出矩阵**

`--json` 打印：

```json
{
  "project": "示例游戏",
  "assets": [
    {"id": "sample_icon", "type": "icon", "mode": "code-draw", "size": {"width": 128, "height": 128}, "scales": [1, 2], "frames": [null], "outputs": ["out/assets/icon/icon_sample_icon@1x.png", "out/assets/icon/icon_sample_icon@2x.png"]}
  ]
}
```

- [ ] **Step 3: 实现 `--prompts`**

为每个 `ai-image` 素材写 `prompts/<id>.md`，包含：

```markdown
# <name>（<id>）
- 类型：icon
- 目标尺寸：128 × 128（导出 1x / 2x）
- 背景：透明
- 生成模式：ai-image
- 回填路径：raw/icon/<id>/<frame>.png

## 风格块
16-bit pixel art; palette: #...; line: ...; lighting: ...; material: ...
Avoid: 3d render, blurry, ...

## 构图
<按类型给出的构图要求>

## 素材描述
<prompt 或 notes>
```

`--check-raw` 列出缺失的原始图，缺失时退出码 1。

- [ ] **Step 4: 验证**

```bash
cd template && python3 scripts/plan.py --json | head -20
cd template && python3 scripts/plan.py --prompts
```

Expected: 输出合法 JSON；生成 `prompts/sample_icon.md`。

- [ ] **Step 5: 提交**

```bash
git add template/scripts/plan.py && git commit -m "feat: 素材规划与 prompt 导出"
```

---

### Task 7: `render.py` 代码绘制渲染

**Files:**
- Create: `template/scripts/render.py`
- Create: `template/codegen/src/sample_icon.svg`（示例，带透明底与色板）

- [ ] **Step 1: 渲染约定**

- `codegen/src/<id>.svg`：单帧；多帧时优先找 `<id>__<frame>.svg`。
- `codegen/src/<id>.html`：渲染时附加 `?frame=<frame>&scale=<scale>`，AI 在页面里按参数绘制。
- 输出尺寸 = `width × max(scales)`，避免后处理放大。
- SVG：`magick -background none -density 384 in.svg -resize WxH! png:out.png`。
- HTML：Playwright `viewport={width,height}`、`device_scale_factor=scale`、`omit_background=True`。
- 字体与素材路径：HTML 通过 `file://` 加载，禁止外链。

- [ ] **Step 2: 实现 CLI**

```bash
python3 scripts/render.py                 # 渲染全部 code-draw 素材
python3 scripts/render.py --id sample_icon
python3 scripts/render.py --scale 4       # 覆盖最大倍数
```

渲染失败时打印命令、stderr 与目标路径，退出码 1。

- [ ] **Step 3: 写示例 SVG**

32×32 viewBox，透明底，3 色药水瓶，使用 style 色板中的 `#29E0FF` / `#FF4D8D` / `#F2F5FF`。

- [ ] **Step 4: 验证渲染**

```bash
cd template && python3 scripts/render.py --id sample_icon
python3 - <<'PY'
from PIL import Image
im = Image.open("raw/icon/sample_icon/sample_icon.png")
print(im.mode, im.size)
PY
```

Expected: `RGBA (256, 256)`（icon 128 × max scale 2）

- [ ] **Step 5: 提交**

```bash
git add template/scripts/render.py template/codegen/src/sample_icon.svg
git commit -m "feat: SVG/HTML 代码绘制渲染"
```

---

### Task 8: `atlas.py` 图集

**Files:**
- Create: `template/scripts/atlas.py`

- [ ] **Step 1: 实现 `build_atlas(images, columns, gap=0)`**

返回 `(atlas_image, meta)`；`meta.frames` 每项含 `index / name / x / y / w / h`；单元格尺寸取传入图的最大宽高；所有帧必须是 RGBA。

- [ ] **Step 2: 实现 CLI**

```bash
python3 scripts/atlas.py build out/assets/character/character_knight_*.png -o out/atlas/knight.png --columns 4
```

输出同名 `.json`。

- [ ] **Step 3: 提交**

```bash
git add template/scripts/atlas.py && git commit -m "feat: 精灵图集拼装"
```

---

### Task 9: `process.py` 后处理

**Files:**
- Create: `template/scripts/process.py`
- Test: `tests/test_process.py`

**函数：**
- `remove_solid_bg(im, tolerance=24)` → RGBA
- `trim_alpha(im, padding=0)` → RGBA
- `fit_canvas(im, width, height, padding, anchor, nearest)` → RGBA
- `quantize_to_palette(im, palette, tolerance)` → RGBA
- `scaled(im, factor, nearest)` → RGBA
- `run(project_root, only=None)` → dict 报告

- [ ] **Step 1: 写失败测试**

```python
import sys, unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))
import process

def solid(w, h, rgba):
    return Image.new("RGBA", (w, h), rgba)

class ProcessTest(unittest.TestCase):
    def test_remove_solid_bg(self):
        im = solid(10, 10, (255, 255, 255, 255))
        im.putpixel((5, 5), (255, 0, 0, 255))
        out = process.remove_solid_bg(im)
        self.assertEqual(out.getpixel((0, 0))[3], 0)
        self.assertEqual(out.getpixel((5, 5))[3], 255)

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

    def test_quantize_to_palette(self):
        im = Image.new("RGBA", (2, 1), (250, 10, 10, 255))
        im.putpixel((1, 0), (10, 250, 10, 255))
        out = process.quantize_to_palette(im, ["#FF0000", "#00FF00"])
        self.assertEqual(out.getpixel((0, 0))[:3], (255, 0, 0))
        self.assertEqual(out.getpixel((1, 0))[:3], (0, 255, 0))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

```bash
python3 -m unittest tests.test_process -v
```

- [ ] **Step 3: 实现后处理**

规则：

- 四角采样：3 个以上角落颜色距离 < tolerance 才判定为纯色背景并去除；去底后做 1px 边缘 despill（半透明像素的颜色向邻居不透明色靠拢）。背景（`background`）和平铺（`tile`）默认 `removeBg: false`，整块纹理的纯色填充是内容，不是背景。
- `trim_alpha` 用 alpha channel 的 `getbbox()`，四周加 `padding`，越界裁剪。
- `fit_canvas` 等比缩放到 `(W-2p, H-2p)` 内；`anchor` 支持 `center`、`bottom-center`、`top-center`；透明画布 RGBA。
- 调色板量化：枚举像素 RGB，映射到最近色（欧氏距离），alpha 不变；numpy 向量化。
- 多倍导出：`nearest` 由 `style.pixelGrid > 0` 或素材 `pixel: true` 决定。
- 帧：按 `frames` 顺序读取 `raw/<type>/<id>/<frame>.png`；无帧时读 `raw/<type>/<id>/<id>.png`。
- 精灵表：帧图先统一到 `cell × cell`，再 `atlas.build_atlas` 拼装，输出 `out/atlas/<id>.png/.json`。
- 报告写 `out/process_report.json`，含每个素材的处理动作、原始尺寸、输出文件、调色差。

- [ ] **Step 4: 跑测试**

```bash
python3 -m unittest tests.test_process -v
```

Expected: 4 tests PASS

- [ ] **Step 5: 提交**

```bash
git add template/scripts/process.py tests/test_process.py
git commit -m "feat: 素材后处理流水线"
```

---

### Task 10: `sheet.py` 联系表

**Files:**
- Create: `template/scripts/sheet.py`

- [ ] **Step 1: 实现**

- 扫描 `out/assets/**/*.png`（1x 优先，缺 1x 用最大倍数）。
- 每类一张 `out/sheets/<type>.jpg`，另拼 `out/sheet.jpg` 总览。
- 深灰底、棋盘格透明底提示、文件名 + 尺寸标签。
- 中文标签用 `common.font()`；找不到字体时退回默认字体。

- [ ] **Step 2: 验证**

```bash
cd template && python3 scripts/sheet.py
```

Expected: 生成 `out/sheet.jpg`，可打开查看。

- [ ] **Step 3: 提交**

```bash
git add template/scripts/sheet.py && git commit -m "feat: 素材联系表"
```

---

### Task 11: `check_assets.py` 质量闸门

**Files:**
- Create: `template/scripts/check_assets.py`
- Test: `tests/test_check.py`

- [ ] **Step 1: 写失败测试**

```python
import sys, unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))
import check_assets as c

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

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 实现检查项**

| 检查 | 判定 |
|---|---|
| 文件/尺寸 | 缺文件或尺寸不符 → ERROR |
| 透明 | 类型要求透明但无透明像素 → ERROR |
| 图标占比 | 主体包围盒较长边占画布 < 0.70 或 > 0.95 → WARN |
| 背景/平铺内容 | 不透明像素占比 < 30% → ERROR（防止被误抠空） |
| 角色基线 | 各帧最底非透明行差 > 2px → ERROR |
| 精灵表 | 尺寸、帧数与矩阵不符 → ERROR |
| 像素风 | 1x 图中半透明像素（0<a<255）占比 > 1% → WARN；颜色数 > 色板数 × 3 → WARN |
| 接缝 | `seam_error > 0.08` → ERROR（仅 `seamless: true`） |
| 九宫格 | `left+right >= width` 或 `top+bottom >= height` → ERROR |
| 色板 | 主色到最近色板色的平均距离 > 24 → WARN |

输出 `out/check_report.json`，打印 `ERROR / WARN / OK` 计数；有 ERROR 退出码 1。

- [ ] **Step 3: 跑测试**

```bash
python3 -m unittest tests.test_check -v
```

Expected: 3 tests PASS

- [ ] **Step 4: 提交**

```bash
git add template/scripts/check_assets.py tests/test_check.py
git commit -m "feat: 素材质量闸门"
```

---

### Task 12: `export.py` 打包交付

**Files:**
- Create: `template/scripts/export.py`

- [ ] **Step 1: 实现**

```bash
python3 scripts/export.py                    # 默认输出到 <工具目录>/outputs/<项目名>/
python3 scripts/export.py --dest /path/to/游戏素材
```

动作：

1. 复制 `out/assets/<type>/` → `<dest>/assets/<type>/`。
2. 复制 `out/atlas/` → `<dest>/assets/atlas/`。
3. 生成 `manifest.json`：素材 id/type/name/mode、尺寸、scales、frames、文件、palette、styleSha256、generatedAt。
4. 复制 `out/sheet.jpg` 与分类联系表 → `<dest>/预览/`。
5. 生成 `素材清单.md` 与 `使用说明.md`（图集键名、帧顺序、九宫格参数、命名规则）。
6. 若项目根目录有 `需求确认.md`，复制到 `<dest>/`。
7. `--copy-to <游戏工程 assets 路径>` 时把 `assets/` 同步过去。

- [ ] **Step 2: 验证**

```bash
cd template && python3 scripts/export.py --dest /tmp/game-assets-test
find /tmp/game-assets-test -maxdepth 3 -type f | sort
```

Expected: `assets/`、`预览/`、`manifest.json`、`素材清单.md`、`使用说明.md` 齐全。

- [ ] **Step 3: 提交**

```bash
git add template/scripts/export.py && git commit -m "feat: 交付物打包"
```

---

### Task 13: 文档（AGENTS / SKILL / README / references）

**Files:**
- Create: `SKILL.md`, `AGENTS.md`, `README.md`
- Create: `references/{需求问询,风格库,素材类型规范,尺寸与图集,生成方法,后处理,校验清单,踩坑记录}.md`

- [ ] **Step 1: 写 `SKILL.md`**

frontmatter `name: game-asset-maker`；description 覆盖「生成游戏素材/图标/角色/精灵表/场景/UI」等触发词；正文指向 AGENTS.md 与两种用法的路径约定。

- [ ] **Step 2: 写 `AGENTS.md`**

必须包含：最高目标、四条总原则、两种用法与路径约定、目录结构、输出目录规则、工具对照、十阶段工作流（0~9）、人工卡点（需求确认 / 风格锚点拍板）、节奏与验收底线、技术栈、脚本速查、参考文档索引、交付汇报格式。

关键硬规则：

- 没有完成需求确认与风格锚点拍板，不得批量生成。
- 禁止套用上一次项目的风格；必须基于 Style Card 并给用户看样图。
- 每张交付素材必须过 `check_assets.py`；有 ERROR 不得交付。
- 缺生图能力时只导出 prompt 包并阻塞，不自行用低质替代品凑数。
- 同一素材被否两次，停止自行决定，交给用户拍板或换生成模式。

- [ ] **Step 3: 写 8 份 references**

每份必须包含可执行清单与模板：

- `需求问询.md`：必问维度、选项、`需求确认.md` 模板。
- `风格库.md`：7 个内置方向 + 自定义 Style Card 写法 + 一致性策略。
- `素材类型规范.md`：6 类素材的构图、留白、光照、帧数、常见错误。
- `尺寸与图集.md`：预设表、覆盖规则、多倍导出、精灵表公式、九宫格、atlas JSON 格式。
- `生成方法.md`：AI 生图 prompt 模板（含正向/负向/style block）、代码绘制技法（SVG/HTML、像素网格、透明底、整数坐标）。
- `后处理.md`：去底策略、alpha 清理、缩放算法选择、调色量化、无缝修补。
- `校验清单.md`：自动闸门命令、联系表审图清单、交付前检查。
- `踩坑记录.md`：至少 10 条（透明底变黑、像素图被插值、精灵表帧错位、AI 图带文字水印、九宫格越界、tile 接缝、色板漂移、尺寸被拉伸、缺帧、路径含空格）。

- [ ] **Step 4: 写 `README.md`**

包含：一句话定位、效果说明（素材分类示例）、这是什么、快速开始（克隆用法 + Skill 用法）、配置示例、脚本速查、目录说明、FAQ、License。

- [ ] **Step 5: 提交**

```bash
git add SKILL.md AGENTS.md README.md references
git commit -m "docs: 工作规范与阶段手册"
```

---

### Task 14: 端到端自检与收尾

**Files:**
- Create: `tests/e2e_smoke.py`
- Modify: `README.md`（补自检命令）

- [ ] **Step 1: 写端到端脚本**

流程：复制 `template` 到临时目录 → 用示例 SVG 跑 `render` → `process` → `sheet` → `check` → `export --dest tmp` → 断言文件齐全。

```bash
python3 tests/e2e_smoke.py
```

Expected: 打印 `E2E OK`，退出码 0。

- [ ] **Step 2: 跑全部测试**

```bash
python3 -m unittest discover -s tests -v
python3 tests/e2e_smoke.py
python3 template/scripts/doctor.py || true
```

- [ ] **Step 3: 检查仓库完整性**

```bash
find . -not -path './.git/*' -not -path './outputs/*' -type f | sort
git status --short
```

Expected: 无未跟踪的临时文件；`outputs/` 只有 `.gitkeep`。

- [ ] **Step 4: 提交**

```bash
git add tests/e2e_smoke.py README.md
git commit -m "test: 端到端自检"
```

---

## 自检对照（spec → task）

| Spec 章节 | 覆盖任务 |
|---|---|
| 仓库形态与目录 | 1, 13 |
| 配置模型 | 2, 3, 4 |
| 双模生成 | 6, 7 |
| 风格一致性 | 2, 6, 9 |
| 工作流 | 13（AGENTS.md） |
| 后处理规则 | 9 |
| 校验闸门 | 11 |
| 交付物 | 12 |
| 错误处理 | 5, 6, 7, 11, 13 |
| 测试策略 | 4, 9, 11, 14 |
| MVP 验收 | 14 |
