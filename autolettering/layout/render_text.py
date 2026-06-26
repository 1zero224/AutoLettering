from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import LayoutResult
from .measure import VERTICAL_OPTICAL_ADVANCE_RATIO
from .vertical_text import vertical_digit_group_scale, vertical_text_tokens


def render_layout_preview(
    layout: LayoutResult,
    font_path: str | Path,
    output_path: str | Path,
    canvas_size: tuple[int, int] | None = None,
    text_color: tuple[int, int, int, int] = (0, 0, 0, 255),
    vertical_column_order: str = "rtl",
    vertical_align: str | None = None,
) -> Path:
    if vertical_column_order not in {"rtl", "ltr"}:
        raise ValueError("vertical_column_order must be 'rtl' or 'ltr'")
    resolved_vertical_align = _resolve_vertical_align(layout, vertical_align)
    if resolved_vertical_align not in {"center", "top"}:
        raise ValueError("vertical_align must be 'center' or 'top'")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    size = canvas_size or (layout.target_width, layout.target_height)
    image = _render_text_layer(layout, font_path, size, text_color, vertical_column_order, resolved_vertical_align)
    if abs(layout.angle_degrees) >= 0.1:
        image = _rotate_within_canvas(image, layout.angle_degrees, size)
    image = _recenter_visible_ink(image, recenter_y=resolved_vertical_align == "center")
    image.save(output)
    return output


def _resolve_vertical_align(layout: LayoutResult, vertical_align: str | None) -> str:
    if vertical_align is not None:
        return vertical_align
    return "top" if layout.orientation == "vertical" else "center"


def measure_preview_alignment(image_path: str | Path) -> dict:
    with Image.open(image_path) as image:
        rgba = image.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        return _alignment_metrics(rgba.size, bbox)


def _alignment_metrics(size: tuple[int, int], bbox: tuple[int, int, int, int] | None) -> dict:
    width, height = size
    if bbox is None:
        return {
            "canvas_width": width,
            "canvas_height": height,
            "ink_bbox": None,
            "ink_width": 0,
            "ink_height": 0,
            "horizontal_center_offset_px": None,
            "vertical_center_offset_px": None,
        }

    left, top, right, bottom = bbox
    ink_center_x = (left + right) / 2
    ink_center_y = (top + bottom) / 2
    return {
        "canvas_width": width,
        "canvas_height": height,
        "ink_bbox": [left, top, right, bottom],
        "ink_width": right - left,
        "ink_height": bottom - top,
        "horizontal_center_offset_px": round(ink_center_x - width / 2, 2),
        "vertical_center_offset_px": round(ink_center_y - height / 2, 2),
    }


def _recenter_visible_ink(image: Image.Image, recenter_y: bool = True) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image

    metrics = _alignment_metrics(image.size, bbox)
    offset_x = metrics["horizontal_center_offset_px"]
    offset_y = metrics["vertical_center_offset_px"]
    if offset_x is None or offset_y is None:
        return image

    dy = -round(offset_y) if recenter_y else 0
    return _translate_layer(image, -round(offset_x), dy)


def _translate_layer(image: Image.Image, dx: int, dy: int) -> Image.Image:
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 0))
    canvas.alpha_composite(image, (dx, dy))
    return canvas


def _render_text_layer(
    layout: LayoutResult,
    font_path: str | Path,
    size: tuple[int, int],
    text_color: tuple[int, int, int, int],
    vertical_column_order: str,
    vertical_align: str,
) -> Image.Image:
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    font = ImageFont.truetype(str(font_path), layout.font_size)
    draw = ImageDraw.Draw(image)
    if layout.orientation == "vertical":
        _draw_vertical(draw, layout, font, size, text_color, vertical_column_order, vertical_align)
        return image

    _draw_horizontal(draw, layout, font, size, text_color)
    return image


