from __future__ import annotations

from pathlib import Path

from PIL import Image


def compose_page_preview(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    cleaned_crop_path: str | Path,
    layout_preview_path: str | Path,
    output_path: str | Path,
    text_bbox: tuple[int, int, int, int] | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        canvas = image.convert("RGB")
    cleaned = _resize_to_bbox(cleaned_crop_path, bbox).convert("RGB")
    overlay_bbox = text_bbox or bbox
    overlay = _resize_to_bbox(layout_preview_path, overlay_bbox).convert("RGBA")

    x1, y1, _, _ = bbox
    text_x1, text_y1, _, _ = overlay_bbox
    canvas.paste(cleaned, (x1, y1))
    canvas.paste(overlay, (text_x1, text_y1), overlay)
    canvas.save(output)
    return output


def compose_page_records(image_path: str | Path, records: list[dict], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        canvas = image.convert("RGB")

    _paste_cleaned_crops(canvas, records)
    _paste_text_overlays(canvas, records)

    canvas.save(output)
    return output


def compose_page_stages(
    image_path: str | Path,
    records: list[dict],
    original_output_path: str | Path,
    cleaned_output_path: str | Path,
    final_output_path: str | Path,
) -> dict[str, Path]:
    original_path = Path(original_output_path)
    cleaned_path = Path(cleaned_output_path)
    final_path = Path(final_output_path)
    original_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as image:
        original = image.convert("RGB")
    cleaned_canvas = original.copy()
    final_canvas = original.copy()

    _paste_cleaned_crops(cleaned_canvas, records)
    final_canvas = cleaned_canvas.copy()
    _paste_text_overlays(final_canvas, records)

    original.save(original_path)
    cleaned_canvas.save(cleaned_path)
    final_canvas.save(final_path)
    return {
        "original_page_path": original_path,
        "cleaned_page_path": cleaned_path,
        "page_preview_path": final_path,
    }


def _paste_cleaned_crops(canvas: Image.Image, records: list[dict]) -> None:
    for record in records:
        bbox = tuple(record["bbox"])
        cleaned = _resize_to_bbox(record["cleaned_crop_path"], bbox).convert("RGB")
        mask = _cleanup_mask(record, bbox)
        x1, y1, _, _ = bbox
        canvas.paste(cleaned, (x1, y1), mask)


def _paste_text_overlays(canvas: Image.Image, records: list[dict]) -> None:
    for record in records:
        if not record.get("text_overlay_required", True):
            continue
        text_bbox = tuple(record.get("text_bbox") or record["bbox"])
        overlay = _resize_to_bbox(record["layout_preview_path"], text_bbox).convert("RGBA")
        text_x1, text_y1, _, _ = text_bbox
        canvas.paste(overlay, (text_x1, text_y1), overlay)


def _cleanup_mask(record: dict, bbox: tuple[int, int, int, int]) -> Image.Image | None:
    mask_path = record.get("cleanup_mask_path")
    if not mask_path:
        return None
    return _resize_to_bbox(mask_path, bbox).convert("L")


def _resize_to_bbox(image_path: str | Path, bbox: tuple[int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2 = bbox
    target_size = (x2 - x1, y2 - y1)
    with Image.open(image_path) as image:
        source = image.copy()
    if source.size == target_size:
        return source
    return source.resize(target_size)
