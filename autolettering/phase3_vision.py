from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models.mimo import MimoVisionClient, build_font_selection_prompt, parse_font_selection_response


class FontSelectionClient(Protocol):
    def choose_font(self, comparison_image_path: str | Path, prompt: str) -> dict:
        ...


def run_phase3_vision_selection(
    input_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 1,
    client: FontSelectionClient | None = None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase3-mimo-font-selection")
    run_dir.mkdir(parents=True, exist_ok=True)
    if client is None:
        raise ValueError("client is required unless experiment script builds one from environment")

    rows = _load_comparison_rows(Path(input_run_dir) / "font-comparisons.jsonl", sample_limit)
    selections, api_calls = _select_fonts(rows, client)
    _write_jsonl(run_dir / "font-selections.jsonl", selections)
    _write_jsonl(run_dir / "reports" / "api-calls.jsonl", api_calls)
    _write_report(run_dir / "reports" / "phase3-vision-report.md", input_run_dir, selections)
    return run_dir


def _load_comparison_rows(path: Path, sample_limit: int) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if payload.get("status") == "candidates_generated":
                rows.append(payload)
    return rows


def _select_fonts(rows: list[dict], client: FontSelectionClient) -> tuple[list[dict], list[dict]]:
    selections: list[dict] = []
    api_calls: list[dict] = []
    for row in rows:
        selection, api_call = _select_one(row, client)
        selections.append(selection)
        api_calls.append(api_call)
    return selections, api_calls


def _select_one(row: dict, client: FontSelectionClient) -> tuple[dict, dict]:
    prompt = build_font_selection_prompt(row.get("translated_text", ""), row["candidate_fonts"])
    try:
        response = client.choose_font(row["comparison_image_path"], prompt)
        result = parse_font_selection_response(
            response["raw_text"],
            [font["font_id"] for font in row["candidate_fonts"]],
        )
        if result.status == "selected":
            return _selection_row(row, result, response["raw_text"], "mimo_vision"), _api_call_row(row, response)
        return _fallback_selection(row, result.failure_reason, response["raw_text"]), _api_call_row(row, response)
    except Exception as exc:
        return _fallback_selection(row, f"api_error:{type(exc).__name__}", None), _api_failure_call(row, exc, prompt)


def _selection_row(row: dict, result, raw_text: str, source: str) -> dict:
    selected_font = _find_font(row["candidate_fonts"], result.selected_font_id)
    return {
        "record_id": row["record_id"],
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": result.status,
        "selected_font_id": result.selected_font_id,
        "selected_font": selected_font,
        "confidence": result.confidence,
        "model_reasoning_summary": result.reasoning_summary,
        "failure_reason": result.failure_reason,
        "selection_source": source,
        "comparison_image_path": row["comparison_image_path"],
        "source_crop_path": row.get("source_crop_path"),
        "raw_model_text": raw_text,
    }


def _fallback_selection(row: dict, reason: str | None, raw_text: str | None) -> dict:
    fallback_font = _first_candidate(row)
    return {
        "record_id": row["record_id"],
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": "selected" if fallback_font else "failed",
        "selected_font_id": fallback_font.get("font_id") if fallback_font else None,
        "selected_font": fallback_font,
        "confidence": 0.0 if fallback_font else None,
        "model_reasoning_summary": f"deterministic fallback after model failure: {reason}",
        "failure_reason": reason,
        "selection_source": "deterministic_fallback" if fallback_font else "none",
        "comparison_image_path": row.get("comparison_image_path"),
        "source_crop_path": row.get("source_crop_path"),
        "raw_model_text": raw_text,
    }


def _api_call_row(row: dict, response: dict) -> dict:
    return {
        "record_id": row["record_id"],
        "status": "ok",
        "request": response.get("request", {}),
        "response": response.get("response", {}),
    }


def _api_failure_selection(row: dict, exc: Exception) -> dict:
    return {
        "record_id": row["record_id"],
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": "failed",
        "selected_font_id": None,
        "selected_font": None,
        "confidence": None,
        "model_reasoning_summary": None,
        "failure_reason": f"api_error:{type(exc).__name__}",
        "selection_source": "none",
        "comparison_image_path": row.get("comparison_image_path"),
        "source_crop_path": row.get("source_crop_path"),
        "raw_model_text": None,
    }


def _api_failure_call(row: dict, exc: Exception, prompt: str) -> dict:
    return {
        "record_id": row["record_id"],
        "status": "failed",
        "request": {
            "image_path": row.get("comparison_image_path"),
            "prompt_chars": len(prompt),
        },
        "response": {
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:500],
        },
    }


def _find_font(candidate_fonts: list[dict], font_id: str | None) -> dict | None:
    if font_id is None:
        return None
    return next((font for font in candidate_fonts if font["font_id"] == font_id), None)


def _first_candidate(row: dict) -> dict | None:
    candidates = row.get("candidate_fonts") or []
    return candidates[0] if candidates else None


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, input_run_dir: str | Path, selections: list[dict]) -> None:
    selected = sum(1 for row in selections if row["status"] == "selected")
    failed = len(selections) - selected
    lines = [
        "# Phase 3 MIMO Font Selection Report",
        "",
        f"Input run directory: `{input_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records submitted: {len(selections)}",
        f"- Selected: {selected}",
        f"- Failed: {failed}",
        "",
        "## Generated Artifacts",
        "",
        "- `font-selections.jsonl`",
        "- `reports/api-calls.jsonl`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
