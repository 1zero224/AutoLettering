from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class LayoutValidationResult:
    status: str
    accepted: bool | None
    needs_revision: bool | None
    overflow_ok: bool | None
    naturalness_score: float | None
    recommended_changes: list[str]
    reasoning_summary: str | None
    failure_reason: str | None


def build_layout_validation_prompt(translated_text: str, layout: dict) -> str:
    facts = _compact_facts(translated_text, layout)
    return (
        "Judge manga text layout. "
        f"Facts JSON: {json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}. "
        "Return JSON only: accepted,needs_revision,overflow_ok,naturalness_score,reasoning_summary."
    )


def parse_layout_validation_response(raw_text: str) -> LayoutValidationResult:
    try:
        payload = json.loads(_strip_json_wrapper(raw_text))
    except json.JSONDecodeError:
        return _failed("invalid_json")

    accepted = _optional_bool(payload.get("accepted"))
    needs_revision = _optional_bool(payload.get("needs_revision"))
    overflow_ok = _optional_bool(payload.get("overflow_ok"))
    status = "accepted" if accepted is True and needs_revision is not True else "needs_revision"
    return LayoutValidationResult(
        status=status,
        accepted=accepted,
        needs_revision=needs_revision,
        overflow_ok=overflow_ok,
        naturalness_score=_optional_float(payload.get("naturalness_score")),
        recommended_changes=_string_list(payload.get("recommended_changes")),
        reasoning_summary=str(payload.get("reasoning_summary", "")).strip() or None,
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


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _failed(reason: str) -> LayoutValidationResult:
    return LayoutValidationResult(
        status="failed",
        accepted=None,
        needs_revision=None,
        overflow_ok=None,
        naturalness_score=None,
        recommended_changes=[],
        reasoning_summary=None,
        failure_reason=reason,
    )


def _compact_facts(translated_text: str, layout: dict) -> dict:
    return {
        "text": translated_text,
        "orientation": layout.get("orientation"),
        "font_size": layout.get("font_size"),
        "overflow": layout.get("overflow_ratio"),
        "target": [layout.get("target_width"), layout.get("target_height")],
        "measured": [layout.get("measured_width"), layout.get("measured_height")],
    }
