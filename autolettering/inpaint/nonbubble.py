from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from .balloons import lama_large_inpaint as balloons_lama_large_inpaint
from .balloons import patchmatch_inpaint as balloons_patchmatch_inpaint
from .models import NonBubbleInpaintResult


def inpaint_nonbubble_text(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    output_dir: str | Path,
    record_id: str,
    method: str = "local_diffusion",
    polarity: str = "dark_on_light",
    dark_threshold: int = 185,
    light_threshold: int = 210,
    mask_dilate_px: int = 5,
    iterations: int = 80,
) -> NonBubbleInpaintResult:
    output_root = Path(output_dir)
    safe_id = _safe_name(record_id)
    with Image.open(image_path) as image:
        crop = image.convert("RGB").crop(bbox)

    text_mask = build_text_mask(crop, dark_threshold, mask_dilate_px, polarity=polarity, light_threshold=light_threshold)
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
    method: str = "local_diffusion",
    iterations: int = 80,
) -> tuple[str, Image.Image]:
    if method == "local_diffusion":
        return "local_diffusion_inpaint", diffuse_inpaint(crop, text_mask, iterations)
    if method in {"opencv_telea", "opencv_ns"}:
        return f"{method}_inpaint", opencv_inpaint(crop, text_mask, method)
    if method == "dark_panel_fill":
        return "dark_panel_fill", dark_panel_fill(crop, text_mask)
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


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
