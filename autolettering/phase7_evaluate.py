from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont


class PreviewEvaluationClient(Protocol):
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        ...


@dataclass(frozen=True)
class PreviewEvaluationResult:
    status: str
    score: int | None
    usable: bool | None
    original_text_removed: bool | None
    art_preserved: bool | None
    lettering_readable: bool | None
    issues: list[str]
    summary: str | None
    failure_reason: str | None


def run_phase7_preview_evaluation(
    preview_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 1,
    client: PreviewEvaluationClient | None = None,
) -> Path:
    if client is None:
        raise ValueError("client is required unless experiment script builds one from environment")
    run_dir = Path(output_root) / (run_id or "phase7-preview-evaluation")
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_preview_rows(Path(preview_run_dir) / "preview-results.jsonl", sample_limit)
    evaluations, api_calls = _evaluate_previews(rows, client)
    _write_jsonl(run_dir / "preview-evaluation.jsonl", evaluations)
    _write_jsonl(run_dir / "reports" / "api-calls.jsonl", api_calls)
    _write_report(run_dir / "reports" / "phase7-evaluation-report.md", preview_run_dir, evaluations)
    return run_dir


def build_preview_evaluation_prompt(row: dict) -> str:
    records = [
        {
            "record_id": record.get("record_id"),
            "text": record.get("translated_text", ""),
            "cleanup_method": record.get("cleanup_method"),
            "bbox": record.get("bbox"),
        }
        for record in row.get("records", [])
    ]
    return "\n".join(
        [
            "Evaluate this manga auto-lettering contact sheet.",
            "Each record is shown as two labeled panels: BEFORE original on the left and AFTER preview on the right.",
            "The BEFORE original panel intentionally contains Japanese text; the AFTER preview panel is the generated result.",
            "Only judge original_text_removed on the AFTER preview side; the BEFORE original side intentionally contains Japanese text.",
            "These are tight crops of the same original text area, sometimes enlarged for inspection; compare BEFORE and AFTER at the same scale.",
            "Do not penalize missing full speech-bubble outlines or full bubble background when the tight crop only contains the text area.",
            "Focus on whether the original Japanese text was removed, nearby art/tones are preserved, and translated lettering is readable.",
            "Compare the generated lettering against the original text area, not only readability.",
            "Mark it unusable or lower the score if translated lettering is oversized, outside the original text area, or covers nearby art.",
            f"Records JSON: {json.dumps(records, ensure_ascii=False)}",
            "Do not echo the Records JSON. Evaluate the image and fill the verdict fields.",
            "Every returned object must include score and usable.",
            "Return only JSON with keys: score (0-10), usable, original_text_removed, art_preserved, lettering_readable, issues, summary.",
        ]
    )


def parse_preview_evaluation_response(raw_text: str) -> PreviewEvaluationResult:
    try:
        payload = json.loads(_strip_json_wrapper(raw_text))
    except json.JSONDecodeError:
        return _failed("invalid_json")
    if isinstance(payload, list):
        return _result_from_record_payloads(payload)
    if not isinstance(payload, dict):
        return _failed("invalid_json")
    return _result_from_payload(payload)


def _result_from_payload(payload: dict) -> PreviewEvaluationResult:
    return PreviewEvaluationResult(
        status="evaluated",
        score=_optional_int(payload.get("score")),
        usable=_optional_bool(payload.get("usable")),
        original_text_removed=_optional_bool(payload.get("original_text_removed")),
        art_preserved=_optional_bool(payload.get("art_preserved")),
        lettering_readable=_optional_bool(payload.get("lettering_readable")),
        issues=_string_list(payload.get("issues")),
        summary=str(payload.get("summary", "")).strip() or None,
        failure_reason=None,
    )


