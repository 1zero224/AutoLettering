from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def draw_page_debug_overlay(
    page_preview_path: str | Path,
    records: list[dict],
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(page_preview_path) as image:
        canvas = image.convert("RGB")

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, record in enumerate(records, start=1):
        _draw_record_marker(draw, tuple(record["bbox"]), f"#{index}", font)

    canvas.save(output)
    return output


def _draw_record_marker(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[int, int, int, int],
    label: str,
    font: ImageFont.ImageFont,
) -> None:
    x1, y1, x2, y2 = bbox
    draw.rectangle((x1, y1, x2, y2), outline=(255, 0, 0), width=3)
    label_box = draw.textbbox((x1, y1), label, font=font)
    width = label_box[2] - label_box[0] + 6
    height = label_box[3] - label_box[1] + 4
    label_y = max(0, y1 - height)
    draw.rectangle((x1, label_y, x1 + width, label_y + height), fill=(255, 0, 0))
    draw.text((x1 + 3, label_y + 2), label, fill=(255, 255, 255), font=font)
