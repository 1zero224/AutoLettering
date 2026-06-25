from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from .balloons import aot_inpaint as balloons_aot_inpaint
from .balloons import lama_large_inpaint as balloons_lama_large_inpaint
from .balloons import lama_mpe_inpaint as balloons_lama_mpe_inpaint
from .balloons import patchmatch_inpaint as balloons_patchmatch_inpaint
from .models import NonBubbleInpaintResult


def inpaint_nonbubble_text(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    output_dir: str | Path,
    record_id: str,
    method: str = "bt_lama_large",
    polarity: str = "dark_on_light",
    dark_threshold: int = 185,
    light_threshold: int = 210,
    mask_dilate_px: int = 5,
    iterations: int = 80,
    text_mask_path: str | Path | None = None,
) -> NonBubbleInpaintResult:
    output_root = Path(output_dir)
    safe_id = _safe_name(record_id)
    with Image.open(image_path) as image:
        crop = image.convert("RGB").crop(bbox)

    text_mask = (
        _dilate_mask(_crop_external_mask(text_mask_path, bbox, crop.size), mask_dilate_px)
        if text_mask_path
        else build_text_mask(crop, dark_threshold, mask_dilate_px, polarity=polarity, light_threshold=light_threshold)
    )
    method_name, cleaned = inpaint_crop(crop, text_mask, method, iterations)
    gpt_mask = build_gpt_edit_mask(text_mask)

    input_path = output_root / "input" / f"{safe_id}.png"
    text_mask_path = output_root / "mask" / f"{safe_id}.png"
    gpt_mask_path = output_root / "gpt_mask" / f"{safe_id}.png"
    cleaned_path = output_root / "cleaned" / f"{safe_id}.png"
    before_after_path = output_root / "before_after" / f"{safe_id}.png"
    _save(crop, input_path)
    _save(text_mask, text_mask_path)
    _save(gpt_mask, gpt_mask_path)
    _save(cleaned, cleaned_path)
    _save_before_after(crop, cleaned, before_after_path)

    return NonBubbleInpaintResult(
        record_id=record_id,
        method=method_name,
        bbox=bbox,
        input_crop_path=input_path,
        text_mask_path=text_mask_path,
        gpt_mask_path=gpt_mask_path,
        cleaned_crop_path=cleaned_path,
        before_after_path=before_after_path,
        dark_pixel_count=int(np.array(text_mask).sum() // 255),
    )


def inpaint_crop(
    crop: Image.Image,
    text_mask: Image.Image,
    method: str = "bt_lama_large",
    iterations: int = 80,
) -> tuple[str, Image.Image]:
    method = _canonical_method(method)
    if method == "local_diffusion":
        return "local_diffusion_inpaint", diffuse_inpaint(crop, text_mask, iterations)
    if method in {"opencv_telea", "opencv_ns"}:
        return f"{method}_inpaint", opencv_inpaint(crop, text_mask, method)
    if method == "bt_opencv_tela":
        return "bt_opencv-tela_actual_cv2_INPAINT_NS", opencv_inpaint(crop, text_mask, "opencv_ns")
    if method == "flat_median_fill":
        return "flat_median_fill", flat_median_fill(crop, text_mask)
    if method == "dark_panel_fill":
        return "dark_panel_fill", dark_panel_fill(crop, text_mask)
    if method == "texture_blur_fill":
        return "texture_blur_fill", texture_blur_fill(crop, text_mask)
    if method == "bt_aot":
        return "bt_aot_inpaint", balloons_aot_inpaint(crop, text_mask)
    if method == "bt_lama_mpe":
        return "bt_lama_mpe_inpaint", balloons_lama_mpe_inpaint(crop, text_mask)
    if method == "bt_lama_large":
        return "bt_lama_large_inpaint", balloons_lama_large_inpaint(crop, text_mask)
    if method == "bt_patchmatch":
        return "bt_patchmatch_inpaint", balloons_patchmatch_inpaint(crop, text_mask)
    raise ValueError(f"unsupported_inpaint_method:{method}")


def build_text_mask(
    crop: Image.Image,
    dark_threshold: int = 185,
    dilate_px: int = 5,
    polarity: str = "dark_on_light",
    light_threshold: int = 210,
) -> Image.Image:
    gray = crop.convert("L")
    if polarity == "light_on_dark":
        bright = gray.point(lambda value: 255 if value > light_threshold else 0, mode="L")
        dark_context = gray.point(lambda value: 255 if value < dark_threshold else 0, mode="L").filter(ImageFilter.MaxFilter(13))
        text = ImageChops.multiply(bright, dark_context).filter(ImageFilter.MaxFilter(13))
        text = ImageChops.multiply(bright, text)
    else:
        text = gray.point(lambda value: 255 if value < dark_threshold else 0, mode="L")
        text = _remove_large_solid_icon_components(text, gray)
    filter_size = max(3, dilate_px if dilate_px % 2 == 1 else dilate_px + 1)
    return text.filter(ImageFilter.MaxFilter(filter_size))


def build_gpt_edit_mask(text_mask: Image.Image) -> Image.Image:
    alpha = ImageChops.invert(text_mask.convert("L"))
    return Image.merge("RGBA", [Image.new("L", text_mask.size, 255)] * 3 + [alpha])


def diffuse_inpaint(crop: Image.Image, text_mask: Image.Image, iterations: int = 80) -> Image.Image:
    array = np.array(crop.convert("RGB"), dtype=np.float32)
    mask = np.array(text_mask.convert("L")) > 0
    if not bool(mask.any()):
        return crop.convert("RGB")

    array[mask] = _initial_fill(array, mask)
    for _ in range(max(1, iterations)):
        averaged = _neighbor_average(array)
        array[mask] = averaged[mask]
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), mode="RGB")


