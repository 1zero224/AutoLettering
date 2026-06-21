from __future__ import annotations

from pathlib import Path
from statistics import median

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .models import BubbleFillResult


def sample_border_color(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    inset: int = 4,
) -> tuple[int, int, int]:
    with Image.open(image_path) as image:
        source = image.convert("RGB")
        expanded = _expand_bbox(bbox, source.size, inset)
        pixels = _border_pixels(source, expanded, bbox)
    if not pixels:
        return (255, 255, 255)
    return tuple(int(median(channel)) for channel in zip(*pixels))


def fill_text_box(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    output_dir: str | Path,
    record_id: str,
) -> BubbleFillResult:
    output_root = Path(output_dir)
    safe_id = _safe_name(record_id)
    fill_color = sample_border_color(image_path, bbox)

    with Image.open(image_path) as image:
        source = image.convert("RGB")
        clean = source.copy()
        ImageDraw.Draw(clean).rectangle(bbox, fill=fill_color)
        before_crop = source.crop(bbox)
        cleaned_crop = clean.crop(bbox)

    before_path = output_root / "before" / f"{safe_id}.png"
    cleaned_path = output_root / "cleaned" / f"{safe_id}.png"
    before_after_path = output_root / "before_after" / f"{safe_id}.png"
    _save_crop(before_crop, before_path)
    _save_crop(cleaned_crop, cleaned_path)
    _save_before_after(before_crop, cleaned_crop, before_after_path)

    return BubbleFillResult(
        record_id=record_id,
        method="bubble_fill",
        bbox=bbox,
        fill_color=fill_color,
        before_crop_path=before_path,
        cleaned_crop_path=cleaned_path,
        before_after_path=before_after_path,
    )


def mask_fill_text_pixels(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    text_bbox: tuple[int, int, int, int],
    output_dir: str | Path,
    record_id: str,
    dark_threshold: int = 185,
    dilate_px: int = 5,
) -> BubbleFillResult:
    output_root = Path(output_dir)
    safe_id = _safe_name(record_id)
    fill_color = sample_border_color(image_path, text_bbox)

    with Image.open(image_path) as image:
        source = image.convert("RGB")
        clean = source.copy()
        before_crop = source.crop(bbox)
        local_mask = _text_mask(source, bbox, text_bbox, dark_threshold, dilate_px)
        fill_layer = Image.new("RGB", before_crop.size, fill_color)
        cleaned_crop = Image.composite(fill_layer, before_crop, local_mask)
        clean.paste(cleaned_crop, bbox[:2])

    before_path = output_root / "before" / f"{safe_id}.png"
    cleaned_path = output_root / "cleaned" / f"{safe_id}.png"
    before_after_path = output_root / "before_after" / f"{safe_id}.png"
    _save_crop(before_crop, before_path)
    _save_crop(cleaned_crop, cleaned_path)
    _save_before_after(before_crop, cleaned_crop, before_after_path)

    return BubbleFillResult(
        record_id=record_id,
        method="bubble_mask_fill",
        bbox=bbox,
        fill_color=fill_color,
        before_crop_path=before_path,
        cleaned_crop_path=cleaned_path,
        before_after_path=before_after_path,
    )


def _text_mask(
    source: Image.Image,
    bbox: tuple[int, int, int, int],
    text_bbox: tuple[int, int, int, int],
    dark_threshold: int,
    dilate_px: int,
) -> Image.Image:
    crop = source.crop(bbox)
    text_local = _offset_bbox(text_bbox, bbox)
    text_crop = source.crop(text_bbox).convert("L")
    dark = text_crop.point(lambda value: 255 if value < dark_threshold else 0, mode="L")
    filter_size = max(3, dilate_px if dilate_px % 2 == 1 else dilate_px + 1)
    dark = dark.filter(ImageFilter.MaxFilter(filter_size))
    mask = Image.new("L", crop.size, 0)
    mask.paste(dark, text_local[:2])
    return mask


def _offset_bbox(
    inner: tuple[int, int, int, int],
    outer: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = inner
    ox1, oy1, _, _ = outer
    return x1 - ox1, y1 - oy1, x2 - ox1, y2 - oy1


def _border_pixels(
    image: Image.Image,
    outer: tuple[int, int, int, int],
    inner: tuple[int, int, int, int],
) -> list[tuple[int, int, int]]:
    pixels: list[tuple[int, int, int]] = []
    ox1, oy1, ox2, oy2 = outer
    ix1, iy1, ix2, iy2 = inner
    for y in range(oy1, oy2):
        for x in range(ox1, ox2):
            if ix1 <= x < ix2 and iy1 <= y < iy2:
                continue
            pixels.append(image.getpixel((x, y)))
    return pixels


def _expand_bbox(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
    inset: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    width, height = image_size
    return max(0, x1 - inset), max(0, y1 - inset), min(width, x2 + inset), min(height, y2 + inset)


def _save_crop(image: Image.Image, path: Path) -> None:
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
