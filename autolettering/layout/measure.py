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
        0.0,
        max_lines,
    )
    if best is None and allow_overflow_ratio > 0.0:
        best = _search_best_candidate(
            candidates,
            font_path,
            target_width,
            target_height,
            min_font_size,
            max_font_size,
            selected_orientation,
            angle_degrees,
            allow_overflow_ratio,
            max_lines,
        )
    if best is None:
        return _fallback_layout(
            text,
            font_path,
            target_width,
            target_height,
            min_font_size,
            selected_orientation,
            angle_degrees,
            allow_overflow_ratio,
        )

    line_breaks, font_size, measured, line_spacing = best
    return _layout_result(
        text,
        line_breaks,
        font_size,
        selected_orientation,
        target_width,
        target_height,
        measured,
        allow_overflow_ratio,
        line_spacing=line_spacing,
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
    allow_overflow_ratio: float,
    max_lines: int,
) -> tuple[str, int, TextMeasurement, int] | None:
    fitting: list[tuple[str, int, TextMeasurement, int]] = []
    for line_breaks in candidates:
        for line_spacing in _line_spacing_candidates(orientation, max_lines):
            for font_size in range(max_font_size, min_font_size - 1, -1):
                measured = measure_text_layout(
                    line_breaks,
                    font_path,
                    font_size,
                    line_spacing=line_spacing,
                    orientation=orientation,
                )
                footprint = _rotation_footprint(measured, angle_degrees)
                overflow = _overflow_ratio(footprint.width, footprint.height, target_width, target_height)
                if overflow <= allow_overflow_ratio:
                    fitting.append((line_breaks, font_size, footprint, line_spacing))
                    break
    if not fitting:
        return None

    best_font_size = max(item[1] for item in fitting)
    return max(
        fitting,
        key=lambda item: _layout_score(
            item[0],
            candidates,
            item[1],
            item[2],
            item[3],
            target_height,
            orientation,
            best_font_size,
        ),
    )


def _line_spacing_candidates(orientation: str, max_lines: int) -> list[int]:
    return [0, 1, 2, 4] if orientation == "vertical" and max_lines > 1 else [4]


def _layout_score(
    line_breaks: str,
    candidates: list[str],
    font_size: int,
    measured: TextMeasurement,
    line_spacing: int,
    target_height: int,
    orientation: str,
    best_font_size: int,
) -> tuple[int, float, int, int, int]:
    if orientation != "vertical":
        return 0, 0.0, font_size, 0, 0
    phrase_bonus = _explicit_break_bonus(line_breaks, candidates, font_size, best_font_size)
    margin_score = _vertical_margin_score(measured, target_height)
    density_penalty = -abs((measured.height / max(1, target_height)) - 0.9)
    size_score = font_size / max(1, best_font_size)
    return phrase_bonus, size_score, margin_score + density_penalty, -line_spacing, -len(line_breaks)


def _explicit_break_bonus(line_breaks: str, candidates: list[str], font_size: int, best_font_size: int) -> int:
    explicit = candidates[0] if candidates else ""
    if line_breaks != explicit or "\n" not in explicit or not _has_title_style_vertical_columns(explicit):
        return 0
    return 1 if font_size / best_font_size >= 0.7 else 0


def _has_title_style_vertical_columns(line_breaks: str) -> bool:
    lengths = [len(part.strip()) for part in line_breaks.splitlines() if part.strip()]
    if len(lengths) < 3:
        return False
    return max(lengths) >= min(lengths) * 2


def _vertical_margin_score(measured: TextMeasurement, target_height: int) -> float:
    bottom_margin = target_height - measured.height
    if bottom_margin < 0:
        return -10.0
    return min(bottom_margin, 12) / 12.0


def _fallback_layout(
    text: str,
    font_path: str | Path,
    target_width: int,
    target_height: int,
    font_size: int,
    orientation: str,
    angle_degrees: float,
    allow_overflow_ratio: float,
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
        allow_overflow_ratio,
        failure_reason="overflow",
        line_spacing=4,
        angle_degrees=angle_degrees,
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
    line_spacing: int = 4,
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
        line_spacing=line_spacing,
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
    compact = "".join(text.split())
    if not compact:
        return [""]
    if orientation == "vertical":
        stripped = "\n".join(part.strip() for part in text.splitlines() if part.strip())
        candidates = [stripped] if stripped else []
        if len(compact) >= 8:
            for candidate in generate_line_break_candidates(compact, max_lines=max_lines):
                if candidate not in candidates:
                    candidates.append(candidate)
        return candidates or [compact]
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
