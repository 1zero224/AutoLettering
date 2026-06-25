from __future__ import annotations

import json

from .phase6_replacement_quality_types import ReplacementQualityResult


def build_replacement_quality_prompt(row: dict) -> str:
    cleanup = row.get("cleanup") or {}
    locator = row.get("fallback_locator") or {}
    validation = row.get("fallback_locator_validation") or {}
    payload = {
        "record_id": row.get("record_id"),
        "translated_text": row.get("translated_text", ""),
        "visible_original_text_in_target": validation.get("visible_original_text"),
        "locator_confidence": locator.get("confidence"),
        "replacement_method": cleanup.get("replacement_method") or cleanup.get("method"),
        "text_bbox": cleanup.get("text_bbox"),
        "mask_bbox": cleanup.get("mask_bbox"),
        "bbox": cleanup.get("bbox"),
    }
    return "\n".join(
        [
            "Evaluate this manga Phase 6 gpt-image-2 masked text replacement review sheet.",
            "The sheet contains labeled reference tiles: original context, locator/validation overlay if available, GPT edit input, mask overlay, GPT output, and final replacement crop.",
            "Judge the final replacement crop as the primary result, using the other tiles to understand the intended edit region.",
            "Do not select a different text region from the manga page. Evaluate only the target region indicated by the locator/validation overlay and the red mask overlay.",
            "If another nearby bubble or caption contains more natural matching text, ignore it unless it is inside the indicated target mask.",
            "If the replacement appears in a different bubble, card, caption, or unmasked area, set region_correct=false even if the Chinese text is readable.",
            "The final result must contain the exact Simplified Chinese text requested for this record.",
            "First transcribe the visible text in the final replacement crop into observed_text before scoring.",
            "If observed_text omits digits, omits Chinese characters, has extra visible text, or differs from translated_text in any way, set exact_text_correct=false.",
            "Judge simplified_chinese_correct separately from exact_text_correct.",
            "Be strict about glyph variants: 暂 is correct when requested, but 暫 is incorrect.",
            "Reject if Japanese text remains in the target region, if the text is in the wrong region, or if the replacement targets unrelated text.",
            "Reject if the style, color, angle, scale, spacing, or text alignment is inconsistent with the original local manga lettering.",
            "Reject if gpt-image-2 damaged art, tones, panel texture, logos, or other content outside the mask.",
            "Do not over-credit readable Chinese text when it uses the wrong glyph, wrong style, or wrong placement.",
            f"Record JSON: {json.dumps(payload, ensure_ascii=False)}",
            "Return only JSON with keys: observed_text, score (0-10), usable, exact_text_correct, simplified_chinese_correct, no_japanese_remaining, region_correct, style_consistent, outside_mask_preserved, issues, summary.",
        ]
    )


def parse_replacement_quality_response(raw_text: str) -> ReplacementQualityResult:
    try:
        payload = json.loads(_strip_json_wrapper(raw_text))
    except json.JSONDecodeError:
        return _failed("invalid_json")
    if not isinstance(payload, dict):
        return _failed("invalid_json")
    issues = _string_list(payload.get("issues"))
    summary = str(payload.get("summary", "")).strip() or None
    region_correct = _normalized_region_correct(payload.get("region_correct"), issues, summary)
    return ReplacementQualityResult(
        status="evaluated",
        score=_optional_int(payload.get("score")),
        usable=_optional_bool(payload.get("usable")),
        exact_text_correct=_optional_bool(payload.get("exact_text_correct")),
        simplified_chinese_correct=_optional_bool(payload.get("simplified_chinese_correct")),
        no_japanese_remaining=_optional_bool(payload.get("no_japanese_remaining")),
        region_correct=region_correct,
        style_consistent=_optional_bool(payload.get("style_consistent")),
        outside_mask_preserved=_optional_bool(payload.get("outside_mask_preserved")),
        issues=_normalized_issues(issues, payload.get("region_correct"), region_correct),
        summary=summary,
        observed_text=_optional_text(payload.get("observed_text")),
        failure_reason=None,
    )


def _strip_json_wrapper(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _optional_int(value: object) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(10, score))


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _normalized_region_correct(value: object, issues: list[str], summary: str | None) -> bool | None:
    parsed = _optional_bool(value)
    if parsed is True and _mentions_wrong_region(" ".join([*issues, summary or ""])):
        return False
    return parsed


def _normalized_issues(issues: list[str], raw_region_correct: object, normalized_region_correct: bool | None) -> list[str]:
    if _optional_bool(raw_region_correct) is True and normalized_region_correct is False:
        return [*issues, "region_correct_overridden_from_issue_text"]
    return issues


def _mentions_wrong_region(text: str) -> bool:
    normalized = text.lower()
    if any(phrase in normalized for phrase in ("not wrong region", "no wrong region", "without wrong region")):
        return False
    return any(
        phrase in normalized
        for phrase in (
            "wrong region",
            "wrong speech bubble",
            "different bubble",
            "adjacent speech bubble",
            "wrong target",
            "incorrectly placed",
            "placed in the wrong",
        )
    )


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _failed(reason: str) -> ReplacementQualityResult:
    return ReplacementQualityResult(
        status="failed",
        score=None,
        usable=None,
        exact_text_correct=None,
        simplified_chinese_correct=None,
        no_japanese_remaining=None,
        region_correct=None,
        style_consistent=None,
        outside_mask_preserved=None,
        issues=[],
        summary=None,
        observed_text=None,
        failure_reason=reason,
    )
