from __future__ import annotations

import json
from pathlib import Path

from .detection.cv_text import detect_text_region, detection_result_to_dict, draw_detection_debug
from .labelplus.models import ManifestImage, ManifestLabel
from .labelplus.parser import parse_labelplus_project
from .phase1 import _select_sample_records, _timestamp_run_id


def run_phase2(
    labelplus_file: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 30,
    radius_x: int = 220,
    radius_y: int = 180,
) -> Path:
    manifest = parse_labelplus_project(labelplus_file)
    run_dir = Path(output_root) / (run_id or _timestamp_run_id().replace("phase1", "phase2"))
    run_dir.mkdir(parents=True, exist_ok=True)

    selected = _select_sample_records(manifest, sample_limit)
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


def _write_detections(
    run_dir: Path,
    selected_records: list[tuple[ManifestImage, ManifestLabel]],
    radius_x: int,
    radius_y: int,
) -> tuple[int, int]:
    ok_count = failed_count = 0
    with (run_dir / "detections.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for image, label in selected_records:
            payload = _detect_record(run_dir, image, label, radius_x, radius_y)
            ok_count += int(payload["status"] == "ok")
            failed_count += int(payload["status"] != "ok")
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
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
    draw_detection_debug(image.image_path, label, result, debug_path)

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
    return payload


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
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
