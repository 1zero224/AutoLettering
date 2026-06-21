from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def build_font_comparison_grid(
    source_crop_path: str | Path,
    candidates: list[tuple[str, str | Path]],
    output_path: str | Path,
    padding: int = 14,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    source = Image.open(source_crop_path).convert("RGB")
    previews = [(font_id, Image.open(path).convert("RGB")) for font_id, path in candidates]
    tiles = [("source", source), *previews]
    label_height = 18
    tile_w = max(image.width for _, image in tiles)
    tile_h = max(image.height for _, image in tiles)
    width = padding + len(tiles) * (tile_w + padding)
    height = padding * 2 + label_height + tile_h

    grid = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(grid)
    font = ImageFont.load_default()
    for index, (label, image) in enumerate(tiles):
        x = padding + index * (tile_w + padding)
        _draw_tile(grid, draw, font, label, image, x, padding, label_height, tile_w, tile_h)

    grid.save(output)
    return output


def _draw_tile(
    grid: Image.Image,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    label: str,
    image: Image.Image,
    x: int,
    y: int,
    label_height: int,
    tile_w: int,
    tile_h: int,
) -> None:
    safe_label = label[:24]
    draw.text((x, y), safe_label, fill="black", font=font)
    box_y = y + label_height
    draw.rectangle((x, box_y, x + tile_w, box_y + tile_h), outline=(180, 180, 180), width=1)
    paste_x = x + (tile_w - image.width) // 2
    paste_y = box_y + (tile_h - image.height) // 2
    grid.paste(image, (paste_x, paste_y))