def opencv_inpaint(crop: Image.Image, text_mask: Image.Image, method: str = "opencv_telea") -> Image.Image:
    cv2 = _require_cv2()

    flags = cv2.INPAINT_TELEA if method == "opencv_telea" else cv2.INPAINT_NS
    image_array = np.array(crop.convert("RGB"), dtype=np.uint8)
    mask_array = np.array(text_mask.convert("L"), dtype=np.uint8)
    result = cv2.inpaint(image_array, mask_array, 3, flags)
    return Image.fromarray(result, mode="RGB")


def dark_panel_fill(crop: Image.Image, text_mask: Image.Image) -> Image.Image:
    array = np.array(crop.convert("RGB"), dtype=np.uint8)
    mask = np.array(text_mask.convert("L")) > 0
    if not bool(mask.any()):
        return crop.convert("RGB")

    gray = np.array(crop.convert("L"), dtype=np.uint8)
    background = (~mask) & (gray < 140)
    if not bool(background.any()):
        background = ~mask
    fill_color = np.median(array[background], axis=0).astype(np.uint8)
    result = array.copy()
    result[mask] = fill_color
    return Image.fromarray(result, mode="RGB")


def texture_blur_fill(crop: Image.Image, text_mask: Image.Image) -> Image.Image:
    mask = _texture_blur_mask(crop, text_mask)
    if not bool((np.array(mask.convert("L"), dtype=np.uint8) > 0).any()):
        return crop.convert("RGB")
    radius = max(10, min(40, int(round(min(crop.size) * 0.16))))
    blurred = crop.convert("RGB").filter(ImageFilter.GaussianBlur(radius=radius))
    result = crop.convert("RGB").copy()
    result.paste(blurred, (0, 0), mask)
    return result


def flat_median_fill(crop: Image.Image, text_mask: Image.Image) -> Image.Image:
    array = np.array(crop.convert("RGB"), dtype=np.uint8)
    mask = np.array(text_mask.convert("L")) > 0
    if not bool(mask.any()):
        return crop.convert("RGB")

    background = ~mask
    if not bool(background.any()):
        fill_color = np.array([255, 255, 255], dtype=np.uint8)
    else:
        fill_color = np.median(array[background], axis=0).astype(np.uint8)
    result = array.copy()
    result[mask] = fill_color
    return Image.fromarray(result, mode="RGB")


def _remove_large_solid_icon_components(mask: Image.Image, gray: Image.Image | None = None) -> Image.Image:
    array = np.array(mask.convert("L"), dtype=np.uint8)
    binary = array > 0
    if not bool(binary.any()):
        return mask

    height, width = binary.shape
    min_area = max(400, int(height * width * 0.045))
    strict_binary = binary
    if gray is not None:
        strict_binary = np.array(gray.convert("L"), dtype=np.uint8) < 80
    visited = np.zeros_like(strict_binary, dtype=bool)
    result = binary.copy()
    for start_y, start_x in zip(*np.where(strict_binary & ~visited)):
        pixels = _component_pixels(strict_binary, visited, int(start_x), int(start_y))
        if _looks_like_solid_icon(pixels, min_area):
            ys, xs = zip(*pixels)
            margin = 1
            y1 = max(0, min(ys) - margin)
            y2 = min(height, max(ys) + margin + 1)
            x1 = max(0, min(xs) - margin)
            x2 = min(width, max(xs) + margin + 1)
            result[y1:y2, x1:x2] = False

    return Image.fromarray((result.astype(np.uint8) * 255), mode="L")


