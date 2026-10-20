"""素材规划：校验清单、计算输出矩阵、导出 prompt 包。

用法：
    python3 scripts/plan.py --json
    python3 scripts/plan.py --prompts
    python3 scripts/plan.py --check-raw
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

COMPOSITION = {
    "character": "单个角色全身，正面或 3/4 视角，脚底贴齐画面底部，居中，四肢轮廓清晰；同一角色的各帧必须保持相同身高、头身比和服装细节。",
    "sprite": "单个角色动作帧，视角与尺寸统一，角色居中，脚底基线一致；每帧只表现一个动作瞬间，帧与帧之间身体锚点不漂移。",
    "icon": "单个道具/技能主体，居中，剪影清晰，主体占画布 70%~85%，四周留均匀空白，不出现场景背景。",
    "background": "完整场景背景，无 UI、无文字、无水印；主体信息避开画面中央，方便叠加角色和界面。",
    "tile": "无缝平铺纹理，正视角，光照均匀，四边可首尾相接；不要出现明显的中心构图或方向性阴影。",
    "ui": "可九宫格拉伸的 UI 面板/按钮，四边设计一致，四角细节完整；默认不出现文字，文字层由游戏引擎渲染。",
    "vfx": "单个特效序列帧，透明背景，效果主体居中；各帧按时间顺序排列，尺寸、锚点和配色保持一致。",
}


def validate_asset(asset, index):
    errors = []
    asset_id = asset.get("id")
    if not asset_id or not ID_RE.match(str(asset_id)):
        errors.append(f"第 {index + 1} 个素材的 id 不合法（需小写蛇形）：{asset_id!r}")
    if asset.get("type") not in common.VALID_TYPES:
        errors.append(f"{asset_id}：type 不合法：{asset.get('type')!r}")
    if asset.get("mode") not in common.VALID_MODES:
        errors.append(f"{asset_id}：mode 不合法：{asset.get('mode')!r}")
    frames = asset.get("frames") or []
    if isinstance(frames, str):
        frames = [frames]
    if asset.get("type") in ("character", "vfx") and not frames:
        errors.append(f"{asset_id}：{asset.get('type')} 必须声明 frames")
    if len(frames) != len(set(frames)):
        errors.append(f"{asset_id}：frames 有重复项")
    return errors


def build_matrix(project, style, assets, presets, root):
    errors, warnings, rows = [], [], []
    seen = set()
    for index, asset in enumerate(assets):
        asset_errors = validate_asset(asset, index)
        errors.extend(asset_errors)
        asset_id = asset.get("id")
        if asset_id in seen:
            asset_errors.append(f"素材 id 重复：{asset_id}")
            errors.append(asset_errors[-1])
        seen.add(asset_id)
        if asset_errors:
            continue
        frames = common.frames_of(asset)
        try:
            size = common.resolve_size(asset, project, presets, len(frames), style=style)
        except common.ConfigError as exc:
            errors.append(str(exc))
            continue

        outputs = []
        for frame in frames:
            for scale in size["scales"]:
                rel = common.output_path(root, size, frame, scale).relative_to(common.project_root(root))
                outputs.append(str(rel))
        atlas = None
        if len(frames) > 1:
            atlas = {
                "image": str(Path("out/atlas") / f"{asset_id}.png"),
                "json": str(Path("out/atlas") / f"{asset_id}.json"),
                "columns": size["columns"],
                "cell": [size.get("cell") or size["width"], size.get("cell") or size["height"]],
            }

        missing_raw = [
            str(common.raw_path(root, size, frame).relative_to(common.project_root(root)))
            for frame in frames
            if not common.raw_path(root, size, frame).exists()
        ]
        if missing_raw:
            warnings.append(f"{asset_id}：缺原始图 {len(missing_raw)} 张")
        if asset.get("mode") == "code-draw":
            src_dir = common.project_root(root) / "codegen" / "src"
            names = [f"{asset_id}{ext}" for ext in (".svg", ".html")]
            names += [f"{asset_id}__{frame}{ext}" for frame in frames if frame for ext in (".svg", ".html")]
            if not any((src_dir / name).exists() for name in names):
                warnings.append(
                    f"{asset_id}：code-draw 源文件不存在"
                    f"（先写 codegen/src/{asset_id}.svg/.html，多帧可用 {asset_id}__<frame>.svg）"
                )

        rows.append({
            "id": asset_id,
            "name": size["name"],
            "type": size["type"],
            "mode": size["mode"],
            "size": {"width": size["width"], "height": size["height"], "cell": size.get("cell"),
                     "columns": size["columns"], "rows": size["rows"], "padding": size["padding"],
                     "anchor": size["anchor"], "transparent": size["transparent"],
                     "seamless": size["seamless"], "nineSlice": size.get("nineSlice")},
            "scales": size["scales"],
            "frames": frames,
            "outputs": outputs,
            "atlas": atlas,
            "missing_raw": missing_raw,
        })
    return {"project": project.get("name"), "style": style.get("name"), "assets": rows}, errors, warnings


def prompt_text(root, asset, size, style):
    frames = common.frames_of(asset)
    lines = [
        f"# {size['name']}（{asset['id']}）",
        "",
        f"- 类型：{size['type']}",
        f"- 目标尺寸：{size['width']} × {size['height']}",
        f"- 导出倍数：{', '.join(str(s) + 'x' for s in size['scales'])}",
        f"- 背景：{'透明' if size['transparent'] else '不透明'}",
        f"- 生成模式：ai-image",
        f"- 帧：{', '.join(frames) if frames[0] else '单帧'}",
        "",
        "## 回填路径",
        "",
    ]
    for frame in frames:
        rel = common.raw_path(root, size, frame).relative_to(common.project_root(root))
        lines.append(f"- `{rel}`")
    biggest = max(size["scales"])
    biggest_w = int(size.get("cell") or size["width"]) * biggest
    biggest_h = int(size.get("cell") or size["height"]) * biggest
    lines += [
        "",
        f"> 建议直接生成 {biggest_w}×{biggest_h}px 的高分辨率图，脚本会负责裁切、补边和缩小；"
        "如果工具只能出固定尺寸，按目标尺寸生成即可。",
        "",
        "## 风格块",
        "",
        common.style_block(style),
        "",
        "## 构图要求",
        "",
        COMPOSITION.get(size["type"], ""),
        "",
        "## 素材描述",
        "",
        asset.get("prompt") or asset.get("notes") or "（未填写，请在生成前补充具体描述：主体、动作、朝向、材质、关键细节）",
        "",
    ]
    return "\n".join(lines)


def write_prompts(root, project, style, assets, presets):
    root = common.project_root(root)
    out_dir = common.ensure_dir(root / "prompts")
    count = 0
    for asset in assets:
        if asset.get("mode") != "ai-image":
            continue
        frames = common.frames_of(asset)
        size = common.resolve_size(asset, project, presets, len(frames), style=style)
        path = out_dir / f"{asset['id']}.md"
        path.write_text(prompt_text(root, asset, size, style), encoding="utf-8")
        print(f"写出 {path}")
        count += 1
    print(f"共 {count} 份 prompt")
    return count


def main():
    ap = argparse.ArgumentParser(description="游戏素材规划")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--json", action="store_true", help="打印输出矩阵 JSON")
    ap.add_argument("--prompts", action="store_true", help="为 ai-image 素材导出 prompt 包")
    ap.add_argument("--check-raw", action="store_true", help="检查原始图是否齐全")
    args = ap.parse_args()

    try:
        project = common.load_project(args.project)
        style = common.load_style(project, args.project)
        assets = common.load_assets(project, args.project)
        presets = common.load_presets(project, args.project)
    except common.ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2

    matrix, errors, warnings = build_matrix(project, style, assets, presets, args.project)
    for warning in warnings:
        print(f"WARN  {warning}", file=sys.stderr)
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    if errors:
        return 1

    if args.json:
        print(json.dumps(matrix, ensure_ascii=False, indent=2))
    else:
        print(f"项目：{matrix['project']}  风格：{matrix['style']}  素材：{len(matrix['assets'])}")
        for row in matrix["assets"]:
            print(f"  {row['id']:<16}{row['type']:<12}{row['mode']:<10}"
                  f"{row['size']['width']}x{row['size']['height']}  scales={row['scales']}  frames={len(row['frames'])}")

    if args.prompts:
        write_prompts(args.project, project, style, assets, presets)

    if args.check_raw:
        missing = [(row["id"], row["missing_raw"]) for row in matrix["assets"] if row["missing_raw"]]
        if missing:
            for asset_id, files in missing:
                print(f"MISSING {asset_id}：{', '.join(files)}", file=sys.stderr)
            return 1
        print("原始图齐全")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
