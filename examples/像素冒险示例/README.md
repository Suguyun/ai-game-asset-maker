# 像素冒险示例

一个完全用 `code-draw` 生成的示例，覆盖：

- 角色 2 帧（待机、行走）+ 自动精灵表
- 3 个背包图标（红药水、铁剑、金币）
- 1 块可无缝平铺的草地 tile
- 1 块九宫格 UI 面板

不需要任何生图 API Key。

## 运行

```bash
# 1. 复制模板
mkdir -p /tmp/pixel-demo && cp -R <仓库>/template /tmp/pixel-demo/工程
cd /tmp/pixel-demo/工程

# 2. 覆盖示例配置与绘制代码
cp <仓库>/examples/像素冒险示例/{project.json,style.json,assets.yaml} .
cp <仓库>/examples/像素冒险示例/codegen/src/*.svg codegen/src/

# 3. 渲染、后处理、校验、打包
python3 scripts/plan.py
python3 scripts/render.py --force
python3 scripts/process.py
python3 scripts/check_assets.py
python3 scripts/sheet.py
python3 scripts/export.py --dest /tmp/pixel-demo/交付
```

打开 `/tmp/pixel-demo/交付/预览/联系表.jpg` 查看成品。

## 改风格

只改 `style.json`：

```json
{
  "palette": ["#2B2D42", "#FF6B9D", "#FFD166", "#06D6A0", "#4CC9F0", "#FFFFFF"],
  "line": "3px rounded dark outline",
  "lighting": "soft cel shading, top-left light",
  "pixelGrid": 0,
  "paletteLock": false
}
```

然后重跑 `process.py`、`check_assets.py`、`sheet.py`。绘制代码里的颜色是写死的示例色板，改色板后要么全局替换 SVG 里的十六进制色值，要么把 `paletteLock` 设为 `true` 让后处理量化到新色板。

## 改尺寸

改 `project.json`：

```json
{ "sizes": { "icon": { "width": 512, "height": 512, "scales": [1, 2, 4] } } }
```

或改单个素材的 `assets.yaml`：

```yaml
- id: potion_red
  size: { preset: icon, width: 128, height: 128, scales: [1, 2, 4] }
```

重跑第 2~3 步即可。

## 文件说明

```
project.json        项目配置（尺寸、输出）
style.json          风格卡（色板、描边、光照、材质）
assets.yaml         素材清单（6 个素材）
codegen/src/*.svg   代码绘制源文件
```

角色多帧用 `<id>__<frame>.svg` 命名；其余单帧用 `<id>.svg`。
