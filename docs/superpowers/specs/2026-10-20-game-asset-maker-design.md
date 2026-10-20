# 游戏素材生成器 · 设计文档

日期：2026-10-20
状态：已确认（用户批准）

## 1. 一句话目标

用户用一句话说明游戏和素材需求，AI 按仓库规范完成：需求问询 → 风格锚点 → 批量生成 → 后处理切图 → 自动校验 → 交付一整套可直接进游戏工程的素材包。风格与尺寸都由项目内可编辑文件控制，不接外部生图 API。

## 2. 非目标

- 不做独立 Web 应用，不做在线服务，不做账号体系。
- 不接 Gemini / OpenAI / ComfyUI 等外部生图 API。生图依赖 AI 编程工具自带的图像生成能力；没有时导出 prompt 包，由人工回填。
- 第一版不做引擎专用适配（Godot `.tres`、Cocos `.plist`、Unity `.meta`），统一输出通用 PNG + atlas JSON + manifest。
- 不做动画编辑器、关卡编辑器、运行时渲染库。

## 3. 仓库形态

与 `ai-promo-video-maker` 同款：Agent 工作流仓库。

- `SKILL.md`：Skill 入口，指向 AGENTS.md。
- `AGENTS.md`：完整工作规范，AI 必须逐步执行。
- `references/`：各阶段详细手册。
- `library/`：内置风格卡与尺寸预设。
- `template/`：新项目唯一骨架（配置 + 脚本 + 空目录）。
- `outputs/`：本项目产出的素材包（gitignored）。

两种用法与参考项目一致：

| 占位符 | 克隆用法 | Skill 用法 |
|---|---|---|
| `<工具目录>` | 仓库根目录 | Skill 安装目录 |
| `<输出目录>` | `<工具目录>/outputs` | 当前工作区根目录下的 `游戏素材` |

## 4. 架构：配置驱动的双模生成流水线

每个项目只有三份可编辑配置：

1. `style.json`：Style Card，风格的唯一真相。
2. `project.json`：项目信息、尺寸覆盖、输出格式。
3. `assets.yaml`：素材清单，逐项声明类型、尺寸、帧、生成模式。

脚本负责所有确定性工作：规划、渲染代码绘制素材、去底、裁切、统一画布、多倍导出、精灵表切分、图集、联系表、校验、打包。AI 负责填配置、写 prompt、写绘制代码、审图与修复。

### 4.1 生成模式

每个素材声明 `mode`：

- `ai-image`：AI 工具具备生图能力时直接生成到 `raw/`；不具备时 `plan.py --prompts` 导出 `prompts/<id>.md`，包含目标尺寸、透明底要求、构图、编译后的 style block、负向词和回填路径。用户回填到 `raw/` 后流程继续。
- `code-draw`：AI 在 `codegen/src/<id>.svg` 或 `<id>.html` 写绘制代码。`render.py` 用 ImageMagick 渲染 SVG、用 Playwright 渲染 HTML，按目标尺寸输出 PNG。

两种模式产出统一落到 `raw/<type>/<id>/<frame>.png`，后处理完全共用。

### 4.2 风格一致性

1. Style Card 编译成统一 style block，注入每一次生图 prompt。
2. 开工先做 1 张角色 + 1 个图标作为风格锚点，用户拍板后才批量。
3. 后处理按 Style Card 调色板做颜色量化锁定（`paletteLock`）；代码绘制直接引用同一份色板 token。
4. 校验阶段比较主色与色板的距离，超容差即判定风格漂移。

## 5. 目录结构

```
ai-game-asset-maker/
├── SKILL.md
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── images/
│   └── superpowers/specs/
├── references/
│   ├── 需求问询.md
│   ├── 风格库.md
│   ├── 素材类型规范.md
│   ├── 尺寸与图集.md
│   ├── 生成方法.md
│   ├── 后处理.md
│   ├── 校验清单.md
│   └── 踩坑记录.md
├── library/
│   ├── styles/
│   │   ├── 像素冒险.json
│   │   ├── Q版卡通.json
│   │   ├── 暗黑奇幻.json
│   │   ├── 赛博霓虹.json
│   │   ├── 手绘水彩.json
│   │   ├── 扁平矢量.json
│   │   └── 写实厚涂.json
│   └── presets/sizes.json
├── template/
│   ├── project.json
│   ├── style.json
│   ├── assets.yaml
│   ├── requirements.txt
│   ├── raw/.gitkeep
│   ├── codegen/src/.gitkeep
│   ├── prompts/.gitkeep
│   ├── out/.gitkeep
│   └── scripts/
│       ├── common.py
│       ├── doctor.py
│       ├── plan.py
│       ├── render.py
│       ├── process.py
│       ├── atlas.py
│       ├── sheet.py
│       ├── check_assets.py
│       └── export.py
├── tests/
│   ├── test_process.py
│   ├── test_sizes.py
│   └── test_check.py
└── outputs/            # gitignored
```

