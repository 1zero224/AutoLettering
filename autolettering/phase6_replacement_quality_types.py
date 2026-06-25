from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplacementQualityResult:
    status: str
    score: int | None
    usable: bool | None
    exact_text_correct: bool | None
    simplified_chinese_correct: bool | None
    no_japanese_remaining: bool | None
    region_correct: bool | None
    style_consistent: bool | None
    outside_mask_preserved: bool | None
    issues: list[str]
    summary: str | None
    failure_reason: str | None
