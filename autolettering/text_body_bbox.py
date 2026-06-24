from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .text_bbox import matched_text_mask_bbox, selected_text_bbox, selected_text_polarity


def selected_text_body_bbox(detection: dict) -> tuple[int, int, int, int]:
    matched_mask = matched_text_mask_bbox(detection)
    if matched_mask is not None:
        return matched_mask
    bbox = selected_text_bbox(detection)
    trimmed = _trim_leading_light_icon(detection, bbox)
    if trimmed is not None:
        return trimmed
    if not _can_trim_top_decoration(detection, bbox):
        return bbox

    image_path = detection.get("image_path")
    if not image_path or not Path(image_path).exists():
        return bbox

    try:
        with Image.open(image_path) as image:
            crop = image.convert("L").crop(bbox)
    except OSError:
        return bbox

    trim_y = _top_text_y_after_decoration(crop)
    if trim_y is None:
        return bbox

    x1, y1, x2, y2 = bbox
    return x1, y1 + trim_y, x2, y2


def _trim_leading_light_icon(
    detection: dict,
    bbox: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    if detection.get("group_name") == "框内":
        return None
    if selected_text_polarity(detection, bbox) != "light_on_dark":
        return None
    if _width(bbox) < _height(bbox) * 1.8:
        return None

    image_path = detection.get("image_path")
    if not image_path or not Path(image_path).exists():
        return None

    try:
        with Image.open(image_path) as image:
            crop = image.convert("L").crop(bbox)
    except OSError:
        return None

    trim_x = _leading_light_icon_trim_x(crop)
    if trim_x is None:
        return None

    x1, y1, x2, y2 = bbox
    return x1 + trim_x, y1, x2, y2


def _leading_light_icon_trim_x(crop: Image.Image) -> int | None:
    bright = np.array(
        crop.point(lambda value: 255 if value > 205 else 0, mode="L").filter(ImageFilter.MaxFilter(3)),
        dtype=np.uint8,
    ) > 0
    if not bool(bright.any()):
        return None

    height, width = bright.shape
    visited = np.zeros_like(bright, dtype=bool)
    components: list[tuple[int, int, int, int, int]] = []
    for start_y, start_x in zip(*np.where(bright & ~visited)):
        pixels = _component_pixels(bright, visited, int(start_x), int(start_y))
        if len(pixels) < 20:
            continue
        x1, y1, x2, y2 = _component_bbox(pixels)
        components.append((x1, y1, x2, y2, len(pixels)))

    components.sort(key=lambda item: (item[0], item[1]))
    if len(components) < 2:
        return None

    icon = components[0]
    next_component = next((item for item in components[1:] if item[0] >= icon[2] + 2), None)
    if next_component is None or not _looks_like_leading_light_icon(icon, width, height):
        return None

    trim_x = next_component[0]
    if trim_x > width * 0.38 or width - trim_x < width * 0.45:
        return None
    return trim_x


def _looks_like_leading_light_icon(
    component: tuple[int, int, int, int, int],
    crop_width: int,
    crop_height: int,
) -> bool:
    x1, y1, x2, y2, area = component
    width = x2 - x1
    height = y2 - y1
    if x1 > max(3, int(crop_width * 0.05)):
        return False
    if width < 12 or height < 12:
        return False
    if width > crop_width * 0.32 or height > crop_height * 0.85:
        return False
    aspect = width / max(1, height)
    fill_ratio = area / max(1, width * height)
    return 0.65 <= aspect <= 1.55 and 0.2 <= fill_ratio <= 0.62


def _can_trim_top_decoration(detection: dict, bbox: tuple[int, int, int, int]) -> bool:
    if detection.get("group_name") == "框内":
        return False
    if selected_text_polarity(detection, bbox) != "dark_on_light":
        return False
    return _height(bbox) >= _width(bbox) * 3


def _top_text_y_after_decoration(crop: Image.Image) -> int | None:
    gray = np.array(crop.convert("L"), dtype=np.uint8)
    dark = gray < 185
    strict_dark = gray < 80
    if not bool(dark.any()) or not bool(strict_dark.any()):
        return None

    icon_bbox = _top_diamond_icon_bbox(strict_dark)
    if icon_bbox is None:
        return None

    remaining = dark.copy()
    x1, y1, x2, y2 = icon_bbox
    margin = 2
    remaining[max(0, y1 - margin) : min(gray.shape[0], y2 + margin), max(0, x1 - margin) : min(gray.shape[1], x2 + margin)] = False

    rows = np.where(remaining.sum(axis=1) > 0)[0]
    if rows.size == 0:
        return None
    text_top = int(rows[0])
    if text_top <= y2 + 1:
        return None
    if text_top > gray.shape[0] * 0.35:
        return None
    return text_top


def _top_diamond_icon_bbox(binary: np.ndarray) -> tuple[int, int, int, int] | None:
    height, width = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    best: tuple[int, int, int, int] | None = None
    for start_y, start_x in zip(*np.where(binary & ~visited)):
        pixels = _component_pixels(binary, visited, int(start_x), int(start_y))
        bbox = _component_bbox(pixels)
        if _looks_like_top_diamond(pixels, bbox, width, height):
            if best is None or bbox[1] < best[1]:
                best = bbox
    return best


def _component_pixels(binary: np.ndarray, visited: np.ndarray, start_x: int, start_y: int) -> list[tuple[int, int]]:
    stack = [(start_x, start_y)]
    visited[start_y, start_x] = True
    pixels: list[tuple[int, int]] = []
    height, width = binary.shape
    while stack:
        x, y = stack.pop()
        pixels.append((y, x))
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and not visited[ny, nx] and binary[ny, nx]:
                visited[ny, nx] = True
                stack.append((nx, ny))
    return pixels


def _component_bbox(pixels: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    ys, xs = zip(*pixels)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _looks_like_top_diamond(
    pixels: list[tuple[int, int]],
    bbox: tuple[int, int, int, int],
    crop_width: int,
    crop_height: int,
) -> bool:
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    if y1 > max(12, int(crop_height * 0.08)):
        return False
    if width < 14 or height < 14:
        return False
    if width > crop_width * 0.9 or height > crop_height * 0.25:
        return False
    aspect = width / max(1, height)
    fill_ratio = len(pixels) / max(1, width * height)
    return 0.65 <= aspect <= 1.55 and fill_ratio >= 0.38 and _has_diamond_profile(pixels, bbox)


def _has_diamond_profile(pixels: list[tuple[int, int]], bbox: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = bbox
    rows = np.zeros((y2 - y1, x2 - x1), dtype=bool)
    for y, x in pixels:
        rows[y - y1, x - x1] = True
    row_widths = rows.sum(axis=1)
    nonempty = row_widths[row_widths > 0]
    if nonempty.size < 5:
        return False
    peak_index = int(np.argmax(row_widths))
    peak_width = int(row_widths[peak_index])
    edge_limit = peak_width * 0.45
    return (
        rows.shape[0] * 0.25 <= peak_index <= rows.shape[0] * 0.75
        and int(nonempty[0]) <= edge_limit
        and int(nonempty[-1]) <= edge_limit
    )


def _width(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[2] - bbox[0])


def _height(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[3] - bbox[1])