## 6. 配置模型

### 6.1 `style.json`

```json
{
  "name": "赛博像素",
  "keywords": ["16-bit pixel art", "neon rim light", "dark navy background"],
  "palette": ["#0B1020", "#1B2A4A", "#F2F5FF", "#29E0FF", "#FF4D8D"],
  "line": "1px dark outline, no anti-aliasing",
  "lighting": "top-left key light, hard shadow",
  "material": "matte surface with emissive accents",
  "referenceImages": [],
  "avoid": ["3d render", "blurry", "photo texture", "text", "watermark"],
  "pixelGrid": 32,
  "paletteLock": true,
  "background": "transparent"
}
```

字段全部可改；`palette` 可增删色值；`referenceImages` 相对项目根目录。

### 6.2 `project.json`

```json
{
  "name": "星港防线",
  "style": "style.json",
  "sizes": {
    "icon": { "width": 256, "height": 256, "scales": [1, 2], "padding": 8 },
    "sprite": { "cell": 64, "columns": 4, "transparent": true }
  },
  "output": { "format": "png", "engine": "generic" },
  "defaults": { "mode": "ai-image", "padding": 8, "trim": true, "anchor": "center" }
}
```

- `sizes` 按素材类型覆盖 `library/presets/sizes.json`。
- 素材项里的 `size` 可引用预设名或直接写对象，再覆盖任意字段。
- 尺寸对象支持：`width`、`height`、`cell`、`scales`、`padding`、`trim`、`anchor`、`transparent`、`columns`、`gap`、`frames`、`seamless`、`nineSlice`。

### 6.3 `assets.yaml`

```yaml
assets:
  - id: knight
    type: character
    name: 骑士
    mode: ai-image
    size: { preset: character, width: 768, height: 768 }
    frames: [idle, walk, attack]
    prompt: "a brave knight in heavy armor, full body, front-facing"

  - id: potion_red
    type: icon
    name: 红色药水
    mode: code-draw
    size: { preset: icon, width: 128, height: 128, scales: [1, 2, 4] }
    notes: "圆形瓶身，红色药水，白色高光"
```

`type` 取值：`character`、`icon`、`background`、`tile`、`ui`、`vfx`。
`id` 使用小写蛇形命名，作为文件名与图集键。

## 7. 工作流（AGENTS.md，十个阶段 0~9）

0. **环境体检**：`doctor.py` 检查 Python 3.9+、Pillow、numpy、PyYAML；代码绘制额外检查 ImageMagick / Playwright。只检查不安装。
1. **预调研**：游戏类型、视角与透视、目标引擎、现有一手素材、命名习惯、分辨率目标。
2. **需求问询（★人工卡点）**：素材清单（类型/数量/名字/尺寸/用途）、风格方向（3~4 张样图）、尺寸规格、交付格式、验收方式。产出 `需求确认.md`，用户明确同意后才开工。
3. **建项目**：复制 `template` 到 `<输出目录>/<中文项目名>/工程/`，写三份配置。
4. **风格锚点（★人工卡点）**：先做 1 张角色 + 1 个图标，拼联系表让用户拍板；定稿后批量。
5. **批量生成**：`plan.py` 校验清单并计算输出矩阵；`plan.py --prompts` 导出 prompt 包；按模式产出 `raw/`。
6. **后处理**：`process.py` 去底 → 裁切 → 补边 → 统一画布 → 多倍导出 → 精灵表 → 调色锁定。
7. **校验循环**：`check_assets.py` 自动闸门 + `sheet.py` 联系表逐张审图，修到全过。
8. **导出交付**：`export.py` 输出分类目录、atlas JSON、manifest、预览图、使用说明。
9. **改版**：记录用户原话 → 只改 style/size/受影响素材 → 备份旧版再交付。

## 8. 后处理规则

