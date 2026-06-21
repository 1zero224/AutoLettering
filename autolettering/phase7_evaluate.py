from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol


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
            "Evaluate this manga auto-lettering page preview.",
            "Focus on whether the original Japanese text was removed, nearby art/tones are preserved, and translated lettering is readable.",
            f"Records JSON: {json.dumps(records, ensure_ascii=False)}",
            "Return only JSON with keys: score (0-10), usable, original_text_removed, art_preserved, lettering_readable, issues, summary.",
        ]
    )


def parse_preview_evaluation_response(raw_text: str) -> PreviewEvaluationResult:
    try:
        payload = json.loads(_strip_json_wrapper(raw_text))
    except json.JSONDecodeError:
        return _failed("invalid_json")
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
    image_path = row.get("preview", {}).get("page_preview_path")
    try:
        response = client.analyze_image(
            image_path,
            prompt,
            kind="phase7_preview_evaluation",
            max_completion_tokens=192,
        )
        result = parse_preview_evaluation_response(response["raw_text"])
        return _evaluation_row(row, result, response["raw_text"]), _api_call_row(row, response)
    except Exception as exc:
        return _failure_evaluation(row, exc), _failure_api_call(row, exc, prompt, image_path)


def _evaluation_row(row: dict, result: PreviewEvaluationResult, raw_text: str) -> dict:
    preview_path = row.get("preview", {}).get("page_preview_path")
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
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
