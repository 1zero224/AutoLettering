from __future__ import annotations

from pathlib import Path

from PIL import Image


def compose_page_preview(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    cleaned_crop_path: str | Path,
    layout_preview_path: str | Path,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        canvas = image.convert("RGB")
    cleaned = _resize_to_bbox(cleaned_crop_path, bbox).convert("RGB")
    overlay = _resize_to_bbox(layout_preview_path, bbox).convert("RGBA")

    x1, y1, _, _ = bbox
    canvas.paste(cleaned, (x1, y1))
    canvas.paste(overlay, (x1, y1), overlay)
    canvas.save(output)
    return output


def compose_page_records(image_path: str | Path, records: list[dict], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        canvas = image.convert("RGB")

    for record in records:
        bbox = tuple(record["bbox"])
        cleaned = _resize_to_bbox(record["cleaned_crop_path"], bbox).convert("RGB")
        overlay = _resize_to_bbox(record["layout_preview_path"], bbox).convert("RGBA")
        x1, y1, _, _ = bbox
        canvas.paste(cleaned, (x1, y1))
        canvas.paste(overlay, (x1, y1), overlay)

    canvas.save(output)
    return output


def _resize_to_bbox(image_path: str | Path, bbox: tuple[int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2 = bbox
    target_size = (x2 - x1, y2 - y1)
    with Image.open(image_path) as image:
        source = image.copy()
    if source.size == target_size:
        return source
    return source.resize(target_size)
