from __future__ import annotations

from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .candidates import generate_line_break_candidates
from .models import LayoutResult, TextMeasurement


def measure_text_layout(
    text: str,
    font_path: str | Path,
    font_size: int,
    line_spacing: int = 4,
    orientation: str = "horizontal",
) -> TextMeasurement:
    font = ImageFont.truetype(str(font_path), font_size)
    if orientation == "vertical":
        return _measure_vertical_text(text, font, line_spacing)

    scratch = Image.new("RGB", (1, 1), "white")
    draw = ImageDraw.Draw(scratch)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=line_spacing)
    return TextMeasurement(width=bbox[2] - bbox[0], height=bbox[3] - bbox[1])


def search_fitting_layout(
    text: str,
    font_path: str | Path,
    target_size: tuple[int, int],
    min_font_size: int = 12,
    max_font_size: int = 72,
    allow_overflow_ratio: float = 0.08,
    max_lines: int = 3,
    orientation: str | None = None,
    angle_degrees: float = 0.0,
) -> LayoutResult:
    target_width, target_height = target_size
    selected_orientation = orientation or _choose_orientation(target_width, target_height)
    candidates = _candidate_texts(text, max_lines, selected_orientation)
    best = _search_best_candidate(
        candidates,
        font_path,
        target_width,
        target_height,
        min_font_size,
        max_font_size,
        selected_orientation,
        angle_degrees,
    )
    if best is None:
        return _fallback_layout(text, font_path, target_width, target_height, min_font_size, selected_orientation, angle_degrees)

    line_breaks, font_size, measured = best
    return _layout_result(
        text,
        line_breaks,
        font_size,
        selected_orientation,
        target_width,
        target_height,
        measured,
        allow_overflow_ratio,
        angle_degrees=angle_degrees,
    )


def _search_best_candidate(
    candidates: list[str],
    font_path: str | Path,
    target_width: int,
    target_height: int,
    min_font_size: int,
    max_font_size: int,
    orientation: str,
    angle_degrees: float,
) -> tuple[str, int, TextMeasurement] | None:
    best: tuple[str, int, TextMeasurement] | None = None
    for line_breaks in candidates:
        for font_size in range(max_font_size, min_font_size - 1, -1):
            measured = measure_text_layout(line_breaks, font_path, font_size, orientation=orientation)
            footprint = _rotation_footprint(measured, angle_degrees)
            if footprint.width <= target_width and footprint.height <= target_height:
                if best is None or font_size > best[1]:
                    best = (line_breaks, font_size, footprint)
                break
    return best


def _fallback_layout(
    text: str,
    font_path: str | Path,
    target_width: int,
    target_height: int,
    font_size: int,
    orientation: str,
    angle_degrees: float,
) -> LayoutResult:
    measured = measure_text_layout(text, font_path, font_size, orientation=orientation)
    return _layout_result(
        text,
        text,
        font_size,
        orientation,
        target_width,
        target_height,
        measured,
        0.0,
        "overflow",
        angle_degrees,
    )


def _layout_result(
    text: str,
    line_breaks: str,
    font_size: int,
    orientation: str,
    target_width: int,
    target_height: int,
    measured: TextMeasurement,
    allow_overflow_ratio: float,
    failure_reason: str | None = None,
    angle_degrees: float = 0.0,
) -> LayoutResult:
    overflow = _overflow_ratio(measured.width, measured.height, target_width, target_height)
    status = "ok" if overflow <= allow_overflow_ratio else "failed"
    return LayoutResult(
        status=status,
        text=text,
        line_breaks=line_breaks,
        font_size=font_size,
        orientation=orientation,
        line_spacing=4,
        letter_spacing=0,
        angle_degrees=round(angle_degrees, 1),
        target_width=target_width,
        target_height=target_height,
        measured_width=measured.width,
        measured_height=measured.height,
        overflow_ratio=round(overflow, 4),
        failure_reason=failure_reason,
    )


def _overflow_ratio(width: int, height: int, target_width: int, target_height: int) -> float:
    width_over = max(0, width - target_width) / max(1, target_width)
    height_over = max(0, height - target_height) / max(1, target_height)
    return max(width_over, height_over)


def _rotation_footprint(measured: TextMeasurement, angle_degrees: float) -> TextMeasurement:
    if abs(angle_degrees) < 0.1:
        return measured
    angle = radians(abs(angle_degrees))
    width = measured.width * cos(angle) + measured.height * sin(angle)
    height = measured.width * sin(angle) + measured.height * cos(angle)
    return TextMeasurement(width=int(round(width)), height=int(round(height)))


def _choose_orientation(target_width: int, target_height: int) -> str:
    return "vertical" if target_height >= target_width * 1.35 else "horizontal"


def _candidate_texts(text: str, max_lines: int, orientation: str) -> list[str]:
    if orientation == "vertical":
        stripped = "\n".join(part.strip() for part in text.splitlines() if part.strip())
        if stripped:
            return [stripped]
        return ["".join(text.split())]
    return generate_line_break_candidates(text, max_lines=max_lines)


def _measure_vertical_text(text: str, font: ImageFont.FreeTypeFont, line_spacing: int) -> TextMeasurement:
    columns = [[char for char in column if char.strip()] for column in text.splitlines()]
    columns = [column for column in columns if column]
    if not columns:
        return TextMeasurement(width=0, height=0)

    scratch = Image.new("RGB", (1, 1), "white")
    draw = ImageDraw.Draw(scratch)
    column_sizes = [_measure_vertical_column(draw, column, font, line_spacing) for column in columns]
    width = sum(size.width for size in column_sizes) + line_spacing * max(0, len(column_sizes) - 1)
    height = max(size.height for size in column_sizes)
    return TextMeasurement(width=width, height=height)


def _measure_vertical_column(
    draw: ImageDraw.ImageDraw,
    chars: list[str],
    font: ImageFont.FreeTypeFont,
    line_spacing: int,
) -> TextMeasurement:
    boxes = [draw.textbbox((0, 0), char, font=font) for char in chars]
    width = max(box[2] - box[0] for box in boxes)
    height = sum(box[3] - box[1] for box in boxes) + line_spacing * max(0, len(chars) - 1)
    return TextMeasurement(width=width, height=height)
