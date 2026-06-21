from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import LayoutResult


def render_layout_preview(
    layout: LayoutResult,
    font_path: str | Path,
    output_path: str | Path,
    canvas_size: tuple[int, int] | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    size = canvas_size or (layout.target_width, layout.target_height)
    image = _render_text_layer(layout, font_path, size)
    if abs(layout.angle_degrees) >= 0.1:
        image = _rotate_within_canvas(image, layout.angle_degrees, size)
    image.save(output)
    return output


def _render_text_layer(layout: LayoutResult, font_path: str | Path, size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    font = ImageFont.truetype(str(font_path), layout.font_size)
    draw = ImageDraw.Draw(image)
    if layout.orientation == "vertical":
        _draw_vertical(draw, layout, font, size)
        return image

    _draw_horizontal(draw, layout, font, size)
    return image


def _draw_horizontal(
    draw: ImageDraw.ImageDraw,
    layout: LayoutResult,
    font: ImageFont.FreeTypeFont,
    size: tuple[int, int],
) -> None:
    bbox = draw.multiline_textbbox((0, 0), layout.line_breaks, font=font, spacing=layout.line_spacing)
    x = max(0, (size[0] - (bbox[2] - bbox[0])) // 2 - bbox[0])
    y = max(0, (size[1] - (bbox[3] - bbox[1])) // 2 - bbox[1])
    draw.multiline_text((x, y), layout.line_breaks, fill=(0, 0, 0, 255), font=font, spacing=layout.line_spacing)


def _rotate_within_canvas(image: Image.Image, angle_degrees: float, size: tuple[int, int]) -> Image.Image:
    rotated = image.rotate(angle_degrees, expand=True, resample=Image.Resampling.BICUBIC)
    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    x = (size[0] - rotated.width) // 2
    y = (size[1] - rotated.height) // 2
    canvas.alpha_composite(rotated, (x, y))
    return canvas


def _draw_vertical(
    draw: ImageDraw.ImageDraw,
    layout: LayoutResult,
    font: ImageFont.FreeTypeFont,
    size: tuple[int, int],
) -> None:
    chars = [char for char in layout.line_breaks if char != "\n"]
    boxes = [draw.textbbox((0, 0), char, font=font) for char in chars]
    widths = [box[2] - box[0] for box in boxes]
    heights = [box[3] - box[1] for box in boxes]
    total_height = sum(heights) + layout.line_spacing * max(0, len(chars) - 1)
    y = max(0, (size[1] - total_height) // 2)
    center_x = size[0] // 2

    for char, box, width, height in zip(chars, boxes, widths, heights):
        x = max(0, center_x - width // 2 - box[0])
        draw.text((x, y - box[1]), char, fill=(0, 0, 0, 255), font=font)
        y += height + layout.line_spacing
