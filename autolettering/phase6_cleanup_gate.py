from __future__ import annotations

import json
from pathlib import Path


DEFAULT_MIN_USABLE_SCORE = 7


def run_phase6_cleanup_gate(
    cleanup_run_dir: str | Path,
    cleanup_quality_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 20,
    record_ids: list[str] | None = None,
    min_usable_score: int = DEFAULT_MIN_USABLE_SCORE,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-cleanup-gate")
    run_dir.mkdir(parents=True, exist_ok=True)
    cleanup_rows = _rows_by_record(Path(cleanup_run_dir) / "cleanup-results.jsonl")
    quality_rows = _selected_quality_rows(
        Path(cleanup_quality_run_dir) / "cleanup-quality.jsonl",
        sample_limit=sample_limit,
        record_ids=record_ids,
    )
    candidates = [
        candidate
        for row in quality_rows
        if (candidate := _escalation_candidate(row, cleanup_rows.get(str(row.get("record_id"))), min_usable_score))
        is not None
    ]
    manifest = _manifest(cleanup_run_dir, cleanup_quality_run_dir, quality_rows, candidates, min_usable_score)
    _write_jsonl(run_dir / "cleanup-escalation-candidates.jsonl", candidates)
    _write_json(run_dir / "manifest.json", manifest)
    _write_report(run_dir / "reports" / "phase6-cleanup-gate-report.md", manifest, candidates)
    return run_dir


def _selected_quality_rows(path: Path, sample_limit: int, record_ids: list[str] | None) -> list[dict]:
    wanted = set(record_ids or [])
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            row = json.loads(line)
            record_id = str(row.get("record_id") or "")
            if wanted and record_id not in wanted:
                continue
            rows.append(row)
    return rows


def _rows_by_record(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            record_id = row.get("record_id")
            if record_id:
                rows[str(record_id)] = row
    return rows


def _escalation_candidate(quality_row: dict, cleanup_row: dict | None, min_usable_score: int) -> dict | None:
    if cleanup_row is None:
        return None
    cleanup = cleanup_row.get("cleanup") or {}
    if not _is_cta_lama_cleanup(cleanup):
        return None
    reason_codes = _quality_reason_codes(quality_row, min_usable_score)
    if not reason_codes:
        return None
    return {
        "record_id": quality_row.get("record_id") or cleanup_row.get("record_id"),
        "image_name": quality_row.get("image_name") or cleanup_row.get("image_name"),
        "status": "candidate",
        "recommended_route": "quality_gate_gpt_image2_masked_edit",
        "recommended_action": "run_gpt_image2_transparent_masked_replacement",
        "reason_codes": reason_codes,
        "quality": {
            "status": quality_row.get("status"),
            "score": quality_row.get("score"),
            "usable": quality_row.get("usable"),
            "original_text_removed": quality_row.get("original_text_removed"),
            "art_preserved": quality_row.get("art_preserved"),
            "issues": quality_row.get("issues") or [],
            "summary": quality_row.get("summary"),
            "evaluation_image_path": quality_row.get("evaluation_image_path"),
        },
        "cleanup": {
            "method": cleanup.get("method"),
            "route": cleanup.get("route"),
            "text_region_source": cleanup.get("text_region_source"),
            "bbox": cleanup.get("bbox"),
            "source_mask_path": cleanup.get("source_mask_path") or cleanup.get("text_mask_path"),
            "before_after_path": cleanup.get("before_after_path"),
            "cleaned_crop_path": cleanup.get("cleaned_crop_path"),
        },
        "gpt_image2_contract": {
            "mask_source": "source_mask_path",
            "mask_mode": "transparent_target_region_preserve_opaque_background",
            "target_text": cleanup_row.get("translated_text", ""),
            "input_image_policy": "use_tight_context_around_original_text_region",
            "must_save_request_summary": True,
            "requires_mimo_replacement_quality_check": True,
        },
    }


def _is_cta_lama_cleanup(cleanup: dict) -> bool:
    method = str(cleanup.get("method") or cleanup.get("actual_inpaint_method") or "")
    route = str(cleanup.get("route") or "")
    text_region_source = str(cleanup.get("text_region_source") or "")
    return (
        "lama" in method
        and (
            route == "cta_mask_lama_large_512px"
            or text_region_source == "ctd_refined_mask_component"
        )
    )


def _quality_reason_codes(row: dict, min_usable_score: int) -> list[str]:
    if row.get("status") != "evaluated":
        return ["phase6_cleanup_quality_not_evaluated"]
    reasons: list[str] = []
    if row.get("usable") is not True:
        reasons.append("phase6_cleanup_unusable")
    if row.get("original_text_removed") is False:
        reasons.append("phase6_cleanup_original_text_visible")
    if row.get("art_preserved") is False:
        reasons.append("phase6_cleanup_art_not_preserved")
    score = row.get("score")
    if isinstance(score, int | float) and score < min_usable_score:
        reasons.append("phase6_cleanup_low_score")
    return list(dict.fromkeys(reasons))


def _manifest(
    cleanup_run_dir: str | Path,
    cleanup_quality_run_dir: str | Path,
    quality_rows: list[dict],
    candidates: list[dict],
    min_usable_score: int,
) -> dict:
    return {
        "schema_version": "autolettering.phase6_cleanup_gate.v1",
        "cleanup_run_dir": str(cleanup_run_dir),
        "cleanup_quality_run_dir": str(cleanup_quality_run_dir),
        "min_usable_score": min_usable_score,
        "quality_row_count": len(quality_rows),
        "candidate_count": len(candidates),
        "candidate_record_ids": [row["record_id"] for row in candidates],
        "gate_policy": {
            "scope": "CTA/CTD matched LaMA cleanup rows only",
            "recommended_route": "quality_gate_gpt_image2_masked_edit",
            "reason": (
                "escalate only when MIMO cleanup quality says a CTA/CTD LaMA repair "
                "is not usable, leaves original text visible, damages art, or scores below threshold"
            ),
        },
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(path: Path, manifest: dict, candidates: list[dict]) -> None:
    lines = [
        "# Phase 6 Cleanup Gate Report",
        "",
        f"Cleanup run directory: `{manifest['cleanup_run_dir']}`",
        f"Cleanup quality run directory: `{manifest['cleanup_quality_run_dir']}`",
        "",
        "## Summary",
        "",
        f"- Quality rows read: {manifest['quality_row_count']}",
        f"- Escalation candidates: {manifest['candidate_count']}",
        f"- Min usable score: {manifest['min_usable_score']}",
        "",
        "## Candidates",
        "",
    ]
    if not candidates:
        lines.append("- None")
    for candidate in candidates:
        quality = candidate["quality"]
        cleanup = candidate["cleanup"]
        lines.extend(
            [
                f"### `{candidate['record_id']}`",
                "",
                f"- Recommended route: `{candidate['recommended_route']}`",
                f"- Reasons: {', '.join(f'`{reason}`' for reason in candidate['reason_codes'])}",
                f"- Cleanup method: `{cleanup.get('method')}`",
                f"- Score: `{quality.get('score')}`",
                f"- Usable: `{quality.get('usable')}`",
                f"- Original text removed: `{quality.get('original_text_removed')}`",
                f"- Art preserved: `{quality.get('art_preserved')}`",
                f"- Source mask: `{cleanup.get('source_mask_path')}`",
                f"- Evaluation image: `{quality.get('evaluation_image_path')}`",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
