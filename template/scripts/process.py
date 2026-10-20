"""后处理：去底、裁切、补边、统一画布、调色锁定、多倍导出、精灵表。

用法：
    python3 scripts/process.py
    python3 scripts/process.py --only knight --only potion_red
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas as atlas_lib  # noqa: E402
import common  # noqa: E402


def remove_solid_bg(im, tolerance=24):
    """把四边纯色背景变透明，并对边缘做简单去溢色。已有透明通道时原样返回。"""
    im = im.convert("RGBA")
    arr = np.array(im)
    alpha = arr[..., 3]
    # 用四边透明像素占比判断，而不是单个像素：AI 图常有一两个半透明杂点，
    # 那不代表背景已经透明，仍需要按纯色 key 去除。
    border = np.concatenate([alpha[0, :], alpha[-1, :], alpha[:, 0], alpha[:, -1]])
    if border.size and float((border < 250).mean()) > 0.5:
        return im

    corners = [arr[0, 0, :3], arr[0, -1, :3], arr[-1, 0, :3], arr[-1, -1, :3]]
    best = None
    for color in corners:
        color = color.astype(np.int32)
        dist = np.linalg.norm(arr[..., :3].astype(np.int32) - color, axis=-1)
        matches = sum(np.linalg.norm(c.astype(np.int32) - color) <= tolerance for c in corners)
        count = int((dist <= tolerance).sum())
        if best is None or (matches, count) > (best[0], best[1]):
            best = (matches, count, color, dist)

    matches, count, bg, dist = best
    total = arr.shape[0] * arr.shape[1]
    if matches < 3 or count < total * 0.15:
        return im

    mask = dist <= tolerance
    arr[..., 3] = np.where(mask, 0, arr[..., 3]).astype(np.uint8)

    # 边缘去溢色：把背景色与主体之间的过渡像素按估计 alpha 反混合
    near = (dist > tolerance) & (dist <= tolerance * 2) & ~mask
    if near.any() and tolerance > 0:
        estimate = np.clip((dist - tolerance) / float(tolerance), 0.0, 1.0)
        rgb = arr[..., :3].astype(np.float32)
        bgf = bg.astype(np.float32)
        with np.errstate(divide="ignore", invalid="ignore"):
            fg = (rgb - bgf * (1.0 - estimate[..., None])) / np.maximum(estimate[..., None], 1e-3)
        arr[..., :3] = np.where(near[..., None], np.clip(fg, 0, 255), rgb).astype(np.uint8)
        arr[..., 3] = np.where(near, (estimate * 255).astype(np.uint8), arr[..., 3]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def trim_alpha(im, padding=0):
    """按 alpha 包围盒裁切，四周保留 padding。"""
    im = im.convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    if not bbox:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    left, top, right, bottom = bbox
    padding = max(0, int(padding))
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(im.width, right + padding)
    bottom = min(im.height, bottom + padding)
    return im.crop((left, top, right, bottom))


def fit_canvas(im, width, height, padding=0, anchor="center", nearest=False, cover=False):
    """等比缩放后放进目标画布。透明素材用 contain，不透明素材用 cover。"""
    im = im.convert("RGBA")
    width, height = max(1, int(width)), max(1, int(height))
    padding = max(0, int(padding))
    avail_w = max(1, width - 2 * padding)
    avail_h = max(1, height - 2 * padding)
    resample = Image.NEAREST if nearest else Image.LANCZOS

    if cover:
        # 不透明素材必须铺满画布，padding 不参与 cover，否则四周会留下透明边
        scale = max(width / im.width, height / im.height)
        new_w = max(1, round(im.width * scale))
        new_h = max(1, round(im.height * scale))
        resized = im.resize((new_w, new_h), resample)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.paste(resized, ((width - new_w) // 2, (height - new_h) // 2), resized)
        return canvas

    scale = min(avail_w / im.width, avail_h / im.height)
    new_w = max(1, round(im.width * scale))
    new_h = max(1, round(im.height * scale))
    resized = im.resize((new_w, new_h), resample)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = (width - new_w) // 2
    if anchor == "bottom-center":
        y = height - padding - new_h
    elif anchor == "top-center":
        y = padding
    else:
        y = (height - new_h) // 2
    canvas.alpha_composite(resized, (max(0, x), max(0, y)))
    return canvas


def harden_alpha(im, threshold=128):
    """像素风把 alpha 二值化，消除抗锯齿产生的半透明边缘。"""
    arr = np.array(im.convert("RGBA"))
    alpha = arr[..., 3]
    arr[..., 3] = np.where(alpha >= threshold, 255, 0).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def quantize_to_palette(im, palette, chunk=65536):
    """把 RGB 映射到最近的调色板颜色，alpha 保持不变。"""
    if not palette:
        return im.convert("RGBA")
    colors = np.array([common.hex_to_rgb(c) if isinstance(c, str) else tuple(c) for c in palette], dtype=np.int32)
    arr = np.array(im.convert("RGBA"))
    flat = arr[..., :3].reshape(-1, 3).astype(np.int32)
    mapped = flat.copy()
    for start in range(0, len(flat), chunk):
        block = flat[start:start + chunk]
        distances = ((block[:, None, :] - colors[None, :, :]) ** 2).sum(axis=-1)
        mapped[start:start + chunk] = colors[distances.argmin(axis=1)]
    arr[..., :3] = mapped.reshape(arr.shape[0], arr.shape[1], 3).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def palette_delta(im, palette, sample=20000):
    """采样估计主色到调色板的平均距离，用于报告风格漂移。"""
    if not palette:
        return 0.0
    colors = np.array([common.hex_to_rgb(c) if isinstance(c, str) else tuple(c) for c in palette], dtype=np.int32)
    arr = np.array(im.convert("RGBA"))
    opaque = arr[arr[..., 3] > 0][:, :3].astype(np.int32)
    if not len(opaque):
        return 0.0
    if len(opaque) > sample:
        step = max(1, len(opaque) // sample)
        opaque = opaque[::step]
    distances = ((opaque[:, None, :] - colors[None, :, :]) ** 2).sum(axis=-1)
    return float(np.sqrt(distances.min(axis=1)).mean())


def process_asset(root, project, style, asset, presets):
    frames = common.frames_of(asset)
    size = common.resolve_size(asset, project, presets, len(frames), style=style)
    body_w = int(size.get("cell") or size["width"])
    body_h = int(size.get("cell") or size["height"])
    palette = style.get("palette") if style.get("paletteLock") else []
    pixel = bool(size.get("pixel"))
    report = {
        "id": asset["id"],
        "type": size["type"],
        "frames": [],
        "outputs": [],
        "palette_delta": 0.0,
        "atlas": None,
    }
    base_frames = []

    for frame in frames:
        raw = common.find_raw(root, size, frame)
        if not raw:
            raise FileNotFoundError(f"缺原始图 {common.raw_path(root, size, frame)}")
        original = ImageOps.exif_transpose(Image.open(raw)).convert("RGBA")
        im = original

        if size.get("transparent", True) and size.get("removeBg", True):
            im = remove_solid_bg(im)
        if size.get("trim", True):
            im = trim_alpha(im, 0)

        # 每个倍率都直接从原始图重采样，避免「先缩到 1x 再放大」损失细节
        padding = int(size.get("padding", 0))
        anchor = size.get("anchor", "center")
        cover = not size.get("transparent", True)
        base = None
        base_scale = None
        for scale in size["scales"]:
            canvas = fit_canvas(
                im, body_w * scale, body_h * scale,
                padding=padding * scale,
                anchor=anchor,
                nearest=pixel,
                cover=cover,
            )
            if pixel:
                canvas = harden_alpha(canvas)
            if palette:
                report["palette_delta"] = max(report["palette_delta"], palette_delta(canvas, palette))
                canvas = quantize_to_palette(canvas, palette)
            out = common.output_path(root, size, frame, scale)
            common.ensure_dir(out.parent)
            canvas.save(out)
            report["outputs"].append(str(out.relative_to(common.project_root(root))))
            if base_scale is None or scale < base_scale:
                resample = Image.NEAREST if pixel else Image.LANCZOS
                base = canvas.copy() if scale == 1 else canvas.resize((body_w, body_h), resample)
                base_scale = scale

        base_frames.append(base)
        report["frames"].append({
            "frame": frame,
            "raw": str(raw.relative_to(common.project_root(root))),
            "raw_size": list(original.size),
            "canvas": [body_w, body_h],
        })

    if len(base_frames) > 1:
        atlas_img, meta = atlas_lib.build_atlas(
            base_frames,
            columns=size["columns"],
            gap=int(size.get("gap", 0)),
            names=[f for f in frames],
        )
        out_dir = common.ensure_dir(common.atlas_dir(root))
        image_path = out_dir / f"{asset['id']}.png"
        atlas_img.save(image_path)
        meta.update({
            "id": asset["id"],
            "name": size["name"],
            "type": size["type"],
            "frame_names": [f for f in frames if f],
            "source_frame_size": [body_w, body_h],
        })
        meta_path = out_dir / f"{asset['id']}.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        report["atlas"] = {
            "image": str(image_path.relative_to(common.project_root(root))),
            "json": str(meta_path.relative_to(common.project_root(root))),
        }
    return report


def run(root=None, only=None):
    root_path = common.project_root(root)
    project = common.load_project(root_path)
    style = common.load_style(project, root_path)
    assets = common.load_assets(project, root_path)
    presets = common.load_presets(project, root_path)
    only = set(only or [])

    reports, errors = [], []
    for asset in assets:
        if only and asset.get("id") not in only:
            continue
        try:
            reports.append(process_asset(root_path, project, style, asset, presets))
        except Exception as exc:
            errors.append({"id": asset.get("id"), "error": str(exc)})
            print(f"ERROR {asset.get('id')}：{exc}", file=sys.stderr)

    result = {
        "project": project.get("name"),
        "style": style.get("name"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "assets": reports,
        "errors": errors,
    }
    out = common.ensure_dir(root_path / "out") / "process_report.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"处理 {len(reports)} 个素材，{len(errors)} 个失败；报告 {out}")
    return 0 if not errors else 1


def main():
    ap = argparse.ArgumentParser(description="素材后处理")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--only", action="append", help="只处理指定素材 id，可重复")
    args = ap.parse_args()
    try:
        return run(args.project, args.only)
    except common.ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