def _result_from_record_payloads(payloads: list[object]) -> PreviewEvaluationResult:
    rows = [payload for payload in payloads if isinstance(payload, dict)]
    if not rows:
        return _failed("invalid_json")
    if not any(_has_evaluation_fields(row) for row in rows):
        return _failed("invalid_json")
    scores = [_optional_int(row.get("score")) for row in rows]
    return PreviewEvaluationResult(
        status="evaluated",
        score=min(score for score in scores if score is not None) if any(score is not None for score in scores) else None,
        usable=all(_optional_bool(row.get("usable")) is True for row in rows),
        original_text_removed=all(_optional_bool(row.get("original_text_removed")) is not False for row in rows),
        art_preserved=all(_optional_bool(row.get("art_preserved")) is True for row in rows),
        lettering_readable=all(_optional_bool(row.get("lettering_readable")) is True for row in rows),
        issues=_record_issues(rows),
        summary=_record_summary(rows),
        failure_reason=None,
    )


def _has_evaluation_fields(row: dict) -> bool:
    fields = {"score", "usable", "original_text_removed", "art_preserved", "lettering_readable", "issues", "summary"}
    return any(field in row for field in fields)


def _load_preview_rows(path: Path, sample_limit: int) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if payload.get("status") == "page_preview_generated":
                rows.append(payload)
    return rows


def _evaluate_previews(rows: list[dict], client: PreviewEvaluationClient) -> tuple[list[dict], list[dict]]:
    evaluations: list[dict] = []
    api_calls: list[dict] = []
    for row in rows:
        evaluation, api_call = _evaluate_one(row, client)
        evaluations.append(evaluation)
        api_calls.append(api_call)
    return evaluations, api_calls


def _evaluate_one(row: dict, client: PreviewEvaluationClient) -> tuple[dict, dict]:
    prompt = build_preview_evaluation_prompt(row)
    image_path = _build_evaluation_contact_sheet(row)
    try:
        response = client.analyze_image(
            image_path,
            prompt,
            kind="phase7_preview_evaluation",
            max_completion_tokens=1024,
        )
        result = parse_preview_evaluation_response(response["raw_text"])
        return _evaluation_row(row, result, response["raw_text"]), _api_call_row(row, response)
    except Exception as exc:
        return _failure_evaluation(row, exc), _failure_api_call(row, exc, prompt, image_path)


def _evaluation_row(row: dict, result: PreviewEvaluationResult, raw_text: str) -> dict:
    preview_path = row.get("preview", {}).get("page_preview_path")
    evaluation_image_path = row.get("preview", {}).get("evaluation_image_path")
    return {
        "image_name": row.get("image_name"),
        "status": result.status,
        "score": result.score,
        "usable": result.usable,
        "original_text_removed": result.original_text_removed,
        "art_preserved": result.art_preserved,
        "lettering_readable": result.lettering_readable,
        "issues": result.issues,
        "summary": result.summary,
        "failure_reason": result.failure_reason,
        "preview_path": preview_path,
        "evaluation_image_path": evaluation_image_path,
        "record_count": row.get("preview", {}).get("record_count"),
        "records": [
            {
                "record_id": record.get("record_id"),
                "cleanup_method": record.get("cleanup_method"),
                "translated_text": record.get("translated_text", ""),
            }
            for record in row.get("records", [])
        ],
        "raw_model_text": raw_text,
    }


def _api_call_row(row: dict, response: dict) -> dict:
    return {
        "image_name": row.get("image_name"),
        "status": "ok",
        "request": response.get("request", {}),
        "response": response.get("response", {}),
    }


def _failure_evaluation(row: dict, exc: Exception) -> dict:
    return {
        "image_name": row.get("image_name"),
        "status": "failed",
        "score": None,
        "usable": None,
        "original_text_removed": None,
        "art_preserved": None,
        "lettering_readable": None,
        "issues": [],
        "summary": None,
        "failure_reason": f"api_error:{type(exc).__name__}",
        "preview_path": row.get("preview", {}).get("page_preview_path"),
        "evaluation_image_path": row.get("preview", {}).get("evaluation_image_path"),
        "record_count": row.get("preview", {}).get("record_count"),
        "records": [],
        "raw_model_text": None,
    }


def _failure_api_call(row: dict, exc: Exception, prompt: str, image_path: str | None) -> dict:
    return {
        "image_name": row.get("image_name"),
        "status": "failed",
        "request": {"prompt_chars": len(prompt), "image_path": image_path},
        "response": {"error_type": type(exc).__name__, "error_message": str(exc)[:500]},
    }


