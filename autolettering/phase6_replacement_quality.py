from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .phase6_replacement_quality_io import build_replacement_quality_prompt, parse_replacement_quality_response
from .phase6_replacement_sheet import resolve_existing_path, write_replacement_quality_sheet
from .phase6_replacement_quality_types import ReplacementQualityResult


GPT_REPLACEMENT_METHOD = "gpt_image2_masked_edit"


class ReplacementQualityClient(Protocol):
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        ...


def run_phase6_replacement_quality(
    cleanup_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    client: ReplacementQualityClient | None = None,
    path_roots: list[str | Path] | None = None,
) -> Path:
    if client is None:
        raise ValueError("client is required unless experiment script builds one from environment")
    cleanup_run_path = Path(cleanup_run_dir)
    roots = [Path(root) for root in path_roots or []]
    run_dir = Path(output_root) / (run_id or "phase6-replacement-quality")
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_replacement_rows(cleanup_run_path / "cleanup-results.jsonl", cleanup_run_path, roots, sample_limit, record_ids)
    evaluations, api_calls = _evaluate_replacement_rows(run_dir, cleanup_run_path, roots, rows, client)
    _write_jsonl(run_dir / "replacement-quality.jsonl", evaluations)
    _write_jsonl(run_dir / "reports" / "api-calls.jsonl", api_calls)
    _write_report(run_dir / "reports" / "phase6-replacement-quality-report.md", cleanup_run_dir, evaluations)
    return run_dir


def _load_replacement_rows(
    path: Path,
    base_dir: Path,
    path_roots: list[Path],
    sample_limit: int,
    record_ids: list[str] | None,
) -> list[dict]:
    wanted = set(record_ids or [])
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if wanted and payload.get("record_id") not in wanted:
                continue
            if _is_evaluable_replacement_row(payload, base_dir, path_roots):
                rows.append(payload)
                if len(rows) >= sample_limit:
                    break
    return rows


def _is_evaluable_replacement_row(row: dict, base_dir: Path, path_roots: list[Path]) -> bool:
    if row.get("status") != "cleaned":
        return False
    cleanup = row.get("cleanup") or {}
    if cleanup.get("replacement_method") != GPT_REPLACEMENT_METHOD:
        return False
    if (row.get("gpt_image2_edit") or {}).get("status") != "ok":
        return False
    replacement = cleanup.get("replacement_crop_path")
    return bool(replacement and resolve_existing_path(replacement, base_dir, path_roots))


def _evaluate_replacement_rows(
    run_dir: Path,
    cleanup_run_dir: Path,
    path_roots: list[Path],
    rows: list[dict],
    client: ReplacementQualityClient,
) -> tuple[list[dict], list[dict]]:
    evaluations: list[dict] = []
    api_calls: list[dict] = []
    for row in rows:
        evaluation, api_call = _evaluate_one(run_dir, cleanup_run_dir, path_roots, row, client)
        evaluations.append(evaluation)
        api_calls.append(api_call)
    return evaluations, api_calls


def _evaluate_one(
    run_dir: Path,
    cleanup_run_dir: Path,
    path_roots: list[Path],
    row: dict,
    client: ReplacementQualityClient,
) -> tuple[dict, dict]:
    prompt = build_replacement_quality_prompt(row)
    image_path = _write_replacement_quality_sheet(run_dir, cleanup_run_dir, path_roots, row)
    try:
        response = client.analyze_image(
            image_path,
            prompt,
            kind="phase6_replacement_quality",
            max_completion_tokens=1200,
        )
        result = parse_replacement_quality_response(response["raw_text"])
        return _evaluation_row(row, result, response["raw_text"], image_path), _api_call_row(row, response)
    except Exception as exc:
        return _failure_evaluation(row, exc, image_path), _failure_api_call(row, exc, prompt, image_path)


