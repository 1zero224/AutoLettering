from __future__ import annotations

import json
from pathlib import Path

from .cleanup_runs import CleanupRunInput, normalize_cleanup_run_dirs


SCHEMA_VERSION = "autolettering.phase7.preview.v1"


def write_phase7_manifest(
    output_path: str | Path,
    run_dir: str | Path,
    detection_run_dir: str | Path,
    cleanup_run_dir: CleanupRunInput,
    layout_run_dir: str | Path,
    rows: list[dict],
) -> Path:
    output = Path(output_path)
    run_path = Path(run_dir)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_path.name,
        "inputs": _manifest_inputs(detection_run_dir, cleanup_run_dir, layout_run_dir),
        "summary": _manifest_summary(rows),
        "artifacts": _manifest_artifacts(run_path),
        "pages": _manifest_pages(rows),
        "skipped_records": [row for row in rows if row["status"] == "skipped"],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _manifest_inputs(
    detection_run_dir: str | Path,
    cleanup_run_dir: CleanupRunInput,
    layout_run_dir: str | Path,
) -> dict:
    return {
        "detection_run_dir": str(detection_run_dir),
        "cleanup_run_dirs": [str(path) for path in normalize_cleanup_run_dirs(cleanup_run_dir)],
        "layout_run_dir": str(layout_run_dir),
    }


def _manifest_summary(rows: list[dict]) -> dict:
    pages = [row for row in rows if row["status"] == "page_preview_generated"]
    return {
        "record_count": sum(len(row.get("records", [])) for row in pages),
        "page_count": len(pages),
        "skipped_count": sum(1 for row in rows if row["status"] == "skipped"),
    }


def _manifest_artifacts(run_dir: Path) -> dict:
    return {
        "preview_results_jsonl": str(run_dir / "preview-results.jsonl"),
        "manual_review_csv": str(run_dir / "reports" / "manual-review.csv"),
        "phase7_report": str(run_dir / "reports" / "phase7-report.md"),
    }


def _manifest_pages(rows: list[dict]) -> list[dict]:
    pages: list[dict] = []
    for row in rows:
        if row["status"] != "page_preview_generated":
            continue
        pages.append(
            {
                "image_name": row["image_name"],
                "original_page_path": row["preview"]["original_page_path"],
                "cleaned_page_path": row["preview"]["cleaned_page_path"],
                "page_preview_path": row["preview"]["page_preview_path"],
                "record_count": row["preview"]["record_count"],
                "records": row.get("records", []),
            }
        )
    return pages
