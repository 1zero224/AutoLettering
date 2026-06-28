from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import multiprocessing as mp
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.detection.comic_text_bubble import DEFAULT_COMIC_DETECTOR_MODEL_PATH
from autolettering.labelplus.parser import parse_labelplus_project
from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.phase1 import run_phase1
from autolettering.phase2 import run_phase2
from autolettering.phase3 import run_phase3
from autolettering.phase3_vision import _select_one as _select_one_font_with_mimo
from autolettering.phase3_vision import run_phase3_vision_selection
from autolettering.phase4 import run_phase4
from autolettering.phase6 import run_phase6_bubble_cleanup
from autolettering.phase7 import run_phase7_preview
from autolettering.phase8 import run_phase8_photoshop_export


SCHEMA_VERSION = "autolettering.gbc06_frame_in_comic_pipeline.v1"
MIMO_RESUME_SCHEMA_VERSION = "mimo-font-selection-resume.v2"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the GBC06 frame-in comic RT-DETRv2 Phase 1-8 pipeline."
    )
    parser.add_argument("--labelplus-file", default=r"GBC06 (已翻 斗笠)\翻译_0.txt")
    parser.add_argument("--font-dir", default="工具箱漫画字体V2.5")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=1000)
    parser.add_argument("--target-group-name", default="框内")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--comic-detector-model-path", default=str(DEFAULT_COMIC_DETECTOR_MODEL_PATH))
    parser.add_argument("--comic-detector-conf-threshold", type=float, default=0.5)
    parser.add_argument("--comic-detector-max-distance-px", type=float, default=120.0)
    parser.add_argument("--font-limit", type=int, default=12)
    parser.add_argument(
        "--mimo-timeout-sec",
        type=int,
        default=90,
        help="Per-record MIMO font-selection timeout. Timed-out records fall back deterministically.",
    )
    parser.add_argument(
        "--mimo-max-consecutive-timeouts",
        type=int,
        default=2,
        help="After this many consecutive MIMO timeouts, remaining font selections use deterministic fallback.",
    )
    parser.add_argument(
        "--cleanup-method",
        default="text_mask_inpaint",
        choices=["region_fill", "soft_region_fill", "mask_fill", "text_mask_inpaint"],
    )
    parser.add_argument(
        "--inpaint-method",
        default="opencv_telea",
        choices=[
            "local_diffusion",
            "flat_median_fill",
            "opencv_telea",
            "opencv_ns",
            "bt_patchmatch",
            "bt_aot",
            "bt_lama_large",
        ],
    )
    parser.add_argument("--mask-dilate-px", type=int, default=3)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    _load_env_file(Path(args.env_file))
    mimo_config = _mimo_config_from_env()
    run_dir = run_full_gbc06_frame_in_comic_pipeline(
        labelplus_file=Path(args.labelplus_file),
        font_dir=Path(args.font_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        target_group_name=args.target_group_name,
        comic_detector_model_path=Path(args.comic_detector_model_path),
        comic_detector_conf_threshold=args.comic_detector_conf_threshold,
        comic_detector_max_distance_px=args.comic_detector_max_distance_px,
        font_limit=args.font_limit,
        cleanup_method=args.cleanup_method,
        inpaint_method=args.inpaint_method,
        mask_dilate_px=args.mask_dilate_px,
        mimo_client=MimoVisionClient(mimo_config),
        mimo_config=mimo_config,
        mimo_model=os.environ.get("MIMO_VISION_MODEL"),
        mimo_timeout_sec=args.mimo_timeout_sec,
        mimo_max_consecutive_timeouts=args.mimo_max_consecutive_timeouts,
    )
    print(run_dir)


def run_full_gbc06_frame_in_comic_pipeline(
    labelplus_file: str | Path,
    font_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 1000,
    target_group_name: str = "框内",
    comic_detector_model_path: str | Path = DEFAULT_COMIC_DETECTOR_MODEL_PATH,
    comic_detector_conf_threshold: float = 0.5,
    comic_detector_max_distance_px: float = 120.0,
    font_limit: int = 12,
    cleanup_method: str = "text_mask_inpaint",
    inpaint_method: str = "opencv_telea",
    mask_dilate_px: int = 3,
    mimo_client: Any | None = None,
    mimo_config: MimoVisionConfig | None = None,
    mimo_model: str | None = None,
    mimo_timeout_sec: int = 90,
    mimo_max_consecutive_timeouts: int = 2,
) -> Path:
    if mimo_client is None:
        raise ValueError("mimo_client is required for real Phase 3 font selection")
    if sample_limit <= 0:
        raise ValueError("sample_limit must be positive")

    context = _prepare_run(labelplus_file, output_root, run_id, target_group_name, sample_limit)
    early_runs = _run_detection_and_font_comparison(
        context,
        font_dir,
        comic_detector_model_path,
        comic_detector_conf_threshold,
        comic_detector_max_distance_px,
        font_limit,
    )
    selection_run = _run_font_selection(
        early_runs["phase3_font_comparison"],
        context,
        mimo_client,
        mimo_config,
        mimo_timeout_sec,
        mimo_max_consecutive_timeouts,
    )
    late_runs = _run_layout_cleanup_preview_export(
        context,
        early_runs["phase2_comic_detection"],
        selection_run,
        cleanup_method,
        inpaint_method,
        mask_dilate_px,
    )
    stage_runs = {**early_runs, "phase3_mimo_font_selection": selection_run, **late_runs}
    _write_pipeline_outputs(
        context,
        font_dir,
        stage_runs,
        comic_detector_model_path,
        comic_detector_conf_threshold,
        comic_detector_max_distance_px,
        font_limit,
        cleanup_method,
        inpaint_method,
        mask_dilate_px,
        mimo_model,
        mimo_timeout_sec,
        mimo_max_consecutive_timeouts,
    )
    return context["run_dir"]


def _prepare_run(
    labelplus_file: str | Path,
    output_root: str | Path,
    run_id: str | None,
    target_group_name: str,
    sample_limit: int,
) -> dict:
    labelplus_path = Path(labelplus_file)
    run_dir = Path(output_root) / (run_id or _timestamp_run_id())
    nested_root = run_dir / "runs"
    nested_root.mkdir(parents=True, exist_ok=True)
    frame_records = _frame_in_records(labelplus_path, target_group_name, sample_limit)
    _write_jsonl(run_dir / "frame-in-records.jsonl", frame_records)
    return {
        "labelplus_path": labelplus_path,
        "run_dir": run_dir,
        "nested_root": nested_root,
        "frame_records": frame_records,
        "record_ids": [record["record_id"] for record in frame_records],
        "target_group_name": target_group_name,
        "sample_limit": sample_limit,
    }


def _run_detection_and_font_comparison(
    context: dict,
    font_dir: str | Path,
    comic_detector_model_path: str | Path,
    comic_detector_conf_threshold: float,
    comic_detector_max_distance_px: float,
    font_limit: int,
) -> dict[str, Path]:
    phase1_run = run_phase1(
        labelplus_file=context["labelplus_path"],
        output_root=context["nested_root"],
        run_id="phase1-parse",
        sample_limit=context["sample_limit"],
    )
    phase2_run = run_phase2(
        labelplus_file=context["labelplus_path"],
        output_root=context["nested_root"],
        run_id="phase2-comic-rtdetrv2",
        sample_limit=context["sample_limit"],
        record_ids=context["record_ids"],
        detection_strategy="comic_rtdetrv2",
        comic_detector_model_path=Path(comic_detector_model_path),
        comic_detector_conf_threshold=comic_detector_conf_threshold,
        comic_detector_max_distance_px=comic_detector_max_distance_px,
    )
    phase3_run = run_phase3(
        labelplus_file=context["labelplus_path"],
        detection_run_dir=phase2_run,
        font_dir=Path(font_dir),
        output_root=context["nested_root"],
        run_id="phase3-font-comparison",
        sample_limit=context["sample_limit"],
        font_limit=font_limit,
        record_ids=context["record_ids"],
    )
    return {"phase1_parse": phase1_run, "phase2_comic_detection": phase2_run, "phase3_font_comparison": phase3_run}


def _run_font_selection(
    comparison_run: Path,
    context: dict,
    mimo_client: Any,
    mimo_config: MimoVisionConfig | None,
    timeout_sec: int,
    max_consecutive_timeouts: int,
) -> Path:
    if mimo_config is None:
        return run_phase3_vision_selection(
            input_run_dir=comparison_run,
            output_root=context["nested_root"],
            run_id="phase3-mimo-font-selection",
            sample_limit=context["sample_limit"],
            client=mimo_client,
            record_ids=context["record_ids"],
        )
    return _run_phase3_vision_selection_resumable(
        input_run_dir=comparison_run,
        output_root=context["nested_root"],
        run_id="phase3-mimo-font-selection",
        sample_limit=context["sample_limit"],
        record_ids=context["record_ids"],
        config=mimo_config,
        timeout_sec=timeout_sec,
        max_consecutive_timeouts=max_consecutive_timeouts,
    )


def _run_layout_cleanup_preview_export(
    context: dict,
    phase2_run: Path,
    phase3_selection_run: Path,
    cleanup_method: str,
    inpaint_method: str,
    mask_dilate_px: int,
) -> dict[str, Path]:
    phase4_run = run_phase4(
        selection_run_dir=phase3_selection_run,
        detection_run_dir=phase2_run,
        output_root=context["nested_root"],
        run_id="phase4-layout-search",
        sample_limit=context["sample_limit"],
        record_ids=context["record_ids"],
    )
    phase6_run = run_phase6_bubble_cleanup(
        detection_run_dir=phase2_run,
        layout_run_dir=phase4_run,
        output_root=context["nested_root"],
        run_id="phase6-bubble-cleanup",
        sample_limit=context["sample_limit"],
        cleanup_method=cleanup_method,
        record_ids=context["record_ids"],
        inpaint_method=inpaint_method,
        mask_dilate_px=mask_dilate_px,
    )
    phase7_run = run_phase7_preview(
        detection_run_dir=phase2_run,
        cleanup_run_dir=[phase6_run],
        layout_run_dir=phase4_run,
        output_root=context["nested_root"],
        run_id="phase7-page-preview",
        sample_limit=context["sample_limit"],
    )
    phase8_run = run_phase8_photoshop_export(
        detection_run_dir=phase2_run,
        font_selection_run_dir=phase3_selection_run,
        layout_run_dir=phase4_run,
        cleanup_run_dir=[phase6_run],
        output_root=context["nested_root"],
        run_id="phase8-photoshop-export",
        sample_limit=context["sample_limit"],
        preview_run_dir=phase7_run,
    )
    return {"phase4_layout": phase4_run, "phase6_bubble_cleanup": phase6_run, "phase7_page_preview": phase7_run, "phase8_photoshop_export": phase8_run}


def _write_pipeline_outputs(
    context: dict,
    font_dir: str | Path,
    stage_runs: dict[str, Path],
    comic_detector_model_path: str | Path,
    comic_detector_conf_threshold: float,
    comic_detector_max_distance_px: float,
    font_limit: int,
    cleanup_method: str,
    inpaint_method: str,
    mask_dilate_px: int,
    mimo_model: str | None,
    mimo_timeout_sec: int,
    mimo_max_consecutive_timeouts: int,
) -> None:
    manifest = _pipeline_manifest(
        context["labelplus_path"],
        font_dir,
        context["run_dir"],
        stage_runs,
        context["frame_records"],
        context["target_group_name"],
        context["sample_limit"],
        comic_detector_model_path,
        comic_detector_conf_threshold,
        comic_detector_max_distance_px,
        font_limit,
        cleanup_method,
        inpaint_method,
        mask_dilate_px,
        mimo_model,
        mimo_timeout_sec,
        mimo_max_consecutive_timeouts,
    )
    _write_json(context["run_dir"] / "manifest.json", manifest)
    _write_report(context["run_dir"] / "reports" / "pipeline-report.md", manifest)


def _frame_in_records(labelplus_file: Path, target_group_name: str, sample_limit: int) -> list[dict]:
    manifest = parse_labelplus_project(labelplus_file)
    rows: list[dict] = []
    for image in manifest.images:
        for label in image.labels:
            if label.group_name != target_group_name:
                continue
            rows.append(
                {
                    "record_id": label.id,
                    "image_name": image.image_name,
                    "image_path": str(image.image_path),
                    "page_index": label.page_index,
                    "record_index": label.record_index,
                    "group_name": label.group_name,
                    "x_px": label.x_px,
                    "y_px": label.y_px,
                    "translated_text": label.translated_text,
                }
            )
            if len(rows) >= sample_limit:
                return rows
    return rows


def _pipeline_manifest(
    labelplus_file: Path,
    font_dir: str | Path,
    run_dir: Path,
    stage_runs: dict[str, Path],
    frame_records: list[dict],
    target_group_name: str,
    sample_limit: int,
    comic_detector_model_path: str | Path,
    comic_detector_conf_threshold: float,
    comic_detector_max_distance_px: float,
    font_limit: int,
    cleanup_method: str,
    inpaint_method: str,
    mask_dilate_px: int,
    mimo_model: str | None,
    mimo_timeout_sec: int,
    mimo_max_consecutive_timeouts: int,
) -> dict:
    summary = _stage_summary(stage_runs)
    configuration = _configuration_payload(
        comic_detector_model_path,
        comic_detector_conf_threshold,
        comic_detector_max_distance_px,
        font_limit,
        cleanup_method,
        inpaint_method,
        mask_dilate_px,
        mimo_model,
        mimo_timeout_sec,
        mimo_max_consecutive_timeouts,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "labelplus_file": str(labelplus_file),
        "font_dir": str(font_dir),
        "run_dir": str(run_dir),
        "target_group_name": target_group_name,
        "sample_limit": sample_limit,
        "frame_in_record_count": len(frame_records),
        "frame_in_record_ids": [row["record_id"] for row in frame_records],
        "stage_runs": {name: str(path) for name, path in stage_runs.items()},
        "configuration": configuration,
        "stage_summary": summary,
        "artifact_index": _artifact_index(run_dir, stage_runs),
        "binding_plan": {
            "point_to_box_matching": "LabelPlus point -> nearest comic RT-DETRv2 text_bubble/text_free bbox within configured distance",
            "font_selection": "Phase 3 MIMO chooses one font from deterministic comparison grids",
            "font_size_layout": "Phase 4 searches font size, orientation, line breaks, spacing, color, and target bbox fit",
            "cleanup_and_lettering": "Phase 6 removes original text inside matched frame-in boxes; Phase 7/8 place editable text only inside those boxes",
        },
    }


def _configuration_payload(
    comic_detector_model_path: str | Path,
    comic_detector_conf_threshold: float,
    comic_detector_max_distance_px: float,
    font_limit: int,
    cleanup_method: str,
    inpaint_method: str,
    mask_dilate_px: int,
    mimo_model: str | None,
    mimo_timeout_sec: int,
    mimo_max_consecutive_timeouts: int,
) -> dict:
    return {
        "phase2_detection_strategy": "comic_rtdetrv2",
        "comic_detector_model_path": str(comic_detector_model_path),
        "comic_detector_conf_threshold": comic_detector_conf_threshold,
        "comic_detector_max_distance_px": comic_detector_max_distance_px,
        "font_limit": font_limit,
        "mimo_font_selection_model": mimo_model,
        "mimo_timeout_sec": mimo_timeout_sec,
        "mimo_max_consecutive_timeouts": mimo_max_consecutive_timeouts,
        "cleanup_method": cleanup_method,
        "inpaint_method": inpaint_method,
        "mask_dilate_px": mask_dilate_px,
        "lettering_scope": "inside_bubble_only",
        "outside_text_lettering": "excluded_by_group_filter",
    }


def _run_phase3_vision_selection_resumable(
    input_run_dir: str | Path,
    output_root: str | Path,
    run_id: str,
    sample_limit: int,
    record_ids: list[str],
    config: MimoVisionConfig,
    timeout_sec: int,
    max_consecutive_timeouts: int,
) -> Path:
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    selection_path = run_dir / "font-selections.jsonl"
    api_path = run_dir / "reports" / "api-calls.jsonl"
    comparison_path = Path(input_run_dir) / "font-comparisons.jsonl"
    rows = _comparison_rows(comparison_path, sample_limit, record_ids)
    _prepare_mimo_resume_files(
        run_dir,
        selection_path,
        api_path,
        input_run_dir,
        comparison_path,
        rows,
        config,
        timeout_sec,
        max_consecutive_timeouts,
    )
    completed_ids = _normalize_mimo_resume_rows(selection_path, api_path, rows)
    consecutive_timeouts = 0

    for row in rows:
        if str(row.get("record_id")) in completed_ids:
            continue
        if max_consecutive_timeouts > 0 and consecutive_timeouts >= max_consecutive_timeouts:
            selection, api_call = _font_timeout_fallback(
                row,
                f"mimo_disabled_after_{max_consecutive_timeouts}_consecutive_timeouts",
                timeout_sec,
            )
        else:
            selection, api_call, timed_out = _select_font_with_process_timeout(row, config, timeout_sec)
            consecutive_timeouts = consecutive_timeouts + 1 if timed_out else 0
        _append_jsonl(api_path, api_call)
        _append_jsonl(selection_path, selection)
        completed_ids.add(str(row.get("record_id")))

    selections = _load_jsonl(selection_path)
    _write_mimo_selection_report(run_dir / "reports" / "phase3-vision-report.md", input_run_dir, selections, timeout_sec)
    return run_dir


def _prepare_mimo_resume_files(
    run_dir: Path,
    selection_path: Path,
    api_path: Path,
    input_run_dir: str | Path,
    comparison_path: Path,
    rows: list[dict],
    config: MimoVisionConfig,
    timeout_sec: int,
    max_consecutive_timeouts: int,
) -> None:
    metadata_path = run_dir / "reports" / "resume-metadata.json"
    metadata = _mimo_resume_metadata(
        input_run_dir,
        comparison_path,
        rows,
        config,
        timeout_sec,
        max_consecutive_timeouts,
    )
    previous = _load_json(metadata_path)
    if previous != metadata:
        _unlink_if_exists(selection_path)
        _unlink_if_exists(api_path)
    _write_json(metadata_path, metadata)


def _mimo_resume_metadata(
    input_run_dir: str | Path,
    comparison_path: Path,
    rows: list[dict],
    config: MimoVisionConfig,
    timeout_sec: int,
    max_consecutive_timeouts: int,
) -> dict:
    return {
        "schema_version": MIMO_RESUME_SCHEMA_VERSION,
        "input_run_dir": str(input_run_dir),
        "font_comparisons_sha256": _file_sha256(comparison_path),
        "filtered_rows_sha256": _stable_json_sha256(rows),
        "record_ids": [str(row.get("record_id")) for row in rows],
        "mimo_base_url": config.base_url,
        "mimo_model": config.model,
        "timeout_sec": timeout_sec,
        "max_consecutive_timeouts": max_consecutive_timeouts,
        "fallback_policy": "deterministic_first_candidate_after_timeout_or_worker_failure",
    }


def _normalize_mimo_resume_rows(selection_path: Path, api_path: Path, rows: list[dict]) -> set[str]:
    target_ids = [str(row.get("record_id")) for row in rows]
    wanted = set(target_ids)
    selections_by_id = _latest_rows_by_id(_load_jsonl(selection_path), wanted)
    api_calls_by_id = _latest_rows_by_id(_load_jsonl(api_path), wanted)
    completed_ids = {record_id for record_id in target_ids if record_id in selections_by_id and record_id in api_calls_by_id}
    _write_jsonl(selection_path, [selections_by_id[record_id] for record_id in target_ids if record_id in completed_ids])
    _write_jsonl(api_path, [api_calls_by_id[record_id] for record_id in target_ids if record_id in completed_ids])
    return completed_ids


def _latest_rows_by_id(rows: list[dict], wanted: set[str]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for row in rows:
        record_id = str(row.get("record_id"))
        if record_id in wanted:
            indexed[record_id] = row
    return indexed


def _comparison_rows(path: Path, sample_limit: int, record_ids: list[str]) -> list[dict]:
    wanted = set(record_ids)
    rows: list[dict] = []
    for row in _load_jsonl(path):
        if len(rows) >= sample_limit:
            break
        if row.get("record_id") in wanted and row.get("status") == "candidates_generated":
            rows.append(row)
    return rows


def _select_font_with_process_timeout(
    row: dict,
    config: MimoVisionConfig,
    timeout_sec: int,
) -> tuple[dict, dict, bool]:
    if timeout_sec <= 0:
        client = MimoVisionClient(config)
        selection, api_call = _select_one_font_with_mimo(row, client)
        return selection, api_call, False

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=_mimo_font_selection_worker, args=(row, config, queue))
    process.start()
    process.join(timeout_sec)
    if process.is_alive():
        process.terminate()
        process.join()
        selection, api_call = _font_timeout_fallback(row, "api_timeout", timeout_sec)
        return selection, api_call, True

    try:
        payload = queue.get(True, 1)
    except Exception:
        selection, api_call = _font_timeout_fallback(row, "worker_returned_no_result", timeout_sec)
        return selection, api_call, False
    if payload.get("status") == "ok":
        return payload["selection"], payload["api_call"], False
    selection, api_call = _font_timeout_fallback(row, payload.get("failure_reason") or "worker_failed", timeout_sec)
    return selection, api_call, False


def _mimo_font_selection_worker(row: dict, config: MimoVisionConfig, queue) -> None:
    try:
        selection, api_call = _select_one_font_with_mimo(row, MimoVisionClient(config))
        queue.put({"status": "ok", "selection": selection, "api_call": api_call})
    except Exception as exc:  # pragma: no cover - defensive subprocess boundary.
        queue.put({"status": "failed", "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"})


def _font_timeout_fallback(row: dict, reason: str, timeout_sec: int) -> tuple[dict, dict]:
    fallback_font = (row.get("candidate_fonts") or [{}])[0] if row.get("candidate_fonts") else None
    selection = {
        "record_id": row["record_id"],
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": "selected" if fallback_font else "failed",
        "selected_font_id": fallback_font.get("font_id") if fallback_font else None,
        "selected_font": fallback_font,
        "confidence": 0.0 if fallback_font else None,
        "model_reasoning_summary": f"deterministic fallback after MIMO font selection failure: {reason}",
        "failure_reason": reason,
        "selection_source": "deterministic_fallback" if fallback_font else "none",
        "comparison_image_path": row.get("comparison_image_path"),
        "source_crop_path": row.get("source_crop_path"),
        "raw_model_text": None,
    }
    api_call = {
        "record_id": row["record_id"],
        "status": "failed",
        "request": {
            "image_path": row.get("comparison_image_path"),
            "timeout_sec": timeout_sec,
            "candidate_count": len(row.get("candidate_fonts") or []),
        },
        "response": {
            "error_type": "TimeoutError" if reason == "api_timeout" else "RuntimeError",
            "error_message": reason,
        },
    }
    return selection, api_call


def _write_mimo_selection_report(path: Path, input_run_dir: str | Path, selections: list[dict], timeout_sec: int) -> None:
    selected = sum(1 for row in selections if row.get("status") == "selected")
    failed = len(selections) - selected
    lines = [
        "# Phase 3 MIMO Font Selection Report",
        "",
        f"Input run directory: `{input_run_dir}`",
        f"Per-record timeout: `{timeout_sec}s`",
        "",
        "## Summary",
        "",
        f"- Records submitted: {len(selections)}",
        f"- Selected: {selected}",
        f"- Failed: {failed}",
        f"- Selection sources: {_format_counts(_counts(row.get('selection_source') for row in selections))}",
        "",
        "## Generated Artifacts",
        "",
        "- `font-selections.jsonl`",
        "- `reports/api-calls.jsonl`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _stage_summary(stage_runs: dict[str, Path]) -> dict[str, Any]:
    phase2_rows = _load_jsonl(stage_runs["phase2_comic_detection"] / "detections.jsonl")
    phase3_comparison_rows = _load_jsonl(stage_runs["phase3_font_comparison"] / "font-comparisons.jsonl")
    phase3_selection_rows = _load_jsonl(stage_runs["phase3_mimo_font_selection"] / "font-selections.jsonl")
    phase3_api_rows = _load_jsonl(stage_runs["phase3_mimo_font_selection"] / "reports" / "api-calls.jsonl")
    phase4_rows = _load_jsonl(stage_runs["phase4_layout"] / "layout-results.jsonl")
    phase6_rows = _load_jsonl(stage_runs["phase6_bubble_cleanup"] / "cleanup-results.jsonl")
    phase7_rows = _load_jsonl(stage_runs["phase7_page_preview"] / "preview-results.jsonl")
    phase8_manifest = _load_json(stage_runs["phase8_photoshop_export"] / "photoshop-manifest.json")
    return {
        "phase2": _phase2_summary(phase2_rows),
        "phase3_font_comparison": {
            "comparison_rows": len(phase3_comparison_rows),
            "status_counts": _counts(row.get("status") for row in phase3_comparison_rows),
            "candidate_fonts_per_record": _candidate_font_count(phase3_comparison_rows),
        },
        "phase3_mimo_font_selection": {
            "selection_rows": len(phase3_selection_rows),
            "status_counts": _counts(row.get("status") for row in phase3_selection_rows),
            "selection_source_counts": _counts(row.get("selection_source") for row in phase3_selection_rows),
            "api_status_counts": _counts(row.get("status") for row in phase3_api_rows),
        },
        "phase4_layout": {
            "layout_rows": len(phase4_rows),
            "status_counts": _counts(row.get("status") for row in phase4_rows),
            "orientation_counts": _counts((row.get("layout") or {}).get("orientation") for row in phase4_rows),
        },
        "phase6_bubble_cleanup": {
            "cleanup_rows": len(phase6_rows),
            "status_counts": _counts(row.get("status") for row in phase6_rows),
            "method_counts": _counts((row.get("cleanup") or {}).get("method") for row in phase6_rows),
        },
        "phase7_page_preview": {
            "preview_rows": len(phase7_rows),
            "status_counts": _counts(row.get("status") for row in phase7_rows),
            "page_preview_count": sum(1 for row in phase7_rows if row.get("status") == "page_preview_generated"),
            "preview_record_count": sum(len(row.get("records", [])) for row in phase7_rows),
        },
        "phase8_photoshop_export": {
            "page_count": (phase8_manifest.get("summary") or {}).get("page_count", 0),
            "text_layer_count": (phase8_manifest.get("summary") or {}).get("record_count", 0),
            "repaired_page_count": sum(1 for page in phase8_manifest.get("pages", []) if page.get("repaired_image_path")),
        },
    }


def _phase2_summary(rows: list[dict]) -> dict[str, Any]:
    distances = [
        float(match["distance_px"])
        for row in rows
        for match in [row.get("comic_text_bubble_match") or {}]
        if match.get("status") == "matched" and isinstance(match.get("distance_px"), int | float)
    ]
    scores = [
        float(match["selected_score"])
        for row in rows
        for match in [row.get("comic_text_bubble_match") or {}]
        if match.get("status") == "matched" and isinstance(match.get("selected_score"), int | float)
    ]
    return {
        "detection_rows": len(rows),
        "status_counts": _counts(row.get("status") for row in rows),
        "match_status_counts": _counts((row.get("comic_text_bubble_match") or {}).get("status") for row in rows),
        "selected_label_counts": _counts((row.get("comic_text_bubble_match") or {}).get("selected_label") for row in rows),
        "failure_reason_counts": _counts(row.get("failure_reason") for row in rows),
        "matched_distance_max_px": round(max(distances), 3) if distances else None,
        "matched_distance_p95_px": _percentile(distances, 0.95),
        "selected_score_min": round(min(scores), 4) if scores else None,
    }


def _artifact_index(run_dir: Path, stage_runs: dict[str, Path]) -> dict[str, Any]:
    return {
        "pipeline_manifest": str(run_dir / "manifest.json"),
        "pipeline_report": str(run_dir / "reports" / "pipeline-report.md"),
        "frame_in_records": str(run_dir / "frame-in-records.jsonl"),
        "phase1_manifest": str(stage_runs["phase1_parse"] / "manifest.json"),
        "phase1_label_point_debug": str(stage_runs["phase1_parse"] / "debug" / "label_points"),
        "phase2_detections": str(stage_runs["phase2_comic_detection"] / "detections.jsonl"),
        "phase2_detection_debug": str(stage_runs["phase2_comic_detection"] / "debug" / "detection"),
        "phase2_manual_review": str(stage_runs["phase2_comic_detection"] / "reports" / "manual-review.csv"),
        "phase3_font_index": str(stage_runs["phase3_font_comparison"] / "font-index.jsonl"),
        "phase3_font_comparisons": str(stage_runs["phase3_font_comparison"] / "font-comparisons.jsonl"),
        "phase3_font_comparison_debug": str(stage_runs["phase3_font_comparison"] / "debug" / "font_comparison"),
        "phase3_mimo_selections": str(stage_runs["phase3_mimo_font_selection"] / "font-selections.jsonl"),
        "phase3_mimo_api_calls": str(stage_runs["phase3_mimo_font_selection"] / "reports" / "api-calls.jsonl"),
        "phase4_layout_results": str(stage_runs["phase4_layout"] / "layout-results.jsonl"),
        "phase4_layout_debug": str(stage_runs["phase4_layout"] / "debug" / "layout_candidates"),
        "phase6_cleanup_results": str(stage_runs["phase6_bubble_cleanup"] / "cleanup-results.jsonl"),
        "phase6_cleanup_crops": str(stage_runs["phase6_bubble_cleanup"] / "crops"),
        "phase7_preview_results": str(stage_runs["phase7_page_preview"] / "preview-results.jsonl"),
        "phase7_pages": str(stage_runs["phase7_page_preview"] / "pages"),
        "phase7_page_overlays": str(stage_runs["phase7_page_preview"] / "debug" / "page_overlays"),
        "phase8_photoshop_manifest": str(stage_runs["phase8_photoshop_export"] / "photoshop-manifest.json"),
        "phase8_photoshop_import_jsx": str(stage_runs["phase8_photoshop_export"] / "photoshop-import.jsx"),
        "phase8_validation_checklist": str(
            stage_runs["phase8_photoshop_export"] / "reports" / "photoshop-validation-checklist.md"
        ),
    }


def _write_report(path: Path, manifest: dict) -> None:
    lines = [
        "# GBC06 框内 Comic RT-DETRv2 全链路报告",
        "",
        *_report_scope_lines(manifest),
        *_report_binding_lines(manifest["configuration"]),
        *_report_config_lines(manifest),
        *_report_stage_run_lines(manifest["stage_runs"]),
        *_report_metric_lines(manifest["stage_summary"]),
        *_report_artifact_lines(manifest["artifact_index"]),
        *_report_explanation_lines(),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _report_scope_lines(manifest: dict) -> list[str]:
    return [
        "## 目标与范围",
        "",
        f"- LabelPlus: `{manifest['labelplus_file']}`",
        f"- 目标分组: `{manifest['target_group_name']}`",
        f"- 框内记录数: {manifest['frame_in_record_count']}",
        "- 框外文字: 本次明确排除，不进入 Phase 2-8 嵌字链路。",
        "- 嵌字方式: 清理框内原文字后叠加可编辑文字层，不使用 gpt-image-2 直接生成框内文字位图。",
        "",
    ]


def _report_binding_lines(config: dict) -> list[str]:
    return [
        "## 核心绑定方案",
        "",
        "- Phase 2 使用 `comic_rtdetrv2`，将 LabelPlus 点位匹配到最近的 `text_bubble` / `text_free` 检测框。",
        f"- 匹配阈值: {config['comic_detector_max_distance_px']} px；检测置信度阈值: {config['comic_detector_conf_threshold']}。",
        "- Phase 3 生成候选字体对比图，并调用 MIMO 视觉模型选择字体。",
        "- Phase 4 根据绑定框自动搜索字号、方向、换行、行距、字距、颜色和目标区域。",
        "- Phase 6 只对 `框内` 记录执行清字；Phase 7/8 只把框内记录合成为预览与 Photoshop 可编辑文本层。",
        "",
    ]


def _report_config_lines(manifest: dict) -> list[str]:
    config = manifest["configuration"]
    return [
        "## 配置",
        "",
        f"- Comic detector model: `{config['comic_detector_model_path']}`",
        f"- MIMO font selection model: `{config['mimo_font_selection_model']}`",
        f"- Font dir: `{manifest['font_dir']}`",
        f"- Font candidates per record: {config['font_limit']}",
        f"- Cleanup method: `{config['cleanup_method']}` / `{config['inpaint_method']}`",
        f"- Text mask dilation: {config['mask_dilate_px']} px",
        "",
    ]


def _report_stage_run_lines(stage_runs: dict) -> list[str]:
    labels = {
        "phase1_parse": "Phase 1 parse",
        "phase2_comic_detection": "Phase 2 comic detection",
        "phase3_font_comparison": "Phase 3 font comparison",
        "phase3_mimo_font_selection": "Phase 3 MIMO font selection",
        "phase4_layout": "Phase 4 layout",
        "phase6_bubble_cleanup": "Phase 6 bubble cleanup",
        "phase7_page_preview": "Phase 7 page preview",
        "phase8_photoshop_export": "Phase 8 Photoshop export",
    }
    return ["## 阶段产出", "", *[f"- {label}: `{stage_runs[key]}`" for key, label in labels.items()], ""]


def _report_metric_lines(summary: dict) -> list[str]:
    return [
        "## 阶段指标",
        "",
        *_phase2_metric_lines(summary["phase2"]),
        *_phase3_metric_lines(summary),
        *_phase4_8_metric_lines(summary),
    ]


def _phase2_metric_lines(phase2: dict) -> list[str]:
    return [
        "### Phase 2",
        "",
        f"- Detection rows: {phase2['detection_rows']}",
        f"- Status: {_format_counts(phase2['status_counts'])}",
        f"- Comic match: {_format_counts(phase2['match_status_counts'])}",
        f"- Selected labels: {_format_counts(phase2['selected_label_counts'])}",
        f"- Failure reasons: {_format_counts(phase2['failure_reason_counts'])}",
        f"- Matched max distance: {phase2['matched_distance_max_px']} px",
        f"- Matched p95 distance: {phase2['matched_distance_p95_px']} px",
        f"- Min selected score: {phase2['selected_score_min']}",
        "",
    ]


def _phase3_metric_lines(summary: dict) -> list[str]:
    comparison = summary["phase3_font_comparison"]
    selection = summary["phase3_mimo_font_selection"]
    return [
        "### Phase 3",
        "",
        f"- Font comparison rows: {comparison['comparison_rows']}",
        f"- Candidate fonts per record: {comparison['candidate_fonts_per_record']}",
        f"- Font selection rows: {selection['selection_rows']}",
        f"- Selection status: {_format_counts(selection['status_counts'])}",
        f"- Selection source: {_format_counts(selection['selection_source_counts'])}",
        f"- MIMO API call status: {_format_counts(selection['api_status_counts'])}",
        "",
    ]


def _phase4_8_metric_lines(summary: dict) -> list[str]:
    return [
        "### Phase 4-8",
        "",
        f"- Layout rows: {summary['phase4_layout']['layout_rows']}",
        f"- Layout status: {_format_counts(summary['phase4_layout']['status_counts'])}",
        f"- Layout orientation: {_format_counts(summary['phase4_layout']['orientation_counts'])}",
        f"- Cleanup rows: {summary['phase6_bubble_cleanup']['cleanup_rows']}",
        f"- Cleanup status: {_format_counts(summary['phase6_bubble_cleanup']['status_counts'])}",
        f"- Preview pages: {summary['phase7_page_preview']['page_preview_count']}",
        f"- Preview records: {summary['phase7_page_preview']['preview_record_count']}",
        f"- Photoshop pages: {summary['phase8_photoshop_export']['page_count']}",
        f"- Photoshop editable text layers: {summary['phase8_photoshop_export']['text_layer_count']}",
        f"- Photoshop repaired pages: {summary['phase8_photoshop_export']['repaired_page_count']}",
        "",
    ]


def _report_artifact_lines(artifacts: dict) -> list[str]:
    return ["## 关键文件索引", "", *[f"- {name}: `{value}`" for name, value in artifacts.items()], ""]


def _report_explanation_lines() -> list[str]:
    return [
        "## 解释",
        "",
        "这个 run 已经把“按点位匹配最近检测框 -> 绑定 -> 自动字号/换行布局 -> 视觉模型选字体 -> 框内嵌字”串成可复现路径。"
        "当前框内路线保留可编辑文字层，因此 Photoshop 导出中最终文字仍可人工微调。"
        "框外记录没有进入本次 record_id 列表，后续如果要处理框外，应单独走非气泡/GPT 替换路线并做质量门禁。",
    ]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _mimo_config_from_env() -> MimoVisionConfig:
    required = ["MIMO_BASE_URL", "MIMO_API_KEY", "MIMO_VISION_MODEL"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    return MimoVisionConfig(
        base_url=os.environ["MIMO_BASE_URL"],
        api_key=os.environ["MIMO_API_KEY"],
        model=os.environ["MIMO_VISION_MODEL"],
        max_completion_tokens=1024,
        thinking_type="disabled",
    )


def _timestamp_run_id() -> str:
    return datetime.now().strftime("gbc06-frame-in-comic-full-%Y%m%d-%H%M%S")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unlink_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _counts(values) -> dict[str, int]:
    counts = Counter(str(value) for value in values if value not in (None, ""))
    return dict(sorted(counts.items()))


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"`{key}={value}`" for key, value in counts.items())


def _candidate_font_count(rows: list[dict]) -> int:
    if not rows:
        return 0
    return max(len(row.get("candidate_fonts") or []) for row in rows)


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return round(ordered[index], 3)


if __name__ == "__main__":
    main()
