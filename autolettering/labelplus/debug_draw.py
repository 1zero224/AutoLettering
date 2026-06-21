from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import ManifestImage, ProjectManifest


def draw_label_point_pages(manifest: ProjectManifest, output_dir: str | Path) -> list[Path]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    output_paths: list[Path] = []
    for image in manifest.images:
        output_path = target_dir / image.image_name
        _draw_one_page(image, output_path)
        output_paths.append(output_path)
    return output_paths


def _draw_one_page(image: ManifestImage, output_path: Path) -> None:
    with Image.open(image.image_path) as source:
        canvas = source.convert("RGB")

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    for label in image.labels:
        color = (220, 30, 30) if label.group_id == 1 else (30, 90, 220)
        radius = max(7, min(canvas.size) // 120)
        x, y = label.x_px, label.y_px
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=3)
        draw.line((x - radius * 2, y, x + radius * 2, y), fill=color, width=2)
        draw.line((x, y - radius * 2, x, y + radius * 2), fill=color, width=2)

        text = str(label.record_index)
        text_box = draw.textbbox((0, 0), text, font=font)
        text_w = text_box[2] - text_box[0]
        text_h = text_box[3] - text_box[1]
        tx = min(max(x + radius + 3, 0), canvas.width - text_w - 4)
        ty = min(max(y - radius - 3, 0), canvas.height - text_h - 4)
        draw.rectangle((tx - 2, ty - 2, tx + text_w + 2, ty + text_h + 2), fill=(255, 255, 255))
        draw.text((tx, ty), text, fill=color, font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)

