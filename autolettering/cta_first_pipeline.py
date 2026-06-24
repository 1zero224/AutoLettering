from __future__ import annotations

import json
from pathlib import Path

from .models.gpt_image import GptImageConfig
from .models.mimo import MimoVisionClient
from .phase2 import run_phase2
from .phase6_nonbubble import run_phase6_nonbubble_cleanup


CTA_FIRST_SCHEMA_VERSION = "autolettering.cta_first_pipeline.v1"


def run_cta_first_cleanup_pipeline(
    labelplus_file: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    radius_x: int = 220,
    radius_y: int = 180,
    ctd_max_edge_distance_px: float = 20.0,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
    mimo_client: MimoVisionClient | None = None,
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
    manifest = _manifest(labelplus_file, phase2_run, phase6_run, detections, cleanups)
    _write_json(run_dir / "manifest.json", manifest)
    _write_report(run_dir / "reports" / "cta-first-pipeline-report.md", manifest)
    return run_dir


def _manifest(
    labelplus_file: str | Path,
    phase2_run: Path,
    phase6_run: Path,
    detections: list[dict],
    cleanups: list[dict],
) -> dict:
    return {
        "schema_version": CTA_FIRST_SCHEMA_VERSION,
        "labelplus_file": str(labelplus_file),
        "phase2_detection_run_dir": str(phase2_run),
        "phase6_cleanup_run_dir": str(phase6_run),
        "summary": _summary(detections, cleanups),
        "routes": [
            {
                "name": "cta_mask_lama_large_512px",
                "description": "CTA mask matched -> lama_large_512px cleanup -> editable lettering layer",
                "record_ids": [
                    row["record_id"]
                    for row in detections
                    if row.get("status") == "ok" and (row.get("cta_match") or {}).get("status") == "matched"
                ],
            },
            {
                "name": "mimo_locator_gpt_image2_masked_edit",
                "description": "CTA unmatched -> MIMO locator -> gpt-image-2 masked replacement only when the real edit call succeeds",
                "completion_condition": "cleanup.status=cleaned and gpt_image2_edit.status=ok and cleanup.replacement_crop_path exists",
                "record_ids": [row["record_id"] for row in detections if row.get("status") == "fallback_required"],
            },
        ],
    }


def _summary(detections: list[dict], cleanups: list[dict]) -> dict:
    return {
        "detected_records": len(detections),
        "cleanup_records": len(cleanups),
        "matched_cta_records": sum(
            1 for row in detections if row.get("status") == "ok" and (row.get("cta_match") or {}).get("status") == "matched"
        ),
        "fallback_required_records": sum(1 for row in detections if row.get("status") == "fallback_required"),
        "lama_large_cleanup_records": sum(
            1 for row in cleanups if "lama_large" in str((row.get("cleanup") or {}).get("method", ""))
        ),
        "gpt_image2_replacement_records": sum(
            1
            for row in cleanups
            if _has_completed_gpt_image2_replacement(row)
        ),
        "gpt_image2_pending_or_failed_records": sum(
            1
            for row in cleanups
            if (row.get("cleanup") or {}).get("method") == "gpt_image2_masked_edit"
            and not _has_completed_gpt_image2_replacement(row)
        ),
        "text_overlay_required_records": sum(
            1 for row in cleanups if (row.get("cleanup") or {}).get("text_overlay_required") is True
        ),
    }


def _has_completed_gpt_image2_replacement(row: dict) -> bool:
    cleanup = row.get("cleanup") or {}
    return (
        row.get("status") == "cleaned"
        and cleanup.get("replacement_method") == "gpt_image2_masked_edit"
        and bool(cleanup.get("replacement_crop_path"))
        and (row.get("gpt_image2_edit") or {}).get("status") == "ok"
    )


def _write_report(path: Path, manifest: dict) -> None:
    lines = [
        "# CTA-first Phase 2-6 Pipeline Report",
        "",
        f"LabelPlus file: `{manifest['labelplus_file']}`",
        f"Phase 2 detection run: `{manifest['phase2_detection_run_dir']}`",
        f"Phase 6 cleanup run: `{manifest['phase6_cleanup_run_dir']}`",
        "",
        "## Routes",
        "",
        "- CTA mask matched -> `lama_large_512px` cleanup -> editable lettering layer",
        "- CTA unmatched -> MIMO locator -> `gpt-image-2` masked replacement when the real edit call succeeds; dry-runs and failures stay pending and still need a text layer",
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
