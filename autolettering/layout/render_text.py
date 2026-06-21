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
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    font = ImageFont.truetype(str(font_path), layout.font_size)
    draw = ImageDraw.Draw(image)
    bbox = draw.multiline_textbbox((0, 0), layout.line_breaks, font=font, spacing=layout.line_spacing)
    x = max(0, (size[0] - (bbox[2] - bbox[0])) // 2 - bbox[0])
    y = max(0, (size[1] - (bbox[3] - bbox[1])) // 2 - bbox[1])
    draw.multiline_text((x, y), layout.line_breaks, fill=(0, 0, 0, 255), font=font, spacing=layout.line_spacing)
    image.save(output)
    return output
