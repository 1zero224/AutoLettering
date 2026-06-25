from __future__ import annotations

from pathlib import Path

from .assets.fonts import font_record_to_dict, scan_font_directory


def context_candidates(comparison: dict, font_dir: str | Path | None, candidate_limit: int) -> list[dict]:
    base = list(comparison.get("candidate_fonts") or [])
    translated_text = str(comparison.get("translated_text") or "")
    if font_dir is not None:
        scanned = [font_record_to_dict(font) for font in scan_font_directory(font_dir, sample_text=translated_text)]
        base = _merge_candidates(base, scanned)
    supported = [candidate for candidate in base if candidate.get("supports_sample_text", True)]
    source = supported or base
    return sorted(source, key=_context_candidate_sort_key)[: max(1, candidate_limit)]


def _merge_candidates(first: list[dict], second: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for candidate in [*first, *second]:
        font_id = str(candidate.get("font_id") or "")
        if not font_id or font_id in seen:
            continue
        merged.append(candidate)
        seen.add(font_id)
    return merged


def _context_candidate_sort_key(candidate: dict) -> tuple[int, str]:
    text = " ".join(
        [
            str(candidate.get("filename", "")),
            str(candidate.get("family_name", "")),
            " ".join(str(item) for item in candidate.get("style_hints") or []),
        ]
    ).casefold()
    priority = 100
    for index, keyword in enumerate(
        [
            "pop",
            "与墨",
            "丸",
            "圆",
            "有圆",
            "黑",
            "文黑",
            "灵动",
            "综艺",
            "海报",
            "方圆",
            "角黑",
            "拙黑",
            "漫",
            "龙珠",
        ]
    ):
        if keyword.casefold() in text:
            priority = min(priority, index)
    return priority, str(candidate.get("filename", ""))
