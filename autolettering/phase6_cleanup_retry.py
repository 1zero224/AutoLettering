from __future__ import annotations

import json
from pathlib import Path

from .phase6_cleanup_quality import CleanupQualityClient, run_phase6_cleanup_quality
from .phase6_nonbubble import run_phase6_nonbubble_cleanup


DEFAULT_RETRY_METHODS = ["bt_lama_large", "bt_patchmatch", "opencv_telea", "bt_aot"]


def run_phase6_cleanup_retry(
    detection_run_dir: str | Path,
    cleanup_quality_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    methods: list[str] | None = None,
    sample_limit: int = 3,
    quality_client: CleanupQualityClient | None = None,
) -> Path:
    if quality_client is None:
        raise ValueError("quality_client is required unless experiment script builds one from environment")
    run_dir = Path(output_root) / (run_id or "phase6-cleanup-retry")
    run_dir.mkdir(parents=True, exist_ok=True)
    failures = _load_retry_records(Path(cleanup_quality_run_dir) / "cleanup-quality.jsonl", sample_limit)
    retry_methods = methods or DEFAULT_RETRY_METHODS
    records = [
        _retry_record(run_dir, Path(detection_run_dir), failure["record_id"], retry_methods, quality_client)
        for failure in failures
    ]
    summary = {
        "record_count": len(records),
        "methods": retry_methods,
        "records": records,
    }
    _write_json(run_dir / "cleanup-retry-summary.json", summary)
    _write_report(run_dir / "reports" / "phase6-cleanup-retry-report.md", detection_run_dir, cleanup_quality_run_dir, summary)
    return run_dir


def _load_retry_records(path: Path, sample_limit: int) -> list[dict]:
    records: list[dict] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(records) >= sample_limit:
                break
            row = json.loads(line)
            if row.get("record_id") and _needs_retry(row):
                records.append(row)
    return records


def _needs_retry(row: dict) -> bool:
    if row.get("status") != "evaluated":
        return True
    return row.get("usable") is not True or row.get("original_text_removed") is False or row.get("art_preserved") is False


def _retry_record(
    run_dir: Path,
    detection_run_dir: Path,
    record_id: str,
    methods: list[str],
    quality_client: CleanupQualityClient,
) -> dict:
    candidates = [
        _retry_method(run_dir, detection_run_dir, record_id, method, quality_client)
        for method in methods
    ]
    best = _best_candidate(candidates)
    return {
        "record_id": record_id,
        "best_method": best.get("method") if best else None,
        "best_score": best.get("score") if best else None,
        "usable": best.get("usable") if best else False,
        "candidates": candidates,
    }


def _retry_method(
    run_dir: Path,
    detection_run_dir: Path,
    record_id: str,
    method: str,
    quality_client: CleanupQualityClient,
) -> dict:
    candidate_run_id = f"{_safe_name(record_id)}__{method}"
    cleanup_run = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run_dir,
        output_root=run_dir / "candidates",
        run_id=candidate_run_id,
        sample_limit=1,
        record_ids=[record_id],
        inpaint_method=method,
        allow_cta_method_override=True,
    )
    quality_run = run_phase6_cleanup_quality(
        cleanup_run_dir=cleanup_run,
        output_root=run_dir / "quality",
        run_id=candidate_run_id,
        sample_limit=1,
        record_ids=[record_id],
        client=quality_client,
    )
    quality = _first_jsonl(quality_run / "cleanup-quality.jsonl")
    cleanup = _first_jsonl(cleanup_run / "cleanup-results.jsonl")
    return {
        "method": method,
        "cleanup_run_dir": str(cleanup_run),
        "quality_run_dir": str(quality_run),
        "status": quality.get("status"),
        "score": quality.get("score"),
        "usable": quality.get("usable"),
        "original_text_removed": quality.get("original_text_removed"),
        "art_preserved": quality.get("art_preserved"),
        "issues": quality.get("issues", []),
        "summary": quality.get("summary"),
        "before_after_path": (cleanup.get("cleanup") or {}).get("before_after_path"),
        "evaluation_image_path": quality.get("evaluation_image_path"),
    }


def _best_candidate(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    usable = [item for item in candidates if item.get("usable") is True]
    pool = usable or candidates
    return max(pool, key=lambda item: _candidate_score(item))


def _candidate_score(candidate: dict) -> tuple[int, int, int]:
    score = candidate.get("score")
    return (
        int(score) if score is not None else -1,
        1 if candidate.get("original_text_removed") is True else 0,
        1 if candidate.get("art_preserved") is True else 0,
    )


def _first_jsonl(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                return json.loads(line)
    return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(
    path: Path,
    detection_run_dir: str | Path,
    cleanup_quality_run_dir: str | Path,
    summary: dict,
) -> None:
    lines = [
        "# Phase 6 Cleanup Retry Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Cleanup quality run directory: `{cleanup_quality_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records retried: {summary['record_count']}",
        f"- Methods: {', '.join(f'`{method}`' for method in summary['methods'])}",
        "",
        "## Records",
        "",
    ]
    for record in summary["records"]:
        lines.extend(
            [
                f"### `{record['record_id']}`",
                "",
                f"- Best method: `{record.get('best_method')}`",
                f"- Best score: `{record.get('best_score')}`",
                f"- Usable: `{record.get('usable')}`",
                "",
                "| Method | Score | Usable | Text removed | Art preserved |",
                "| --- | ---: | --- | --- | --- |",
            ]
        )
        for candidate in record.get("candidates", []):
            lines.append(
                f"| `{candidate['method']}` | {candidate.get('score')} | {candidate.get('usable')} | "
                f"{candidate.get('original_text_removed')} | {candidate.get('art_preserved')} |"
            )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
