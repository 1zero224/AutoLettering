from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def near_square_columns(count: int, cell_width: int = 340, cell_height: int = 364) -> int:
    if count <= 0:
        return 1
    best_columns = 1
    best_score = float("inf")
    for columns in range(1, count + 1):
        rows = int(np.ceil(count / columns))
        ratio = (columns * cell_width) / max(1, rows * cell_height)
        score = abs(np.log(ratio))
        if score < best_score:
            best_columns = columns
            best_score = score
    return best_columns


def write_grid(
    output_path: Path,
    tiles: list[tuple[str, str | Path]],
    columns: int,
    tile_size: tuple[int, int] = (330, 330),
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    loaded = [(label, Image.open(path).convert("RGB")) for label, path in tiles]
    rows = int(np.ceil(len(loaded) / columns))
    tile_w, tile_h = tile_size
    label_h, pad = 24, 10
    sheet = Image.new("RGB", (pad + columns * (tile_w + pad), pad + rows * (tile_h + label_h + pad)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(loaded):
        col = index % columns
        row = index // columns
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + label_h + pad)
        draw.rectangle((x, y, x + tile_w, y + label_h), fill=(245, 245, 245), outline=(180, 180, 180))
        draw.text((x + 4, y + 6), label[:42], fill="black", font=font)
        thumb = image.copy()
        thumb.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
        draw.rectangle((x, y + label_h, x + tile_w, y + label_h + tile_h), outline=(210, 210, 210), fill="white")
        sheet.paste(thumb, (x + (tile_w - thumb.width) // 2, y + label_h + (tile_h - thumb.height) // 2))
    sheet.save(output_path)
    return output_path
