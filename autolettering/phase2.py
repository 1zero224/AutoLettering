from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from .detection.cv_text import detect_text_region, detection_result_to_dict, draw_detection_debug
from .labelplus.models import ManifestImage, ManifestLabel
from .labelplus.parser import parse_labelplus_project
from .phase1 import _select_sample_records, _timestamp_run_id
from .record_selection import normalize_record_ids
from .text_bbox import selected_text_bbox
from .text_body_bbox import selected_text_body_bbox


def run_phase2(
    labelplus_file: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 30,
    radius_x: int = 220,
    radius_y: int = 180,
    record_ids: Iterable[str] | None = None,
) -> Path:
    manifest = parse_labelplus_project(labelplus_file)
    run_dir = Path(output_root) / (run_id or _timestamp_run_id().replace("phase1", "phase2"))
    run_dir.mkdir(parents=True, exist_ok=True)

    selected = _select_detection_records(manifest, sample_limit, record_ids)
    ok_count, failed_count = _write_detections(run_dir, selected, radius_x, radius_y)

    _write_phase2_report(
        output_path=run_dir / "reports" / "phase2-report.md",
        labelplus_file=Path(labelplus_file),
        sample_count=len(selected),
        ok_count=ok_count,
        failed_count=failed_count,
        radius_x=radius_x,
        radius_y=radius_y,
    )
    return run_dir


def _select_detection_records(
    manifest,
    sample_limit: int,
    record_ids: Iterable[str] | None = None,
) -> list[tuple[ManifestImage, ManifestLabel]]:
    wanted = normalize_record_ids(record_ids)
    if wanted is None:
        return _select_sample_records(manifest, sample_limit)
    selected: list[tuple[ManifestImage, ManifestLabel]] = []
    for image in manifest.images:
        for label in image.labels:
            if label.id in wanted:
                selected.append((image, label))
                if len(selected) >= sample_limit:
                    return selected
    return selected


def _write_detections(
    run_dir: Path,
    selected_records: list[tuple[ManifestImage, ManifestLabel]],
    radius_x: int,
    radius_y: int,
) -> tuple[int, int]:
    ok_count = failed_count = 0
    rows: list[dict] = []
    with (run_dir / "detections.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for image, label in selected_records:
            payload = _detect_record(run_dir, image, label, radius_x, radius_y)
            rows.append(payload)
            ok_count += int(payload["status"] == "ok")
            failed_count += int(payload["status"] != "ok")
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _write_manual_review_csv(run_dir / "reports" / "manual-review.csv", rows)
    return ok_count, failed_count


def _detect_record(
    run_dir: Path,
    image: ManifestImage,
    label: ManifestLabel,
    radius_x: int,
    radius_y: int,
) -> dict:
    result = detect_text_region(image.image_path, label, image.width, image.height, radius_x, radius_y)
    debug_path = run_dir / "debug" / "detection" / f"{Path(image.image_name).stem}-{label.record_index}.png"

    payload = detection_result_to_dict(result)
    payload.update(
        {
            "image_name": image.image_name,
            "image_path": str(image.image_path),
            "translated_text": label.translated_text,
            "group_name": label.group_name,
            "debug_image_path": str(debug_path),
        }
    )
    full_bbox, body_bbox = _add_derived_text_bboxes(payload)
    draw_detection_debug(
        image.image_path,
        label,
        result,
        debug_path,
        selected_text_full_xyxy=full_bbox,
        selected_text_body_xyxy=body_bbox,
    )
    return payload


def _add_derived_text_bboxes(payload: dict) -> tuple[tuple[int, int, int, int] | None, tuple[int, int, int, int] | None]:
    if payload.get("status") != "ok" or not payload.get("selected_text_box_xyxy"):
        payload["selected_text_full_xyxy"] = None
        payload["selected_text_body_xyxy"] = None
        return None, None

    full_bbox = selected_text_bbox(payload)
    body_bbox = selected_text_body_bbox(payload)
    payload["selected_text_full_xyxy"] = list(full_bbox)
    payload["selected_text_body_xyxy"] = list(body_bbox)
    return full_bbox, body_bbox


def _write_manual_review_csv(output_path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "record_id",
        "status",
        "confidence",
        "failure_reason",
        "candidate_count",
        "selected_text_box_xyxy",
        "selected_text_full_xyxy",
        "selected_text_body_xyxy",
        "debug_image_path",
        "manual_decision",
        "review_notes",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_manual_review_row(row))


def _manual_review_row(row: dict) -> dict:
    return {
        "record_id": row["record_id"],
        "status": row["status"],
        "confidence": row["confidence"],
        "failure_reason": row.get("failure_reason") or "",
        "candidate_count": len(row.get("candidate_boxes", [])),
        "selected_text_box_xyxy": json.dumps(row.get("selected_text_box_xyxy"), ensure_ascii=False),
        "selected_text_full_xyxy": json.dumps(row.get("selected_text_full_xyxy"), ensure_ascii=False),
        "selected_text_body_xyxy": json.dumps(row.get("selected_text_body_xyxy"), ensure_ascii=False),
        "debug_image_path": row.get("debug_image_path", ""),
        "manual_decision": "",
        "review_notes": "",
    }


def _write_phase2_report(
    output_path: Path,
    labelplus_file: Path,
    sample_count: int,
    ok_count: int,
    failed_count: int,
    radius_x: int,
    radius_y: int,
) -> None:
    lines = [
        "# Phase 2 Detection Report",
        "",
        f"LabelPlus file: `{labelplus_file}`",
        "",
        "## Summary",
        "",
        f"- Sample records: {sample_count}",
        f"- Detected records: {ok_count}",
        f"- Failed records: {failed_count}",
        f"- Search radius: `{radius_x} x {radius_y}`",
        "",
        "## Generated Artifacts",
        "",
        "- `detections.jsonl`",
        "- `debug/detection/*.png`",
        "- `reports/manual-review.csv`",
        "",
        "Debug overlay colors: raw selected box = red, full text evidence box = green, body text box = purple.",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
