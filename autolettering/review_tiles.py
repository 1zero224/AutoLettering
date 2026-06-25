from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def write_segmented_review_tile(
    source_path: str | Path,
    output_path: str | Path,
    size: tuple[int, int] = (340, 620),
    max_segment_height: int = 420,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        tile = segmented_review_tile(image.convert("RGB"), size=size, max_segment_height=max_segment_height)
    tile.save(output)
    return output


def segmented_review_tile(
    image: Image.Image,
    size: tuple[int, int] = (340, 620),
    max_segment_height: int = 420,
) -> Image.Image:
    tile = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(tile)
    segments = _review_segments(image.convert("RGB"), max_segment_height)
    columns = 1 if len(segments) == 1 else 2
    rows = math.ceil(len(segments) / columns)
    padding, label_height = 8, 18
    cell_width = (size[0] - padding * (columns + 1)) // columns
    cell_height = (size[1] - padding * (rows + 1)) // rows
    font = _font(12)
    for index, (label, segment) in enumerate(segments):
        column = index % columns
        row = index // columns
        x = padding + column * (cell_width + padding)
        y = padding + row * (cell_height + padding)
        draw.rectangle((x, y, x + cell_width, y + cell_height), outline=(185, 185, 185), fill="white")
        draw.text((x + 4, y + 3), label, fill=(45, 45, 45), font=font)
        fitted = _fit_segment(segment, (cell_width - 8, cell_height - label_height - 8))
        tile.paste(
            fitted,
            (x + (cell_width - fitted.width) // 2, y + label_height + (cell_height - label_height - fitted.height) // 2),
        )
    return tile


def _review_segments(image: Image.Image, max_segment_height: int) -> list[tuple[str, Image.Image]]:
    if image.height <= max_segment_height:
        return [("FULL", image)]
    segment_count = min(4, max(2, math.ceil(image.height / max_segment_height)))
    segments: list[tuple[str, Image.Image]] = []
    for index in range(segment_count):
        y1 = round(image.height * index / segment_count)
        y2 = round(image.height * (index + 1) / segment_count)
        segments.append((_segment_label(index + 1, segment_count), image.crop((0, y1, image.width, y2))))
    return segments


def _segment_label(index: int, total: int) -> str:
    if index == 1:
        return f"{index}/{total} TOP"
    if index == total:
        return f"{index}/{total} BOTTOM"
    return f"{index}/{total} MIDDLE"


def _fit_segment(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    max_width, max_height = size
    scale = min(max_width / max(1, image.width), max_height / max(1, image.height), 3.0)
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    return image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()
