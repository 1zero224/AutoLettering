from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateBox:
    xyxy: tuple[int, int, int, int]
    area: int
    dark_pixel_count: int
    center_distance: float
    score: float
    polarity: str = "dark_on_light"


@dataclass(frozen=True)
class DetectionResult:
    record_id: str
    status: str
    search_region_xyxy: tuple[int, int, int, int]
    candidate_boxes: list[CandidateBox]
    selected_text_box_xyxy: tuple[int, int, int, int] | None
    confidence: float
    failure_reason: str | None
