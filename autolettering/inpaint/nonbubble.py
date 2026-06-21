from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from .models import NonBubbleInpaintResult


def inpaint_nonbubble_text(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    output_dir: str | Path,
    record_id: str,
    dark_threshold: int = 185,
    mask_dilate_px: int = 5,
    iterations: int = 80,
) -> NonBubbleInpaintResult:
    output_root = Path(output_dir)
    safe_id = _safe_name(record_id)
    with Image.open(image_path) as image:
        crop = image.convert("RGB").crop(bbox)

    text_mask = build_text_mask(crop, dark_threshold, mask_dilate_px)
    cleaned = diffuse_inpaint(crop, text_mask, iterations)
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
        method="local_diffusion_inpaint",
        bbox=bbox,
        input_crop_path=input_path,
        text_mask_path=text_mask_path,
        gpt_mask_path=gpt_mask_path,
        cleaned_crop_path=cleaned_path,
        before_after_path=before_after_path,
        dark_pixel_count=int(np.array(text_mask).sum() // 255),
    )


def build_text_mask(crop: Image.Image, dark_threshold: int = 185, dilate_px: int = 5) -> Image.Image:
    gray = crop.convert("L")
    dark = gray.point(lambda value: 255 if value < dark_threshold else 0, mode="L")
    filter_size = max(3, dilate_px if dilate_px % 2 == 1 else dilate_px + 1)
    return dark.filter(ImageFilter.MaxFilter(filter_size))


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