def _draw_horizontal(
    draw: ImageDraw.ImageDraw,
    layout: LayoutResult,
    font: ImageFont.FreeTypeFont,
    size: tuple[int, int],
    text_color: tuple[int, int, int, int],
) -> None:
    bbox = draw.multiline_textbbox((0, 0), layout.line_breaks, font=font, spacing=layout.line_spacing)
    x = max(0, (size[0] - (bbox[2] - bbox[0])) // 2 - bbox[0])
    y = max(0, (size[1] - (bbox[3] - bbox[1])) // 2 - bbox[1])
    draw.multiline_text((x, y), layout.line_breaks, fill=text_color, font=font, spacing=layout.line_spacing)


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
    text_color: tuple[int, int, int, int],
    vertical_column_order: str,
    vertical_align: str,
) -> None:
    columns = [vertical_text_tokens(column) for column in layout.line_breaks.splitlines()]
    columns = [column for column in columns if column]
    column_metrics = [_vertical_column_metrics(draw, column, font, layout.line_spacing) for column in columns]
    total_width = sum(item["width"] for item in column_metrics) + layout.line_spacing * max(0, len(column_metrics) - 1)
    left = max(0, (size[0] - total_width) // 2)
    if vertical_column_order == "ltr":
        x = left
        for column, metrics in zip(columns, column_metrics):
            _draw_vertical_column(draw, column, metrics, font, layout.line_spacing, x, size[1], text_color, vertical_align)
            x += metrics["width"] + layout.line_spacing
        return

    x = left + total_width
    for column, metrics in zip(columns, column_metrics):
        x -= metrics["width"]
        _draw_vertical_column(draw, column, metrics, font, layout.line_spacing, x, size[1], text_color, vertical_align)
        x -= layout.line_spacing


def _vertical_column_metrics(
    draw: ImageDraw.ImageDraw,
    chars: list[str],
    font: ImageFont.FreeTypeFont,
    line_spacing: int,
) -> dict:
    fonts = [_vertical_token_font(font, char) for char in chars]
    boxes = [draw.textbbox((0, 0), char, font=token_font) for char, token_font in zip(chars, fonts)]
    widths = [box[2] - box[0] for box in boxes]
    heights = [box[3] - box[1] for box in boxes]
    advances = [_vertical_token_advance(height, token_font) for height, token_font in zip(heights, fonts)]
    return {
        "fonts": fonts,
        "boxes": boxes,
        "widths": widths,
        "heights": heights,
        "advances": advances,
        "width": max(widths),
        "height": sum(advances) + line_spacing * max(0, len(chars) - 1),
    }


def _draw_vertical_column(
    draw: ImageDraw.ImageDraw,
    chars: list[str],
    metrics: dict,
    font: ImageFont.FreeTypeFont,
    line_spacing: int,
    x_left: int,
    canvas_height: int,
    text_color: tuple[int, int, int, int],
    vertical_align: str,
) -> None:
    y = 0 if vertical_align == "top" else max(0, (canvas_height - metrics["height"]) // 2)
    center_x = x_left + metrics["width"] // 2
    for char, token_font, box, width, _height, advance in zip(
        chars,
        metrics["fonts"],
        metrics["boxes"],
        metrics["widths"],
        metrics["heights"],
        metrics["advances"],
    ):
        x = max(0, center_x - width // 2 - box[0])
        draw.text((x, y - box[1]), char, fill=text_color, font=token_font)
        y += advance + line_spacing


def _vertical_token_font(font: ImageFont.FreeTypeFont, token: str) -> ImageFont.FreeTypeFont:
    scale = vertical_digit_group_scale(token)
    if scale >= 1.0:
        return font
    return font.font_variant(size=max(1, round(font.size * scale)))


def _vertical_token_advance(ink_height: int, token_font: ImageFont.FreeTypeFont) -> int:
    optical_cell = int(round(token_font.size * VERTICAL_OPTICAL_ADVANCE_RATIO))
    return max(ink_height, optical_cell)
