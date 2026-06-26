from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

from .inpaint.nonbubble import build_gpt_edit_mask, build_text_mask


@dataclass(frozen=True)
class TextPixelGptMask:
    gpt_mask: Image.Image
    text_mask: Image.Image
    strategy: str
    editable_pixel_count: int


def build_text_pixel_gpt_mask(
    context_crop: Image.Image,
    local_bbox: tuple[int, int, int, int],
    polarity: str = "dark_on_light",
    expand_px: int = 2,
) -> TextPixelGptMask:
    target = context_crop.convert("RGB").crop(local_bbox)
    text_mask = build_target_text_mask(target, polarity=polarity, expand_px=expand_px)
    editable_count = int(np.array(text_mask.convert("L"), dtype=np.uint8).sum() // 255)
    if editable_count == 0:
        text_mask = _rect_mask((local_bbox[2] - local_bbox[0], local_bbox[3] - local_bbox[1]))
        editable_count = int(np.array(text_mask, dtype=np.uint8).sum() // 255)
        strategy = "rect_fallback_no_text_pixels"
    else:
        strategy = "text_pixels_within_bbox"

    full_text_mask = Image.new("L", context_crop.size, 0)
    full_text_mask.paste(text_mask, (local_bbox[0], local_bbox[1]))
    return TextPixelGptMask(
        gpt_mask=build_gpt_edit_mask(full_text_mask),
        text_mask=full_text_mask,
        strategy=strategy,
        editable_pixel_count=editable_count,
    )


def build_target_text_mask(
    target: Image.Image,
    polarity: str = "dark_on_light",
    expand_px: int = 2,
) -> Image.Image:
    polarities = [polarity] if polarity in {"dark_on_light", "light_on_dark"} else ["dark_on_light", "light_on_dark"]
    masks = [build_text_mask(target, dilate_px=1, polarity=item) for item in dict.fromkeys(polarities)]
    combined = masks[0]
    for mask in masks[1:]:
        combined = Image.fromarray(
            np.maximum(np.array(combined.convert("L"), dtype=np.uint8), np.array(mask.convert("L"), dtype=np.uint8)),
            mode="L",
        )
    filtered = _remove_dominant_solid_non_text_components(combined)
    if polarity == "light_on_dark":
        filtered = _remove_edge_bright_non_text_components(filtered)
    if expand_px > 0:
        filter_size = max(3, expand_px * 2 + 1)
        filtered = filtered.filter(ImageFilter.MaxFilter(filter_size))
        if polarity == "light_on_dark":
            filtered = _remove_edge_bright_non_text_components(filtered)
    return filtered


def _remove_dominant_solid_non_text_components(mask: Image.Image) -> Image.Image:
    binary = np.array(mask.convert("L"), dtype=np.uint8) > 0
    if not bool(binary.any()):
        return mask.convert("L")

    height, width = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    components: list[dict] = []
    for start_y, start_x in zip(*np.where(binary & ~visited)):
        components.append(_component(binary, visited, int(start_x), int(start_y)))

    if len(components) < 3:
        return mask.convert("L")

    text_like_areas = [component["area"] for component in components if component["area"] < height * width * 0.08]
    reference_area = float(np.median(text_like_areas or [component["area"] for component in components]))
    result = binary.copy()
    for component in components:
        if _looks_like_dominant_solid_non_text(component, reference_area, width * height):
            x1, y1, x2, y2 = component["bbox"]
            result[y1:y2, x1:x2] = False

    if not bool(result.any()):
        return mask.convert("L")
    return Image.fromarray(result.astype(np.uint8) * 255, mode="L")


def _remove_edge_bright_non_text_components(mask: Image.Image) -> Image.Image:
    binary = np.array(mask.convert("L"), dtype=np.uint8) > 0
    if not bool(binary.any()):
        return mask.convert("L")

    height, width = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    result = binary.copy()
    for start_y, start_x in zip(*np.where(binary & ~visited)):
        component = _component(binary, visited, int(start_x), int(start_y))
        if _looks_like_edge_non_text_component(component, width, height):
            x1, y1, x2, y2 = component["bbox"]
            result[y1:y2, x1:x2] = False

    if not bool(result.any()):
        return mask.convert("L")
    return Image.fromarray(result.astype(np.uint8) * 255, mode="L")


def _looks_like_edge_non_text_component(component: dict, crop_width: int, crop_height: int) -> bool:
    x1, y1, x2, y2 = component["bbox"]
    width = x2 - x1
    height = y2 - y1
    touches_vertical_edge = x1 == 0 or x2 == crop_width
    touches_horizontal_edge = y1 == 0 or y2 == crop_height
    if not (touches_vertical_edge or touches_horizontal_edge):
        return False
    area_ratio = component["area"] / max(1, crop_width * crop_height)
    if touches_vertical_edge and height >= crop_height * 0.65 and width >= max(5, crop_width * 0.035):
        return True
    if touches_horizontal_edge and width >= crop_width * 0.65 and height >= max(5, crop_height * 0.06):
        return True
    return area_ratio >= 0.12 and component["fill_ratio"] >= 0.72


def _looks_like_dominant_solid_non_text(component: dict, reference_area: float, crop_area: int) -> bool:
    x1, y1, x2, y2 = component["bbox"]
    width = x2 - x1
    height = y2 - y1
    area = component["area"]
    fill_ratio = component["fill_ratio"]
    if area < max(400, crop_area * 0.035):
        return False
    if reference_area <= 0 or area < reference_area * 3.0:
        return False
    if fill_ratio < 0.72:
        return False
    return width >= 16 and height >= 16


def _component(binary: np.ndarray, visited: np.ndarray, start_x: int, start_y: int) -> dict:
    stack = [(start_x, start_y)]
    visited[start_y, start_x] = True
    area = 0
    min_x = max_x = start_x
    min_y = max_y = start_y
    while stack:
        x, y = stack.pop()
        area += 1
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < binary.shape[1] and 0 <= ny < binary.shape[0] and not visited[ny, nx] and binary[ny, nx]:
                visited[ny, nx] = True
                stack.append((nx, ny))
    bbox = (int(min_x), int(min_y), int(max_x + 1), int(max_y + 1))
    bbox_area = max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    return {"area": int(area), "bbox": bbox, "fill_ratio": float(area / bbox_area)}


def _rect_mask(size: tuple[int, int]) -> Image.Image:
    return Image.new("L", size, 255)
