"""打包交付：把 out/ 下的成品整理成素材包，并生成 manifest 与使用说明。

用法：
    python3 scripts/export.py
    python3 scripts/export.py --dest /path/to/游戏素材
    python3 scripts/export.py --copy-to /path/to/游戏工程/assets --force
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def default_dest(root, project):
    root = common.project_root(root)
    if root.name == "工程":
        return root.parent
    raw_name = str(project.get("name") or "游戏素材")
    safe_name = re.sub(r"[^\w一-鿿.-]+", "_", raw_name).replace("..", "__").strip("._-")
    return root.parent / "outputs" / (safe_name or "游戏素材")


def export(root=None, dest=None, copy_to=None, force=False, skip_check=False, allow_missing=False):
    root_path = common.project_root(root)
    project = common.load_project(root_path)
    style = common.load_style(project, root_path)
    assets = common.load_assets(project, root_path)
    presets = common.load_presets(project, root_path)
    dest = Path(dest).expanduser().resolve() if dest else default_dest(root_path, project)
    dest = dest.resolve()
    common.ensure_dir(dest)

    # 交付闸门：没有最新的 0-ERROR 校验报告，不允许打包
    check_path = root_path / "out" / "check_report.json"
    if not skip_check:
        if not check_path.exists():
            print("ERROR 缺少 out/check_report.json；先运行 check_assets.py", file=sys.stderr)
            return 1
        try:
            check_report = json.loads(check_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"ERROR 无法读取 check_report.json：{exc}", file=sys.stderr)
            return 1
        if int(check_report.get("summary", {}).get("ERROR", 0)) > 0:
            print("ERROR 校验报告仍有 ERROR，修到 0 ERROR 再交付", file=sys.stderr)
            return 1
        watched = [
            *(p for p in (root_path / "out" / "assets").rglob("*") if p.is_file()),
            *(p for p in (root_path / "project.json", root_path / "assets.yaml", Path(style["_path"])) if p.exists()),
        ]
        newest = max((p.stat().st_mtime for p in watched), default=0)
        if newest > check_path.stat().st_mtime + 2:
            print("ERROR check_report.json 早于最新成品或配置；重跑 check_assets.py（或加 --skip-check）", file=sys.stderr)
            return 1

    expected = []
    for asset in assets:
        frames = common.frames_of(asset)
        size = common.resolve_size(asset, project, presets, len(frames), style=style)
        for frame in frames:
            for scale in size["scales"]:
                expected.append(common.output_path(root_path, size, frame, scale))
    missing = [path for path in expected if not path.exists()]
    if missing and not allow_missing:
        for path in missing:
            print(f"ERROR 缺成品 {path.relative_to(root_path)}", file=sys.stderr)
        print("补齐后重新运行 process.py / check_assets.py；或加 --allow-missing 强制继续", file=sys.stderr)
        return 1

    copy_target = None
    if copy_to:
        target_path = Path(copy_to).expanduser().resolve()
        copy_target = target_path if target_path.name == "assets" else target_path / "assets"
        if copy_target.exists() and any(copy_target.iterdir()) and not force:
            print(f"ERROR 目标目录已有文件：{copy_target}", file=sys.stderr)
            print("确认要覆盖请加 --force；建议先导出到交付目录让用户确认", file=sys.stderr)
            return 1

    warnings = []
    manifest_assets = []
    asset_rows = []

    for asset in assets:
        frames = common.frames_of(asset)
        size = common.resolve_size(asset, project, presets, len(frames), style=style)
        files = []
        for frame in frames:
            for scale in size["scales"]:
                src = common.output_path(root_path, size, frame, scale)
                if not src.exists():
                    warnings.append(f"缺成品：{src.relative_to(root_path)}")
                    continue
                rel = Path("assets") / size["type"] / src.name
                target = dest / rel
                common.ensure_dir(target.parent)
                shutil.copy2(src, target)
                files.append(str(rel))

        atlas_rel = None
        atlas_meta_rel = None
        if len(frames) > 1:
            atlas_img = common.atlas_dir(root_path) / f"{asset['id']}.png"
            atlas_json = common.atlas_dir(root_path) / f"{asset['id']}.json"
            if atlas_img.exists() and atlas_json.exists():
                atlas_rel = Path("assets") / "atlas" / atlas_img.name
                atlas_meta_rel = Path("assets") / "atlas" / atlas_json.name
                common.ensure_dir((dest / atlas_rel).parent)
                shutil.copy2(atlas_img, dest / atlas_rel)
                shutil.copy2(atlas_json, dest / atlas_meta_rel)
                files += [str(atlas_rel), str(atlas_meta_rel)]
            else:
                warnings.append(f"{asset['id']}：缺图集，先跑 process.py")

        manifest_assets.append({
            "id": asset["id"],
            "name": size["name"],
            "type": size["type"],
            "mode": size["mode"],
            "size": {
                "width": size["width"],
                "height": size["height"],
                "cell": size.get("cell"),
                "columns": size["columns"],
                "rows": size["rows"],
                "padding": size["padding"],
                "anchor": size["anchor"],
                "transparent": size["transparent"],
                "seamless": size["seamless"],
                "nineSlice": size.get("nineSlice"),
            },
            "scales": size["scales"],
            "frames": [f for f in frames if f],
            "files": files,
            "atlas": str(atlas_rel) if atlas_rel else None,
            "atlasMeta": str(atlas_meta_rel) if atlas_meta_rel else None,
        })
        asset_rows.append((asset["id"], size["name"], size["type"], size["mode"],
                           f"{size['width']}x{size['height']}", ",".join(map(str, size["scales"])),
                           ",".join(str(f) for f in frames if f) or "-"))

    manifest = {
        "project": project.get("name"),
        "style": style.get("name"),
        "styleSha256": common.sha256_file(style["_path"]) if Path(style.get("_path", "")).exists() else None,
        "engine": project.get("output", {}).get("engine", "generic"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "assets": manifest_assets,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    preview = dest / "预览"
    if (root_path / "out" / "sheet.jpg").exists():
        common.ensure_dir(preview)
        shutil.copy2(root_path / "out" / "sheet.jpg", preview / "联系表.jpg")
    else:
        warnings.append("缺 out/sheet.jpg，先跑 sheet.py")
    sheets_dir = root_path / "out" / "sheets"
    if sheets_dir.exists():
        common.ensure_dir(preview / "分类")
        for sheet in sorted(sheets_dir.glob("*.jpg")):
            shutil.copy2(sheet, preview / "分类" / sheet.name)

    for confirm in (root_path / "需求确认.md", root_path.parent / "需求确认.md"):
        if confirm.exists():
            shutil.copy2(confirm, dest / "需求确认.md")
            break

    write_asset_list(dest, project, style, asset_rows)
    write_usage(dest, project, style, manifest_assets)

    if copy_target:
        common.ensure_dir(copy_target)
        shutil.copytree(dest / "assets", copy_target, dirs_exist_ok=True)
        print(f"已同步素材到 {copy_target}")

    for warning in warnings:
        print(f"WARN {warning}", file=sys.stderr)
    print(f"交付目录 {dest}")
    print(f"  {len(manifest_assets)} 个素材，{sum(len(a['files']) for a in manifest_assets)} 个文件")
    return 0


def write_asset_list(dest, project, style, rows):
    lines = [
        f"# {project.get('name')} · 素材清单",
        "",
        f"- 风格：{style.get('name')}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| id | 名称 | 类型 | 模式 | 单帧尺寸 | 倍数 | 帧 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    (dest / "素材清单.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_usage(dest, project, style, assets):
    lines = [
        f"# {project.get('name')} · 素材包使用说明",
        "",
        "## 目录",
        "",
        "- `assets/<类型>/`：按类型分好的 PNG。",
        "- `assets/atlas/`：多帧素材的精灵表与坐标 JSON。",
        "- `manifest.json`：全部素材的机器可读清单。",
        "- `预览/`：联系表，方便快速浏览。",
        "",
        "## 命名规则",
        "",
        "`<类型>_<id>[_<帧>]@<倍数>x.png`，例如 `icon_potion_red@2x.png`、`character_knight_walk@1x.png`。",
        "",
        "## 使用要点",
        "",
        "- 像素风素材导入引擎时，缩放过滤选择 Nearest / Point，关闭压缩和 mipmap，避免糊边。",
        "- 透明底 PNG 直接用；不透明背景没有 alpha 通道。",
        "- 多帧素材同时提供单帧 PNG 与精灵表，帧顺序见下表和 `assets/atlas/<id>.json`。",
        "",
    ]
    for asset in assets:
        if not asset["frames"] or len(asset["frames"]) < 2:
            continue
        cell = asset["size"].get("cell")
        cell_text = f"{cell}×{cell}" if cell else f"{asset['size']['width']}×{asset['size']['height']}"
        lines += [
            f"### {asset['name']}（{asset['id']}）",
            "",
            f"- 帧顺序：{', '.join(str(f) for f in asset['frames'])}",
            f"- 精灵表：`{asset['atlas']}`",
            f"- 图集坐标：`{asset['atlasMeta']}`（单元格 {cell_text}，{asset['size']['columns']} 列）",
            "",
        ]
    for asset in assets:
        nine = asset["size"].get("nineSlice")
        if nine:
            lines += [
                f"### {asset['name']}（{asset['id']}）九宫格",
                "",
                f"left={nine.get('left')} right={nine.get('right')} top={nine.get('top')} bottom={nine.get('bottom')}",
                "",
            ]
    lines += [
        "## 重新生成",
        "",
        "```bash",
        "cd 工程",
        "python3 scripts/plan.py --check-raw",
        "python3 scripts/process.py",
        "python3 scripts/check_assets.py",
        "python3 scripts/sheet.py",
        "python3 scripts/export.py",
        "```",
        "",
        f"风格：{style.get('name')}；改 `style.json` 后重跑上述命令即可整套换风格。",
    ]
    (dest / "使用说明.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="打包素材交付物")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--dest", help="交付目录；默认 outputs/<项目名> 或 工程 的上级目录")
    ap.add_argument("--copy-to", help="额外同步一份 assets/ 到游戏工程")
    ap.add_argument("--force", action="store_true", help="--copy-to 目标已有文件时允许覆盖")
    ap.add_argument("--skip-check", action="store_true", help="跳过 check_report.json 的 0-ERROR 闸门")
    ap.add_argument("--allow-missing", action="store_true", help="缺成品时仍然继续导出")
    args = ap.parse_args()
    try:
        return export(args.project, args.dest, args.copy_to, args.force, args.skip_check, args.allow_missing)
    except common.ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
