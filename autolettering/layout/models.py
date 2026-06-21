from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextMeasurement:
    width: int
    height: int


@dataclass(frozen=True)
class LayoutResult:
    status: str
    text: str
    line_breaks: str
    font_size: int
    orientation: str
    line_spacing: int
    letter_spacing: int
    angle_degrees: float
    target_width: int
    target_height: int
    measured_width: int
    measured_height: int
    overflow_ratio: float
    failure_reason: str | None = None
