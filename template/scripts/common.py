"""公共工具：配置加载、尺寸解析、命名与字体。

所有脚本都从这里拿项目、风格、素材清单和最终尺寸，保证同一份配置
在渲染、后处理、校验、导出时解析结果完全一致。
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path

VALID_TYPES = ("character", "sprite", "icon", "background", "tile", "ui", "vfx")
VALID_MODES = ("ai-image", "code-draw")
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
FRAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

BUILTIN_PRESETS = {
    "icon": {"width": 256, "height": 256, "scales": [1, 2], "padding": 8, "trim": True, "anchor": "center", "transparent": True},
    "character": {"width": 512, "height": 512, "scales": [1, 2], "padding": 8, "trim": True, "anchor": "bottom-center", "transparent": True},
    "sprite": {"cell": 64, "columns": 4, "scales": [1], "gap": 0, "padding": 0, "trim": False, "anchor": "bottom-center", "transparent": True},
    "background": {"width": 1920, "height": 1080, "scales": [1], "padding": 0, "trim": False, "anchor": "center", "transparent": False},
    "tile": {"width": 64, "height": 64, "scales": [1, 2], "padding": 0, "trim": False, "anchor": "center", "transparent": True, "seamless": True},
    "ui": {"width": 512, "height": 128, "scales": [1, 2], "padding": 0, "trim": False, "anchor": "center", "transparent": True,
           "nineSlice": {"left": 32, "right": 32, "top": 32, "bottom": 32}},
    "vfx": {"cell": 128, "columns": 8, "scales": [1], "gap": 0, "padding": 4, "trim": False, "anchor": "center", "transparent": True},
}


class ConfigError(Exception):
    """配置或素材清单不合法。"""


def project_root(root=None):
    """工程根目录。优先级：显式参数 > 环境变量 > 脚本所在 template/工程目录。"""
    if root:
        return Path(root).expanduser().resolve()
    env = os.environ.get("GAME_ASSET_PROJECT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"找不到配置文件：{path}")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON 格式错误：{path}：{exc}")


def load_project(root=None):
    root = project_root(root)
    project = _read_json(root / "project.json")
    project.setdefault("name", "未命名项目")
    project.setdefault("style", "style.json")
    project.setdefault("sizes", {})
    project.setdefault("defaults", {})
    project["_root"] = str(root)
    return project


def load_style(project, root=None):
    root = project_root(root)
    ref = Path(project.get("style", "style.json"))
    path = ref if ref.is_absolute() else root / ref
    style = _read_json(path)
    style.setdefault("name", "未命名风格")
    style.setdefault("keywords", [])
    style.setdefault("palette", [])
    style.setdefault("line", "")
    style.setdefault("lighting", "")
    style.setdefault("material", "")
    style.setdefault("referenceImages", [])
    style.setdefault("avoid", [])
    style.setdefault("pixelGrid", 0)
    style.setdefault("paletteLock", False)
    style.setdefault("background", "transparent")
    style["_path"] = str(path)
    return style


def load_assets(project, root=None):
    root = project_root(root)
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - 环境问题
        raise ConfigError("缺少 PyYAML：pip install -r requirements.txt") from exc

    ref = Path(project.get("assets", "assets.yaml"))
    path = ref if ref.is_absolute() else root / ref
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise ConfigError(f"找不到素材清单：{path}")
    except Exception as exc:
        raise ConfigError(f"YAML 解析失败：{path}：{exc}")
    assets = data.get("assets") if isinstance(data, dict) else data
    if not isinstance(assets, list) or not assets:
        raise ConfigError(f"素材清单为空或格式不对：{path}")
    for asset in assets:
        if not isinstance(asset, dict):
            raise ConfigError(f"素材项格式不对：{asset!r}")
        asset_id = asset.get("id")
        if not isinstance(asset_id, str) or not ID_RE.match(asset_id):
            raise ConfigError(f"素材 id 不合法（需小写蛇形，不能含路径分隔符）：{asset_id!r}")
        frames = asset.get("frames") or []
        if isinstance(frames, str):
            frames = [frames]
        for frame in frames:
            if not isinstance(frame, str) or not FRAME_RE.match(frame) or ".." in frame:
                raise ConfigError(f"素材 {asset_id} 的帧名不合法：{frame!r}")
        asset.setdefault("mode", project.get("defaults", {}).get("mode", "ai-image"))
        asset.setdefault("frames", frames)
    return assets


def load_presets(project, root=None):
    root = project_root(root)
    candidates = [
        root / "presets" / "sizes.json",
        Path(__file__).resolve().parents[1] / "presets" / "sizes.json",
        Path(__file__).resolve().parents[2] / "library" / "presets" / "sizes.json",
    ]
    for path in candidates:
        if path.exists():
            return _read_json(path)
    return BUILTIN_PRESETS


def frames_of(asset):
    """返回帧列表；无帧素材返回 [None]，None 表示文件名不带帧段。"""
    frames = asset.get("frames") or []
    if isinstance(frames, str):
        frames = [frames]
    return list(frames) if frames else [None]


def resolve_size(asset, project, presets, frame_count=1, style=None):
    """按 默认预设 < 项目覆盖 < 素材覆盖 的优先级解析最终尺寸。"""
    typ = asset.get("type")
    if typ not in VALID_TYPES:
        raise ConfigError(f"素材 {asset.get('id')} 的类型不合法：{typ}")

    # 优先级：类型默认 < 素材显式 preset < 项目覆盖 < 素材内联覆盖
    merged = dict(presets.get(typ, BUILTIN_PRESETS.get(typ, {})))

    spec = asset.get("size") or {}
    if isinstance(spec, str):
        spec = {"preset": spec}
    preset_name = spec.get("preset")
    if preset_name:
        if preset_name not in presets:
            raise ConfigError(f"素材 {asset.get('id')} 引用了不存在的尺寸预设：{preset_name}")
        merged.update(presets[preset_name])

    project_sizes = project.get("sizes") or {}
    merged.update(project_sizes.get(typ) or {})
    merged.update({k: v for k, v in spec.items() if k != "preset"})

    defaults = project.get("defaults") or {}
    for key in ("padding", "trim", "anchor"):
        if key in defaults and key not in merged:
            merged[key] = defaults[key]

    frames = max(1, int(frame_count))
    columns = int(merged.get("columns") or (frames if frames > 1 else 1))
    columns = max(1, columns)
    cell = merged.get("cell")

    if cell:
        cell = int(cell)
        rows = math.ceil(frames / columns)
        merged["cell"] = cell
        merged["rows"] = rows
        merged["width"] = cell * columns
        merged["height"] = cell * rows
    else:
        if not merged.get("width") or not merged.get("height"):
            raise ConfigError(f"素材 {asset.get('id')} 缺少 width/height 或 cell")
        merged["width"] = int(merged["width"])
        merged["height"] = int(merged["height"])
        merged["rows"] = math.ceil(frames / columns)

    merged["columns"] = columns
    merged["frames"] = frames
    scales = merged.get("scales") or [1]
    merged["scales"] = sorted({int(s) for s in scales})
    if any(s <= 0 for s in merged["scales"]):
        raise ConfigError(f"素材 {asset.get('id')} 的 scales 必须是正整数")

    merged.setdefault("padding", 0)
    merged.setdefault("anchor", "center")
    merged.setdefault("trim", True)
    merged.setdefault("transparent", True)
    merged.setdefault("gap", 0)
    merged.setdefault("seamless", False)
    # 整块纹理（背景/平铺）的纯色填充是内容，不是背景，默认不去底
    merged.setdefault("removeBg", typ not in ("background", "tile"))
    pixel_grid = int((style or {}).get("pixelGrid", 0) or 0)
    merged["pixel"] = bool(merged.get("pixel") or pixel_grid > 0)
    merged["pixelGrid"] = pixel_grid
    merged["type"] = typ
    merged["id"] = asset.get("id")
    merged["mode"] = asset.get("mode", "ai-image")
    merged["name"] = asset.get("name") or asset.get("id")
    return merged


def frame_file(asset_id, frame):
    return f"{frame}.png" if frame else f"{asset_id}.png"


def raw_path(root, size, frame):
    return project_root(root) / "raw" / size["type"] / size["id"] / frame_file(size["id"], frame)


def output_name(asset_type, asset_id, frame, scale):
    middle = f"{asset_type}_{asset_id}"
    if frame:
        middle += f"_{frame}"
    return f"{middle}@{scale}x.png"


def output_path(root, size, frame, scale):
    return project_root(root) / "out" / "assets" / size["type"] / output_name(size["type"], size["id"], frame, scale)


def atlas_dir(root):
    return project_root(root) / "out" / "atlas"


def style_block(style):
    """把 Style Card 编译成生图 prompt 里可复用的风格块。"""
    parts = []
    if style.get("keywords"):
        parts.append(", ".join(style["keywords"]))
    if style.get("palette"):
        parts.append("palette: " + ", ".join(style["palette"]))
    for key, label in (("line", "line"), ("lighting", "lighting"), ("material", "material")):
        if style.get(key):
            parts.append(f"{label}: {style[key]}")
    if style.get("background") == "transparent":
        parts.append("isolated on transparent background, no backdrop")
    text = "; ".join(parts)
    if style.get("avoid"):
        text += "\nAvoid: " + ", ".join(style["avoid"])
    return text


def hex_to_rgb(value):
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"颜色格式不对：{value}")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def font(size=14):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()