| 步骤 | 规则 |
|---|---|
| 去底 | 有 alpha 直接用；无 alpha 按四角采样纯色 key 去底并做边缘 despill；失败标记待人工 |
| 裁切/补边 | trim 透明边 → 按 `anchor`（默认 center，角色可设 bottom-center）补到目标画布 → `padding` |
| 缩放 | 像素风 nearest，其余 lanczos；按 `scales` 生成多倍图 |
| 调色锁定 | `paletteLock` 开启时量化到 Style Card 色板，报告平均色差 |
| 精灵表 | 按 `columns`/`gap` 拼装，输出每帧坐标 |
| 九宫格 | UI 输出 `nineSlice` 元数据并校验边距 |
| 无缝检测 | tile 做四向 wrap 比较，输出接缝误差分数 |
| 命名 | `<type>_<id>_<frame>@<scale>x.png`；无帧时省略帧段 |

## 9. 校验闸门

- 文件齐全、命名合法、无缺失帧。
- 每档尺寸正确、透明通道存在、透明边距均匀。
- 图标主体占画布 70%~85%。
- 角色各帧同画布、脚底基线一致。
- 精灵表行列、帧数、单元格尺寸正确。
- 像素风无抗锯齿半透明、颜色数不超色板。
- 背景分辨率达标、无文字水印（AI 审图确认）。
- tile 接缝误差低于阈值。
- UI 九宫格边距合法。
- 主色与 Style Card 色板距离在容差内。
- 输出 `out/sheet.jpg` 联系表，AI 逐张审图并记录结论。

校验失败时给出可执行修复建议；同一素材被否两次，切换生成模式或请用户提供参考图。

## 10. 交付物

```
outputs/<中文项目名>/
├── 需求确认.md
├── 素材清单.md
├── 设计说明.md
├── assets/
│   ├── character/ icon/ background/ tile/ ui/ vfx/
│   ├── atlas/<id>.json
│   └── manifest.json
├── 预览/
│   ├── 联系表.jpg
│   └── <分类>-预览.jpg
└── 工程/            # template 副本：配置、prompts、codegen、脚本、raw/out
```

`manifest.json` 包含：素材 id、type、name、尺寸、scales、帧列表、文件路径、色板、style 指纹、生成时间。

## 11. 错误处理

| 情况 | 处理 |
|---|---|
| 缺原始图 | 阻塞，列出缺失项和对应 prompt 文件路径 |
| 尺寸不符 | 先自动适配，报告注明原始尺寸与适配动作 |
| 去底失败 | 提示改用纯色背景重生，或人工抠图后重跑 |
| 代码绘制渲染失败 | 打印渲染日志与目标路径，不静默跳过 |
| 风格漂移 | 重新用锚点图校准；连续两次仍失败则请用户给参考图 |
| tile 接缝超标 | 建议重生成或使用 offset-seam 修补，并在报告中标注 |
| 同一素材被否两次 | 换生成模式或停止自行决定，交由用户拍板 |

## 12. 测试策略

- `tests/test_sizes.py`：预设合并、覆盖优先级、多倍尺寸计算。
- `tests/test_process.py`：trim/补边/缩放/调色量化/精灵表拼装的尺寸与像素正确性（用合成图）。
- `tests/test_check.py`：尺寸、透明、接缝、九宫格校验的通过/失败分支。
- 端到端自检：用合成素材跑 `plan → process → check → export`，确认产物结构完整。

## 13. MVP 验收标准

1. 克隆仓库后按 README 安装依赖，`python3 template/scripts/doctor.py` 能给出准确体检结果。
2. 新建项目、修改 `style.json` 的色板与 `project.json` 的尺寸后，`plan.py` 输出的矩阵随之变化。
3. `code-draw` 模式能用 SVG 渲染出指定尺寸的透明 PNG。
4. `process.py` 能对一批原始图完成去底、裁切、补边、多倍导出、精灵表拼装。
5. `check_assets.py` 能捕获尺寸错误、缺帧、接缝超标、九宫格越界，并输出联系表。
6. `export.py` 产出完整的 `assets/`、`atlas/`、`manifest.json`、预览图。
7. 仓库文档齐全，AI 仅凭 `AGENTS.md` + `references/` 就能独立执行完整流程。

## 14. 后续扩展（不在第一版）

- 引擎适配：Godot / Cocos Creator / Unity。
- 更多 code-draw 模板：像素角色生成器、地图 tile 生成器、UI 九宫格生成器。
- 外部生图 Provider 适配层。
- 本地网页画廊。
