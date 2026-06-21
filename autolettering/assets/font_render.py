from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .fonts import FontRecord


def render_text_preview(
    font: FontRecord,
    text: str,
    output_path: str | Path,
    font_size: int = 48,
    padding: int = 18,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    drawable_text = text or " "
    pil_font = ImageFont.truetype(str(font.path), font_size)
    bbox = _text_bbox(drawable_text, pil_font)
    width = max(96, bbox[2] - bbox[0] + padding * 2)
    height = max(80, bbox[3] - bbox[1] + padding * 2)

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text((padding - bbox[0], padding - bbox[1]), drawable_text, fill="black", font=pil_font, spacing=4)
    image.save(output)
    return output


def _text_bbox(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, int, int]:
    scratch = Image.new("RGB", (1, 1), "white")
    draw = ImageDraw.Draw(scratch)
    return draw.multiline_textbbox((0, 0), text, font=font, spacing=4)
