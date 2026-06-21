from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .candidates import generate_line_break_candidates
from .models import LayoutResult, TextMeasurement


def measure_text_layout(
    text: str,
    font_path: str | Path,
    font_size: int,
    line_spacing: int = 4,
) -> TextMeasurement:
    font = ImageFont.truetype(str(font_path), font_size)
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
) -> LayoutResult:
    target_width, target_height = target_size
    candidates = generate_line_break_candidates(text, max_lines=max_lines)
    best = _search_best_candidate(candidates, font_path, target_width, target_height, min_font_size, max_font_size)
    if best is None:
        return _fallback_layout(text, font_path, target_width, target_height, min_font_size)

    line_breaks, font_size, measured = best
    return _layout_result(text, line_breaks, font_size, target_width, target_height, measured, allow_overflow_ratio)


def _search_best_candidate(
    candidates: list[str],
    font_path: str | Path,
    target_width: int,
    target_height: int,
    min_font_size: int,
    max_font_size: int,
) -> tuple[str, int, TextMeasurement] | None:
    best: tuple[str, int, TextMeasurement] | None = None
    for line_breaks in candidates:
        for font_size in range(max_font_size, min_font_size - 1, -1):
            measured = measure_text_layout(line_breaks, font_path, font_size)
            if measured.width <= target_width and measured.height <= target_height:
                if best is None or font_size > best[1]:
                    best = (line_breaks, font_size, measured)
                break
    return best


def _fallback_layout(text: str, font_path: str | Path, target_width: int, target_height: int, font_size: int) -> LayoutResult:
    measured = measure_text_layout(text, font_path, font_size)
    return _layout_result(text, text, font_size, target_width, target_height, measured, 0.0, "overflow")


def _layout_result(
    text: str,
    line_breaks: str,
    font_size: int,
    target_width: int,
    target_height: int,
    measured: TextMeasurement,
    allow_overflow_ratio: float,
    failure_reason: str | None = None,
) -> LayoutResult:
    overflow = _overflow_ratio(measured.width, measured.height, target_width, target_height)
    status = "ok" if overflow <= allow_overflow_ratio else "failed"
    return LayoutResult(
        status=status,
        text=text,
        line_breaks=line_breaks,
        font_size=font_size,
        orientation="horizontal",
        line_spacing=4,
        letter_spacing=0,
        angle_degrees=0.0,
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