def _evaluation_row(row: dict, result: ReplacementQualityResult, raw_text: str, image_path: str) -> dict:
    cleanup = row.get("cleanup") or {}
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "status": result.status,
        "score": result.score,
        "usable": result.usable,
        "exact_text_correct": result.exact_text_correct,
        "simplified_chinese_correct": result.simplified_chinese_correct,
        "no_japanese_remaining": result.no_japanese_remaining,
        "region_correct": result.region_correct,
        "style_consistent": result.style_consistent,
        "outside_mask_preserved": result.outside_mask_preserved,
        "issues": result.issues,
        "summary": result.summary,
        "failure_reason": result.failure_reason,
        "replacement_method": cleanup.get("replacement_method"),
        "replacement_crop_path": cleanup.get("replacement_crop_path"),
        **_source_fields(row),
        "evaluation_image_path": image_path,
        "raw_model_text": raw_text,
    }


def _api_call_row(row: dict, response: dict) -> dict:
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "status": "ok",
        "request": response.get("request", {}),
        "response": response.get("response", {}),
    }


def _failure_evaluation(row: dict, exc: Exception, image_path: str) -> dict:
    cleanup = row.get("cleanup") or {}
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "status": "failed",
        "score": None,
        "usable": None,
        "exact_text_correct": None,
        "simplified_chinese_correct": None,
        "no_japanese_remaining": None,
        "region_correct": None,
        "style_consistent": None,
        "outside_mask_preserved": None,
        "issues": [],
        "summary": None,
        "failure_reason": f"api_error:{type(exc).__name__}",
        "replacement_method": cleanup.get("replacement_method"),
        "replacement_crop_path": cleanup.get("replacement_crop_path"),
        **_source_fields(row),
        "evaluation_image_path": image_path,
        "raw_model_text": None,
    }


def _failure_api_call(row: dict, exc: Exception, prompt: str, image_path: str) -> dict:
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "status": "failed",
        "request": {"prompt_chars": len(prompt), "image_path": image_path},
        "response": {"error_type": type(exc).__name__, "error_message": str(exc)[:500]},
    }


def _source_fields(row: dict) -> dict:
    cleanup = row.get("cleanup") or {}
    gpt = row.get("gpt_image2_edit") or {}
    request = gpt.get("request") or {}
    edit_context = gpt.get("edit_context") or {}
    return {
        "source_request_image_path": edit_context.get("input_path") or request.get("image_path"),
        "source_request_mask_path": edit_context.get("mask_path") or request.get("mask_path"),
        "source_replacement_crop_path": cleanup.get("replacement_crop_path"),
        "source_cleaned_crop_path": cleanup.get("cleaned_crop_path"),
        "source_local_context_bbox": edit_context.get("local_context_bbox"),
        "source_mask_bbox": cleanup.get("mask_bbox"),
        "source_target_size": request.get("target_size"),
    }


def _write_replacement_quality_sheet(run_dir: Path, cleanup_run_dir: Path, path_roots: list[Path], row: dict) -> str:
    return write_replacement_quality_sheet(run_dir, cleanup_run_dir, row, path_roots)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, cleanup_run_dir: str | Path, evaluations: list[dict]) -> None:
    evaluated = [row for row in evaluations if row["status"] == "evaluated"]
    usable = sum(1 for row in evaluated if row.get("usable") is True)
    failed = sum(1 for row in evaluations if row["status"] != "evaluated")
    exact_text_failed = sum(1 for row in evaluated if row.get("exact_text_correct") is False)
    style_failed = sum(1 for row in evaluated if row.get("style_consistent") is False)
    lines = [
        "# Phase 6 Replacement Quality Report",
        "",
        f"Cleanup run directory: `{cleanup_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records submitted: {len(evaluations)}",
        f"- Evaluated: {len(evaluated)}",
        f"- Usable replacements: {usable}",
        f"- Exact text failures: {exact_text_failed}",
        f"- Style consistency failures: {style_failed}",
        f"- Failed evaluations: {failed}",
        "",
        "## Generated Artifacts",
        "",
        "- `replacement-quality.jsonl`",
        "- `reports/api-calls.jsonl`",
        "- `debug/replacement_quality_sheets/*.png`",
        "- `debug/replacement_mask_overlays/*.png`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

