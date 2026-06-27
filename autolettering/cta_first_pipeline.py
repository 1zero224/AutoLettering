from __future__ import annotations

import json
from pathlib import Path

from .models.gpt_image import GptImageConfig
from .models.mimo import MimoVisionClient
from .phase2 import run_phase2
from .phase6_nonbubble import run_phase6_nonbubble_cleanup
from .phase6_replacement_quality_gate import (
    MISSING_QUALITY_REASON,
    QUALITY_REJECTION_REASON,
    RunDirInput,
    gpt_replacement_quality_gate,
    load_replacement_quality_by_id,
)


CTA_FIRST_SCHEMA_VERSION = "autolettering.cta_first_pipeline.v1"


def run_cta_first_cleanup_pipeline(
    labelplus_file: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    radius_x: int = 220,
    radius_y: int = 180,
    ctd_max_edge_distance_px: float = 30.0,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
    mimo_client: MimoVisionClient | None = None,
    phase6_gpt_quality_run_dir: RunDirInput = None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase2-6-cta-first-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    nested_root = run_dir / "runs"
    phase2_run = run_phase2(
        labelplus_file=Path(labelplus_file),
        output_root=nested_root,
        run_id="phase2-cta-mask",
        sample_limit=sample_limit,
        radius_x=radius_x,
        radius_y=radius_y,
        record_ids=record_ids,
        detection_strategy="cta_mask",
        ctd_max_edge_distance_px=ctd_max_edge_distance_px,
    )
    phase6_run = run_phase6_nonbubble_cleanup(
        detection_run_dir=phase2_run,
        output_root=nested_root,
        run_id="phase6-cta-first-cleanup",
        sample_limit=sample_limit,
        record_ids=record_ids,
        gpt_config=gpt_config,
        call_gpt_image=call_gpt_image,
        inpaint_method="bt_lama_large",
        mimo_client=mimo_client,
    )
    detections = _load_jsonl(phase2_run / "detections.jsonl")
    cleanups = _load_jsonl(phase6_run / "cleanup-results.jsonl")
    replacement_quality = (
        load_replacement_quality_by_id(phase6_gpt_quality_run_dir)
        if phase6_gpt_quality_run_dir is not None
        else None
    )
    manifest = _manifest(
        labelplus_file,
        phase2_run,
        phase6_run,
        detections,
        cleanups,
        phase6_gpt_quality_run_dir=phase6_gpt_quality_run_dir,
        replacement_quality_by_id=replacement_quality,
    )
    _write_json(run_dir / "manifest.json", manifest)
    _write_report(run_dir / "reports" / "cta-first-pipeline-report.md", manifest)
    return run_dir


def _manifest(
    labelplus_file: str | Path,
    phase2_run: Path,
    phase6_run: Path,
    detections: list[dict],
    cleanups: list[dict],
    phase6_gpt_quality_run_dir: RunDirInput = None,
    replacement_quality_by_id: dict[str, dict] | None = None,
) -> dict:
    return {
        "schema_version": CTA_FIRST_SCHEMA_VERSION,
        "labelplus_file": str(labelplus_file),
        "phase2_detection_run_dir": str(phase2_run),
        "phase6_cleanup_run_dir": str(phase6_run),
        "phase6_gpt_quality_run_dir": _serialize_run_dir(phase6_gpt_quality_run_dir),
        "text_detection_plan": _text_detection_plan(),
        "cleanup_plan": _cleanup_plan(),
        "photoshop_export_contract": _photoshop_export_contract(),
        "review_image_contract": _review_image_contract(),
        "summary": _summary(detections, cleanups, replacement_quality_by_id),
        "routes": [
            {
                "name": "cta_mask_lama_large_512px",
                "description": "Matched CTD refined-mask component -> lama_large_512px cleanup -> editable lettering layer",
                "record_ids": [
                    row["record_id"]
                    for row in detections
                    if row.get("status") == "ok" and (row.get("cta_match") or {}).get("status") == "matched"
                ],
            },
            {
                "name": "mimo_locator_gpt_image2_masked_edit",
                "description": "Unmatched LabelPlus point -> near-square MIMO locator crop -> gpt-image-2 transparent masked replacement only when the real edit call and optional replacement-quality gate succeed",
                "completion_condition": (
                    "cleanup.status=cleaned and gpt_image2_edit.status=ok and cleanup.replacement_crop_path exists "
                    "and replacement-quality.jsonl accepts the same record when a quality run is supplied"
                ),
                "record_ids": [row["record_id"] for row in detections if row.get("status") == "fallback_required"],
            },
        ],
    }


def _text_detection_plan() -> dict:
    return {
        "user_requested_strategy": "cta",
        "project_strategy": "cta_mask",
        "ballonstranslator_detector_module": "ctd",
        "ballonstranslator_detector_class": "ComicTextDetector",
        "ballonstranslator_config_path": "BallonsTranslator/config/config.json",
        "ballonstranslator_config_key": "module.textdetector_params.ctd",
        "mask_artifact": "debug/ctd_masks/<page>/ctd-refined-mask.png",
        "component_manifest": "debug/ctd_masks/<page>/cta-closed-mask-components.json",
        "distance_artifact": "debug/ctd_masks/<page>/ctd-mask-edge-distances.jsonl",
        "componentization": "connected_components_over_refined_mask",
        "matching_metric": "labelplus_point_to_mask_edge",
        "matching_cardinality": "unique_mask_component_claim",
        "fallback_trigger": "no_unique_ctd_mask_match_within_threshold",
    }


def _cleanup_plan() -> dict:
    return {
        "matched_ctd_mask": {
            "text_region_source": "ctd_refined_mask_component",
            "inpaint_method": "lama_large_512px",
            "lettering": "programmatic_editable_text_layer",
        },
        "unmatched_labelplus_point": {
            "context_crop": "near_square_labelplus_context_crop",
            "locator": "mimo_vision_model_returns_crop_local_bbox",
            "replacement": "gpt-image-2_transparent_masked_edit",
            "lettering": "gpt-image-2_direct_replacement_when_call_and_optional_quality_gate_succeed",
        },
    }


def _photoshop_export_contract() -> dict:
    return {
        "project_manifest": "photoshop-manifest.json",
        "import_script": "photoshop-import.jsx",
        "layer_order_top_to_bottom": ["嵌字图层1", "嵌字图层2", "...", "修复图像", "原图"],
        "repaired_image_source": "page-level image synthesized from lama_large_512px cleanup crops plus quality-accepted gpt-image-2 replacement crops",
    }


def _review_image_contract() -> dict:
    return {
        "font_and_effect_grids": "use near_square_columns instead of long strips",
        "fallback_locator_grid": "visuals/fallback-locator-grid.png",
        "mimo_review_policy": "readable near-square contact sheets",
    }


def _summary(detections: list[dict], cleanups: list[dict], replacement_quality_by_id: dict[str, dict] | None = None) -> dict:
    return {
        "detected_records": len(detections),
        "cleanup_records": len(cleanups),
        "matched_cta_records": sum(
            1 for row in detections if row.get("status") == "ok" and (row.get("cta_match") or {}).get("status") == "matched"
        ),
        "matched_ctd_records": sum(
            1 for row in detections if row.get("status") == "ok" and (row.get("ctd_match") or {}).get("status") == "matched"
        ),
        "fallback_required_records": sum(1 for row in detections if row.get("status") == "fallback_required"),
        "lama_large_cleanup_records": sum(
            1 for row in cleanups if "lama_large" in str((row.get("cleanup") or {}).get("method", ""))
        ),
        "gpt_image2_replacement_records": sum(
            1
            for row in cleanups
            if _has_completed_gpt_image2_replacement(row, replacement_quality_by_id)
        ),
        "gpt_image2_pending_or_failed_records": sum(
            1
            for row in cleanups
            if (row.get("cleanup") or {}).get("method") == "gpt_image2_masked_edit"
            and not _has_completed_gpt_image2_replacement(row, replacement_quality_by_id)
        ),
        "gpt_image2_quality_rejected_records": sum(
            1
            for row in cleanups
            if _gpt_replacement_quality_failure_reason(row, replacement_quality_by_id) == QUALITY_REJECTION_REASON
        ),
        "gpt_image2_quality_missing_records": sum(
            1
            for row in cleanups
            if _gpt_replacement_quality_failure_reason(row, replacement_quality_by_id) == MISSING_QUALITY_REASON
        ),
        "text_overlay_required_records": sum(
            1 for row in cleanups if (row.get("cleanup") or {}).get("text_overlay_required") is True
        ),
    }


def _has_completed_gpt_image2_replacement(row: dict, replacement_quality_by_id: dict[str, dict] | None = None) -> bool:
    cleanup = row.get("cleanup") or {}
    api_completed = (
        row.get("status") == "cleaned"
        and cleanup.get("replacement_method") == "gpt_image2_masked_edit"
        and bool(cleanup.get("replacement_crop_path"))
        and (row.get("gpt_image2_edit") or {}).get("status") == "ok"
    )
    if not api_completed:
        return False
    return bool(gpt_replacement_quality_gate(row.get("record_id"), cleanup, replacement_quality_by_id).get("accepted"))


def _gpt_replacement_quality_failure_reason(row: dict, replacement_quality_by_id: dict[str, dict] | None = None) -> str | None:
    if replacement_quality_by_id is None or not _has_gpt_replacement_artifact(row):
        return None
    gate = gpt_replacement_quality_gate(row.get("record_id"), row.get("cleanup") or {}, replacement_quality_by_id)
    return gate.get("failure_reason")


def _has_gpt_replacement_artifact(row: dict) -> bool:
    cleanup = row.get("cleanup") or {}
    return (
        cleanup.get("replacement_method") == "gpt_image2_masked_edit"
        and bool(cleanup.get("replacement_crop_path"))
        and (row.get("gpt_image2_edit") or {}).get("status") == "ok"
    )


def _serialize_run_dir(run_dir: RunDirInput) -> str | list[str] | None:
    if run_dir is None:
        return None
    if isinstance(run_dir, (str, Path)):
        return str(run_dir)
    return [str(item) for item in run_dir]


def _write_report(path: Path, manifest: dict) -> None:
    lines = [
        "# CTA-first Phase 2-6 Pipeline Report",
        "",
        f"LabelPlus file: `{manifest['labelplus_file']}`",
        f"Phase 2 detection run: `{manifest['phase2_detection_run_dir']}`",
        f"Phase 6 cleanup run: `{manifest['phase6_cleanup_run_dir']}`",
        "",
        "## Strategy Contract",
        "",
        "- BallonsTranslator detector: `ctd` / `ComicTextDetector`",
        "- CTA-first means CTD refined-mask connected components first, then unique LabelPlus point-to-mask-edge matching.",
        "- `cta_mask` is the project-facing strategy name; it is not a separate BallonsTranslator detector module.",
        "- Each page records closed mask components in `cta-closed-mask-components.json` and all LabelPlus point-to-mask-edge distances in `ctd-mask-edge-distances.jsonl`.",
        "",
        "## Routes",
        "",
        "- Matched CTD mask -> `lama_large_512px` cleanup -> editable lettering layer",
        "- Unmatched LabelPlus point -> near-square MIMO locator crop -> `gpt-image-2` transparent masked replacement when the real edit call succeeds and any supplied `replacement-quality.jsonl` accepts the record; dry-runs, quality misses, and quality rejects stay pending and still need a text layer",
        "",
        "## Photoshop Export Contract",
        "",
        "- `photoshop-import.jsx` reads `photoshop-manifest.json`, not the LabelPlus txt directly.",
        "- PSD layer order is editable `嵌字图层1`, `嵌字图层2`, ... above `修复图像`, above `原图`.",
        "",
        "## Review Image Contract",
        "",
        "- Font comparison and effect review sheets should use near-square grids instead of long strips.",
        "- Fallback locator evidence is collected in `visuals/fallback-locator-grid.png`.",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in manifest["summary"].items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