def _component_pixels(binary: np.ndarray, visited: np.ndarray, start_x: int, start_y: int) -> list[tuple[int, int]]:
    stack = [(start_x, start_y)]
    visited[start_y, start_x] = True
    pixels: list[tuple[int, int]] = []
    height, width = binary.shape
    while stack:
        x, y = stack.pop()
        pixels.append((y, x))
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            if visited[ny, nx] or not binary[ny, nx]:
                continue
            visited[ny, nx] = True
            stack.append((nx, ny))
    return pixels


def _looks_like_solid_icon(pixels: list[tuple[int, int]], min_area: int) -> bool:
    area = len(pixels)
    if area < min_area:
        return False
    ys, xs = zip(*pixels)
    component_width = max(xs) - min(xs) + 1
    component_height = max(ys) - min(ys) + 1
    aspect = component_width / max(1, component_height)
    fill_ratio = area / max(1, component_width * component_height)
    return 0.65 <= aspect <= 1.55 and fill_ratio >= 0.38 and _has_diamond_profile(pixels)


def _has_diamond_profile(pixels: list[tuple[int, int]]) -> bool:
    ys, xs = zip(*pixels)
    min_y, max_y = min(ys), max(ys)
    min_x, max_x = min(xs), max(xs)
    height = max_y - min_y + 1
    width = max_x - min_x + 1
    if height < 12 or width < 12:
        return False
    rows = np.zeros((height, width), dtype=bool)
    rows[np.array(ys) - min_y, np.array(xs) - min_x] = True
    row_widths = rows.sum(axis=1)
    nonempty = row_widths[row_widths > 0]
    if nonempty.size < 5:
        return False
    peak_index = int(np.argmax(row_widths))
    peak_width = int(row_widths[peak_index])
    if peak_width <= 0:
        return False
    edge_limit = peak_width * 0.45
    peak_centered = height * 0.25 <= peak_index <= height * 0.75
    narrow_edges = int(nonempty[0]) <= edge_limit and int(nonempty[-1]) <= edge_limit
    return peak_centered and narrow_edges


def _initial_fill(array: np.ndarray, mask: np.ndarray) -> np.ndarray:
    known = array[~mask]
    if known.size == 0:
        return np.array([255, 255, 255], dtype=np.float32)
    return np.median(known, axis=0)


def _neighbor_average(array: np.ndarray) -> np.ndarray:
    padded = np.pad(array, ((1, 1), (1, 1), (0, 0)), mode="edge")
    return (
        padded[:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
    ) / 4.0


def _require_cv2():
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise RuntimeError("opencv_inpaint_requires_cv2") from exc
    return cv2


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _save_before_after(before: Image.Image, after: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (before.width + after.width, max(before.height, after.height)), "white")
    canvas.paste(before.convert("RGB"), (0, 0))
    canvas.paste(after.convert("RGB"), (before.width, 0))
    canvas.save(path)


def _crop_external_mask(mask_path: str | Path, bbox: tuple[int, int, int, int], target_size: tuple[int, int]) -> Image.Image:
    with Image.open(mask_path) as image:
        mask = image.convert("L")
        crop = mask.crop(bbox)
    if crop.size != target_size:
        crop = crop.resize(target_size)
    return crop


def _dilate_mask(mask: Image.Image, dilate_px: int) -> Image.Image:
    filter_size = max(3, dilate_px if dilate_px % 2 == 1 else dilate_px + 1)
    return mask.convert("L").filter(ImageFilter.MaxFilter(filter_size))


def _texture_blur_mask(crop: Image.Image, text_mask: Image.Image) -> Image.Image:
    mask = text_mask.convert("L")
    binary = np.array(mask, dtype=np.uint8) > 0
    if not bool(binary.any()):
        return mask
    height, width = binary.shape
    row_coverage = float(binary.any(axis=1).mean())
    if height >= width * 3 and row_coverage >= 0.35:
        return Image.new("L", crop.size, 255)
    return mask.filter(ImageFilter.MaxFilter(11))


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"


def _canonical_method(method: str) -> str:
    return {
        "opencv-tela": "bt_opencv_tela",
        "opencv_tela": "bt_opencv_tela",
        "patchmatch": "bt_patchmatch",
        "aot": "bt_aot",
        "lama_mpe": "bt_lama_mpe",
        "lama_large_512px": "bt_lama_large",
        "texture-blur-fill": "texture_blur_fill",
    }.get(method, method)