def _build_evaluation_contact_sheet(row: dict) -> str:
    output = _contact_sheet_path(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    records = [record for record in row.get("records", []) if record.get("preview_before_after_path")]
    if not records:
        row.setdefault("preview", {})["evaluation_image_path"] = row.get("preview", {}).get("page_preview_path")
        return str(row["preview"]["evaluation_image_path"])

    font = ImageFont.load_default()
    label_height = 44
    padding = 12
    loaded = [(_record_label(record), Image.open(record["preview_before_after_path"]).convert("RGB")) for record in records]
    width = max(image.width for _, image in loaded) + padding * 2
    height = padding + sum(label_height + image.height + padding for _, image in loaded)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    y = padding
    for label, image in loaded:
        draw.text((padding, y), label[:120], fill="black", font=font)
        draw.text((padding, y + 18), "BEFORE original", fill=(40, 40, 40), font=font)
        draw.text((padding + image.width // 2 + 4, y + 18), "AFTER preview", fill=(40, 40, 40), font=font)
        y += label_height
        draw.rectangle((padding - 1, y - 1, padding + image.width, y + image.height), outline=(180, 180, 180), width=1)
        sheet.paste(image, (padding, y))
        split_x = padding + image.width // 2
        draw.line((split_x, y, split_x, y + image.height - 1), fill=(255, 0, 0), width=1)
        y += image.height + padding
    sheet.save(output)
    row.setdefault("preview", {})["evaluation_image_path"] = str(output)
    return str(output)


def _contact_sheet_path(row: dict) -> Path:
    preview_path = Path(row.get("preview", {}).get("page_preview_path", "preview.png"))
    run_dir = preview_path.parent.parent if preview_path.parent.name == "pages" else preview_path.parent
    return run_dir / "debug" / "evaluation_contact_sheets" / f"{_safe_name(str(row.get('image_name') or preview_path.stem))}.png"


def _record_label(record: dict) -> str:
    return " | ".join(
        [
            str(record.get("record_id", "")),
            str(record.get("cleanup_method", "")),
        ]
    )


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, preview_run_dir: str | Path, evaluations: list[dict]) -> None:
    evaluated = [row for row in evaluations if row["status"] == "evaluated"]
    usable = sum(1 for row in evaluated if row.get("usable") is True)
    failed = sum(1 for row in evaluations if row["status"] == "failed")
    average = _average_score(evaluated)
    lines = [
        "# Phase 7 Preview Evaluation Report",
        "",
        f"Preview run directory: `{preview_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Pages submitted: {len(evaluations)}",
        f"- Evaluated: {len(evaluated)}",
        f"- Usable: {usable}",
        f"- Failed: {failed}",
        f"- Average score: {average}",
        "",
        "## Generated Artifacts",
        "",
        "- `preview-evaluation.jsonl`",
        "- `reports/api-calls.jsonl`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _average_score(evaluated: list[dict]) -> str:
    scores = [row["score"] for row in evaluated if row.get("score") is not None]
    if not scores:
        return "n/a"
    return f"{sum(scores) / len(scores):.1f}"


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


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _record_issues(rows: list[dict]) -> list[str]:
    issues: list[str] = []
    for row in rows:
        prefix = str(row.get("record_id", "")).strip()
        for issue in _string_list(row.get("issues")):
            issues.append(f"{prefix}: {issue}" if prefix else issue)
    return issues


def _record_summary(rows: list[dict]) -> str | None:
    summaries = []
    for row in rows:
        summary = str(row.get("summary", "")).strip()
        if not summary:
            continue
        record_id = str(row.get("record_id", "")).strip()
        summaries.append(f"{record_id}: {summary}" if record_id else summary)
    return "; ".join(summaries) or None


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


def _failed(reason: str) -> PreviewEvaluationResult:
    return PreviewEvaluationResult(
        status="failed",
        score=None,
        usable=None,
        original_text_removed=None,
        art_preserved=None,
        lettering_readable=None,
        issues=[],
        summary=None,
        failure_reason=reason,
    )
