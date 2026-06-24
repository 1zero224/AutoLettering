from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from autolettering.experiment_grid import near_square_columns


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
    label_height = 22
    tile_w = min(220, max(96, max(image.width for _, image in tiles)))
    tile_h = min(260, max(96, max(image.height for _, image in tiles)))
    columns = near_square_columns(len(tiles), cell_width=tile_w + padding, cell_height=tile_h + label_height + padding)
    rows = (len(tiles) + columns - 1) // columns
    width = padding + columns * (tile_w + padding)
    height = padding + rows * (label_height + tile_h + padding)

    grid = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(grid)
    font = ImageFont.load_default()
    for index, (label, image) in enumerate(tiles):
        column = index % columns
        row = index // columns
        x = padding + column * (tile_w + padding)
        y = padding + row * (label_height + tile_h + padding)
        _draw_tile(grid, draw, font, label, image, x, y, label_height, tile_w, tile_h)

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
    draw.rectangle((x, y, x + tile_w, y + label_height), fill=(245, 245, 245), outline=(180, 180, 180))
    draw.text((x + 4, y + 5), safe_label, fill="black", font=font)
    box_y = y + label_height
    draw.rectangle((x, box_y, x + tile_w, box_y + tile_h), outline=(180, 180, 180), width=1)
    fitted = ImageOps.contain(image, (tile_w, tile_h), Image.Resampling.LANCZOS)
    paste_x = x + (tile_w - fitted.width) // 2
    paste_y = box_y + (tile_h - fitted.height) // 2
    grid.paste(fitted, (paste_x, paste_y))
