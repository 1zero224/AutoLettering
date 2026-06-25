from __future__ import annotations

import json
from pathlib import Path

from .record_selection import normalize_record_ids, row_matches_record_ids


CONTEXT_FONT_SCHEMA_VERSION = "autolettering.phase3.context_font_selection.v1"


def result_row(
    comparison: dict,
    result: dict,
    rendered: list[dict],
    grid_path: Path,
    raw_model_text: str | None,
) -> dict:
    selected = find_font(rendered, result.get("selected_font_id"))
    return {
        "schema_version": CONTEXT_FONT_SCHEMA_VERSION,
        "record_id": comparison.get("record_id"),
        "image_name": comparison.get("image_name"),
        "translated_text": comparison.get("translated_text", ""),
        "status": result["status"],
        "selected_font_id": result.get("selected_font_id"),
        "selected_font": selected,
        "confidence": result.get("confidence"),
        "model_reasoning_summary": result.get("reasoning_summary"),
        "failure_reason": result.get("failure_reason"),
        "selection_source": result.get("selection_source") or "none",
        "comparison_image_path": str(grid_path),
        "source_crop_path": comparison.get("source_crop_path"),
        "candidate_fonts": rendered,
        "raw_model_text": raw_model_text,
    }


def selection_output_row(row: dict) -> dict:
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": row.get("status"),
        "selected_font_id": row.get("selected_font_id"),
        "selected_font": row.get("selected_font"),
        "confidence": row.get("confidence"),
        "model_reasoning_summary": row.get("model_reasoning_summary"),
        "failure_reason": row.get("failure_reason"),
        "selection_source": row.get("selection_source"),
        "comparison_image_path": row.get("comparison_image_path"),
        "source_crop_path": row.get("source_crop_path"),
        "raw_model_text": row.get("raw_model_text"),
    }


def selection_payload(
    status: str,
    selected_font_id: str | None,
    confidence: float | None,
    reasoning_summary: str | None,
    failure_reason: str | None,
    selection_source: str,
) -> dict:
    return {
        "status": status,
        "selected_font_id": selected_font_id,
        "confidence": confidence,
        "reasoning_summary": reasoning_summary,
        "failure_reason": failure_reason,
        "selection_source": selection_source,
    }


def failed_row(comparison: dict, reason: str) -> dict:
    return {
        "schema_version": CONTEXT_FONT_SCHEMA_VERSION,
        "record_id": comparison.get("record_id"),
        "image_name": comparison.get("image_name"),
        "translated_text": comparison.get("translated_text", ""),
        "status": "failed",
        "selected_font_id": None,
        "selected_font": None,
        "confidence": None,
        "model_reasoning_summary": None,
        "failure_reason": reason,
        "selection_source": "none",
        "comparison_image_path": None,
        "source_crop_path": comparison.get("source_crop_path"),
        "candidate_fonts": [],
        "raw_model_text": None,
    }


def api_call_row(comparison: dict, response: dict) -> dict:
    return {
        "record_id": comparison.get("record_id"),
        "status": "ok",
        "request": response.get("request", {}),
        "response": response.get("response", {}),
    }


def skipped_api_call(
    comparison: dict,
    reason: str,
    prompt: str | None = None,
    image_path: str | Path | None = None,
) -> dict:
    return {
        "record_id": comparison.get("record_id"),
        "status": "skipped",
        "request": {"prompt_chars": len(prompt or ""), "image_path": str(image_path) if image_path else None},
        "response": {"reason": reason},
    }


def failed_api_call(comparison: dict, exc: Exception, prompt: str, image_path: str | Path) -> dict:
    return {
        "record_id": comparison.get("record_id"),
        "status": "failed",
        "request": {"prompt_chars": len(prompt), "image_path": str(image_path)},
        "response": {"error_type": type(exc).__name__, "error_message": str(exc)[:500]},
    }


def load_rows(path: Path, sample_limit: int, record_ids: list[str] | None, status: str) -> list[dict]:
    wanted = normalize_record_ids(record_ids)
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            row = json.loads(line)
            if row_matches_record_ids(row, wanted) and row.get("status") == status:
                rows.append(row)
    return rows


def rows_by_record(path: Path, status: str | None = None) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if status is not None and row.get("status") != status:
                continue
            record_id = row.get("record_id")
            if record_id:
                rows[str(record_id)] = row
    return rows


def find_font(fonts: list[dict], font_id: str | None) -> dict | None:
    if font_id is None:
        return None
    return next((font for font in fonts if font.get("font_id") == font_id), None)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_manifest(output_path: Path, font_run: Path, layout_run: Path, cleanup_run: Path, rows: list[dict]) -> None:
    payload = {
        "schema_version": CONTEXT_FONT_SCHEMA_VERSION,
        "font_comparison_run_dir": str(font_run),
        "layout_run_dir": str(layout_run),
        "cleanup_run_dir": str(cleanup_run),
        "record_count": len(rows),
        "selected_count": sum(1 for row in rows if row.get("status") == "selected"),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_report(output_path: Path, font_run: Path, layout_run: Path, cleanup_run: Path, rows: list[dict]) -> None:
    lines = [
        "# Phase 3 Context Font Selection",
        "",
        f"Font comparison run: `{font_run}`",
        f"Layout run: `{layout_run}`",
        f"Cleanup run: `{cleanup_run}`",
        "",
        "## Summary",
        "",
        f"- Records: {len(rows)}",
        f"- Selected: {sum(1 for row in rows if row.get('status') == 'selected')}",
        "",
        "## Artifacts",
        "",
        "- `context-font-results.jsonl`",
        "- `font-selections.jsonl`",
        "- `debug/context_font_grids/*.png`",
        "- `context_crops/*/*.png`",
        "- `reports/api-calls.jsonl`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
