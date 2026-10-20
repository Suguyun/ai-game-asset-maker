"""质量闸门：尺寸、透明、边距、基线、图集、接缝、九宫格、像素风、色板。

用法：
    python3 scripts/check_assets.py
    python3 scripts/check_assets.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import process  # noqa: E402

PALETTE_TOLERANCE = 24.0
SEAM_TOLERANCE = 0.08


def alpha_bbox(im):
    return im.convert("RGBA").getchannel("A").getbbox()


def fill_ratio(im):
    bbox = alpha_bbox(im)
    if not bbox:
        return 0.0
    width, height = im.size
    return max((bbox[2] - bbox[0]) / width, (bbox[3] - bbox[1]) / height)


def seam_error(im):
    """左右边、上下边的平均色差（含 alpha，0~1）。无缝平铺时四边应当接近。"""
    arr = np.array(im.convert("RGBA")).astype(np.float32)
    if arr.shape[0] < 2 or arr.shape[1] < 2:
        return 1.0
    left_right = np.abs(arr[:, 0, :] - arr[:, -1, :]).mean()
    top_bottom = np.abs(arr[0, :, :] - arr[-1, :, :]).mean()
    return float(((left_right + top_bottom) / 2.0) / 255.0)


def semi_transparent_ratio(im):
    alpha = np.array(im.convert("RGBA"))[..., 3]
    if alpha.size == 0:
        return 0.0
    return float(((alpha > 0) & (alpha < 255)).sum() / alpha.size)


def unique_colors(im):
    arr = np.array(im.convert("RGBA"))
    opaque = arr[arr[..., 3] > 0][:, :3]
    return len({tuple(pixel) for pixel in opaque})


def nine_slice_ok(width, height, nine):
    if not nine:
        return True
    return (
        int(nine.get("left", 0)) + int(nine.get("right", 0)) < int(width)
        and int(nine.get("top", 0)) + int(nine.get("bottom", 0)) < int(height)
    )


def add(checks, level, code, message):
    checks.append({"level": level, "code": code, "message": message})


def check_asset(root, project, style, asset, presets):
    frames = common.frames_of(asset)
    size = common.resolve_size(asset, project, presets, len(frames), style=style)
    cell = size.get("cell")
    frame_w = int(cell or size["width"])
    frame_h = int(cell or size["height"])
    checks = []
    one_x = {}
    chosen_scale = {}

    for frame in frames:
        for scale in size["scales"]:
            path = common.output_path(root, size, frame, scale)
            label = f"{path.name}"
            if not path.exists():
                add(checks, "ERROR", "missing", f"缺少成品 {path.relative_to(common.project_root(root))}")
                continue
            im = Image.open(path).convert("RGBA")
            expected = (frame_w * scale, frame_h * scale)
            if im.size != expected:
                add(checks, "ERROR", "size", f"{label} 尺寸 {im.size} != {expected}")
            if frame not in one_x or scale < chosen_scale[frame]:
                one_x[frame] = im
                chosen_scale[frame] = scale

    if not one_x:
        return checks, size

    resample = Image.NEAREST if size.get("pixel") else Image.LANCZOS
    for frame, im in list(one_x.items()):
        if chosen_scale[frame] != 1 and im.size == (frame_w * chosen_scale[frame], frame_h * chosen_scale[frame]):
            one_x[frame] = im.resize((frame_w, frame_h), resample)

    if size.get("transparent", True) and size["type"] not in ("tile", "background"):
        for frame, im in one_x.items():
            if im.getchannel("A").getextrema()[0] >= 255:
                add(checks, "ERROR", "alpha", f"{frame or asset['id']} 没有透明像素（需要透明背景）")

    if size["type"] in ("tile", "background"):
        for frame, im in one_x.items():
            alpha = np.array(im)[..., 3]
            opaque_ratio = float((alpha > 0).mean()) if alpha.size else 0.0
            if opaque_ratio < 0.30:
                add(checks, "ERROR", "content", f"{asset['id']} 内容几乎全透明（不透明像素仅 {opaque_ratio:.0%}）")
            if not size.get("transparent") and int(alpha.min()) < 255:
                add(checks, "WARN", "opaque", f"{asset['id']} 声明为不透明，但画面含透明像素")

    if size["type"] == "icon":
        for frame, im in one_x.items():
            if not alpha_bbox(im):
                add(checks, "ERROR", "empty", f"{asset['id']} 画面全透明")
                continue
            ratio = fill_ratio(im)
            if ratio < 0.70:
                add(checks, "WARN", "icon_fill", f"{asset['id']} 主体偏小（占长边 {ratio:.0%}，建议 70%~95%）")
            elif ratio > 0.95:
                add(checks, "WARN", "icon_fill", f"{asset['id']} 主体几乎铺满（占长边 {ratio:.0%}）")
            padding = int(size.get("padding", 0))
            if padding > 0:
                left, top, right, bottom = alpha_bbox(im)
                if left < padding - 1 or top < padding - 1 or im.width - right < padding - 1 or im.height - bottom < padding - 1:
                    add(checks, "ERROR", "icon_margin", f"{asset['id']} 主体超出安全边距 padding={padding}")

    if size["type"] in ("character", "sprite") and len(one_x) > 1:
        baselines = []
        bboxes = []
        for frame, im in one_x.items():
            bbox = alpha_bbox(im)
            if not bbox:
                add(checks, "ERROR", "empty", f"{asset['id']} 的帧 {frame} 全透明")
                continue
            baselines.append(bbox[3])
            bboxes.append((frame, bbox))
        if baselines and max(baselines) - min(baselines) > 2:
            add(checks, "ERROR", "baseline",
                f"{asset['id']} 角色脚底基线不一致：{baselines}（最大差 {max(baselines) - min(baselines)}px）")

    if size.get("seamless"):
        for frame, im in one_x.items():
            error = seam_error(im)
            if error > SEAM_TOLERANCE:
                add(checks, "ERROR", "seam", f"{asset['id']} 平铺接缝误差 {error:.3f} > {SEAM_TOLERANCE}")

    if size["type"] == "ui":
        nine = size.get("nineSlice")
        for frame, im in one_x.items():
            if not nine_slice_ok(im.width, im.height, nine):
                add(checks, "ERROR", "nine_slice", f"{asset['id']} 九宫格边距超过画布：{nine} / {im.size}")

    if size.get("pixel"):
        for frame, im in one_x.items():
            ratio = semi_transparent_ratio(im)
            if ratio > 0.01:
                add(checks, "WARN", "pixel_alpha", f"{asset['id']} 半透明像素占 {ratio:.1%}（像素风建议关闭抗锯齿）")
            if style.get("palette"):
                count = unique_colors(im)
                limit = max(16, len(style["palette"])) * 3
                if count > limit:
                    add(checks, "WARN", "pixel_colors", f"{asset['id']} 颜色数 {count} 超过阈值 {limit}")

    if style.get("paletteLock") and style.get("palette"):
        for frame, im in one_x.items():
            delta = process.palette_delta(im, style["palette"])
            if delta > PALETTE_TOLERANCE:
                add(checks, "WARN", "palette", f"{asset['id']} 主色距色板平均 {delta:.1f}（阈值 {PALETTE_TOLERANCE}）")

    if len(frames) > 1:
        atlas_image = common.atlas_dir(root) / f"{asset['id']}.png"
        atlas_json = common.atlas_dir(root) / f"{asset['id']}.json"
        if not atlas_image.exists() or not atlas_json.exists():
            add(checks, "ERROR", "atlas", f"{asset['id']} 缺少图集 {atlas_image.name}/{atlas_json.name}")
        else:
            image = Image.open(atlas_image)
            meta = json.loads(atlas_json.read_text(encoding="utf-8"))
            if list(image.size) != list(meta.get("image_size", [])):
                add(checks, "ERROR", "atlas_size", f"{asset['id']} 图集尺寸 {image.size} != 元数据 {meta.get('image_size')}")
            if len(meta.get("frames", [])) != len(frames):
                add(checks, "ERROR", "atlas_frames", f"{asset['id']} 图集帧数 {len(meta.get('frames', []))} != {len(frames)}")
            names = [frame.get("name") for frame in meta.get("frames", []) if isinstance(frame, dict)]
            expected_names = [frame for frame in frames if frame]
            if names != expected_names:
                add(checks, "ERROR", "atlas_names", f"{asset['id']} 图集帧名 {names} != {expected_names}")
            if list(meta.get("cell", [])) != [frame_w, frame_h]:
                add(checks, "ERROR", "atlas_cell", f"{asset['id']} 图集单元格 {meta.get('cell')} != {[frame_w, frame_h]}")

    return checks, size


def run(root=None):
    root_path = common.project_root(root)
    project = common.load_project(root_path)
    style = common.load_style(project, root_path)
    assets = common.load_assets(project, root_path)
    presets = common.load_presets(project, root_path)

    results = []
    counts = {"ERROR": 0, "WARN": 0, "OK": 0}
    for asset in assets:
        checks, _ = check_asset(root_path, project, style, asset, presets)
        errors = [c for c in checks if c["level"] == "ERROR"]
        warns = [c for c in checks if c["level"] == "WARN"]
        counts["ERROR"] += len(errors)
        counts["WARN"] += len(warns)
        if not errors and not warns:
            counts["OK"] += 1
        results.append({"id": asset.get("id"), "type": asset.get("type"), "checks": checks})
        for check in checks:
            print(f"{check['level']:<6}{asset.get('id'):<18}{check['message']}")

    report = {
        "project": project.get("name"),
        "style": style.get("name"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": counts,
        "assets": results,
    }
    out = common.ensure_dir(root_path / "out") / "check_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{counts['ERROR']} ERROR，{counts['WARN']} WARN，{counts['OK']} 个素材全过；报告 {out}")
    return 0 if counts["ERROR"] == 0 else 1, report


def main():
    ap = argparse.ArgumentParser(description="素材质量闸门")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--json", action="store_true", help="把完整报告打印到 stdout")
    args = ap.parse_args()
    try:
        code, report = run(args.project)
    except common.ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
