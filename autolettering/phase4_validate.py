from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .layout.validation import build_layout_validation_prompt, parse_layout_validation_response


class LayoutValidationClient(Protocol):
    def analyze_image(self, image_path: str | Path, prompt: str, kind: str = "image_analysis") -> dict:
        ...


def run_phase4_layout_validation(
    layout_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 1,
    client: LayoutValidationClient | None = None,
) -> Path:
    if client is None:
        raise ValueError("client is required unless experiment script builds one from environment")
    run_dir = Path(output_root) / (run_id or "phase4-layout-validation")
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_layout_rows(Path(layout_run_dir) / "layout-results.jsonl", sample_limit)
    validations, api_calls = _validate_layouts(rows, client)
    _write_jsonl(run_dir / "layout-validation.jsonl", validations)
    _write_jsonl(run_dir / "reports" / "api-calls.jsonl", api_calls)
    _write_report(run_dir / "reports" / "phase4-validation-report.md", layout_run_dir, validations)
    return run_dir


def _load_layout_rows(path: Path, sample_limit: int) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if payload.get("status") == "layout_generated":
                rows.append(payload)
    return rows


def _validate_layouts(rows: list[dict], client: LayoutValidationClient) -> tuple[list[dict], list[dict]]:
    validations: list[dict] = []
    api_calls: list[dict] = []
    for row in rows:
        validation, api_call = _validate_one(row, client)
        validations.append(validation)
        api_calls.append(api_call)
    return validations, api_calls


def _validate_one(row: dict, client: LayoutValidationClient) -> tuple[dict, dict]:
    layout = row["layout"]
    prompt = build_layout_validation_prompt(row.get("translated_text", ""), layout)
    try:
        response = client.analyze_image(
            layout["preview_path"],
            prompt,
            kind="layout_validation",
            max_completion_tokens=96,
        )
        result = parse_layout_validation_response(response["raw_text"])
        return _validation_row(row, result, response["raw_text"]), _api_call_row(row, response)
    except Exception as exc:
        return _failure_validation(row, exc), _failure_api_call(row, exc, prompt)


def _validation_row(row: dict, result, raw_text: str) -> dict:
    layout = row["layout"]
    return {
        "record_id": row["record_id"],
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": result.status,
        "accepted": result.accepted,
        "needs_revision": result.needs_revision,
        "overflow_ok": result.overflow_ok,
        "naturalness_score": result.naturalness_score,
        "recommended_changes": result.recommended_changes,
        "reasoning_summary": result.reasoning_summary,
        "failure_reason": result.failure_reason,
        "layout_preview_path": layout["preview_path"],
        "raw_model_text": raw_text,
    }


def _api_call_row(row: dict, response: dict) -> dict:
    return {
        "record_id": row["record_id"],
        "status": "ok",
        "request": response.get("request", {}),
        "response": response.get("response", {}),
    }


def _failure_validation(row: dict, exc: Exception) -> dict:
    layout = row.get("layout", {})
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": "failed",
        "accepted": None,
        "needs_revision": None,
        "overflow_ok": None,
        "naturalness_score": None,
        "recommended_changes": [],
        "reasoning_summary": None,
        "failure_reason": f"api_error:{type(exc).__name__}",
        "layout_preview_path": layout.get("preview_path"),
        "raw_model_text": None,
    }


def _failure_api_call(row: dict, exc: Exception, prompt: str) -> dict:
    return {
        "record_id": row.get("record_id"),
        "status": "failed",
        "request": {"prompt_chars": len(prompt), "image_path": row.get("layout", {}).get("preview_path")},
        "response": {"error_type": type(exc).__name__, "error_message": str(exc)[:500]},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, layout_run_dir: str | Path, validations: list[dict]) -> None:
    accepted = sum(1 for row in validations if row["status"] == "accepted")
    failed = sum(1 for row in validations if row["status"] == "failed")
    needs_revision = len(validations) - accepted - failed
    lines = [
        "# Phase 4 Layout Validation Report",
        "",
        f"Layout run directory: `{layout_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records submitted: {len(validations)}",
        f"- Accepted: {accepted}",
        f"- Needs revision: {needs_revision}",
        f"- Failed: {failed}",
        "",
        "## Generated Artifacts",
        "",
        "- `layout-validation.jsonl`",
        "- `reports/api-calls.jsonl`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
