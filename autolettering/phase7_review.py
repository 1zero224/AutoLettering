from __future__ import annotations

import csv
import json
from pathlib import Path


def write_phase7_manual_review_csv(output_path: str | Path, rows: list[dict]) -> Path:
    output = Path(output_path)
    fieldnames = [
        "record_id",
        "status",
        "image_name",
        "translated_text",
        "bbox",
        "cleanup_method",
        "cleanup_crop_path",
        "layout_preview_path",
        "page_preview_path",
        "preview_before_after_path",
        "failure_reason",
        "manual_decision",
        "review_notes",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            for review_row in _manual_review_rows(row):
                writer.writerow(review_row)
    return output


def _manual_review_rows(row: dict) -> list[dict]:
    if row["status"] == "skipped":
        return [_skipped_review_row(row)]
    return [_generated_review_row(row, record) for record in row.get("records", [])]


def _generated_review_row(row: dict, record: dict) -> dict:
    return {
        "record_id": record["record_id"],
        "status": row["status"],
        "image_name": row.get("image_name", ""),
        "translated_text": record.get("translated_text", ""),
        "bbox": json.dumps(record.get("bbox"), ensure_ascii=False),
        "cleanup_method": record.get("cleanup_method") or "",
        "cleanup_crop_path": record.get("cleanup_crop_path", ""),
        "layout_preview_path": record.get("layout_preview_path", ""),
        "page_preview_path": row.get("preview", {}).get("page_preview_path", ""),
        "preview_before_after_path": record.get("preview_before_after_path", ""),
        "failure_reason": "",
        "manual_decision": "",
        "review_notes": "",
    }


def _skipped_review_row(row: dict) -> dict:
    return {
        "record_id": row["record_id"],
        "status": row["status"],
        "image_name": "",
        "translated_text": "",
        "bbox": "",
        "cleanup_method": "",
        "cleanup_crop_path": "",
        "layout_preview_path": "",
        "page_preview_path": "",
        "preview_before_after_path": "",
        "failure_reason": row.get("preview", {}).get("failure_reason", ""),
        "manual_decision": "",
        "review_notes": "",
    }
