from __future__ import annotations

import json
from pathlib import Path

from .cleanup_runs import CleanupRunInput, normalize_cleanup_run_dirs
from .phase7 import run_phase7_preview
from .phase7_evaluate import PreviewEvaluationClient, run_phase7_preview_evaluation
from .phase8 import run_phase8_photoshop_export


SCHEMA_VERSION = "autolettering.phase7_8.smoke.v1"


def run_phase7_8_smoke(
    detection_run_dir: str | Path,
    cleanup_run_dirs: CleanupRunInput,
    layout_run_dir: str | Path,
    font_selection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 2,
    evaluation_client: PreviewEvaluationClient | None = None,
    font_mapping_path: str | Path | None = None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase7-8-smoke")
    run_dir.mkdir(parents=True, exist_ok=True)
    cleanup_dirs = normalize_cleanup_run_dirs(cleanup_run_dirs)

    phase7_run = run_phase7_preview(
        detection_run_dir=detection_run_dir,
        cleanup_run_dir=cleanup_dirs,
        layout_run_dir=layout_run_dir,
        output_root=run_dir / "runs",
        run_id="phase7-preview",
        sample_limit=sample_limit,
    )
    evaluation_run = _run_evaluation_if_requested(phase7_run, run_dir, evaluation_client)
    phase8_run = run_phase8_photoshop_export(
        detection_run_dir=detection_run_dir,
        font_selection_run_dir=font_selection_run_dir,
        layout_run_dir=layout_run_dir,
        cleanup_run_dir=cleanup_dirs,
        output_root=run_dir / "runs",
        run_id="phase8-export",
        sample_limit=sample_limit,
        font_mapping_path=font_mapping_path,
        preview_run_dir=phase7_run,
    )

    manifest = _manifest(
        run_dir,
        detection_run_dir,
        cleanup_dirs,
        layout_run_dir,
        font_selection_run_dir,
        phase7_run,
        evaluation_run,
        phase8_run,
        sample_limit,
        font_mapping_path,
    )
    _write_json(run_dir / "manifest.json", manifest)
    _write_report(run_dir / "reports" / "phase7-8-smoke-report.md", manifest)
    return run_dir


def _run_evaluation_if_requested(
    phase7_run: Path,
    run_dir: Path,
    evaluation_client: PreviewEvaluationClient | None,
) -> Path | None:
    if evaluation_client is None:
        return None
    return run_phase7_preview_evaluation(
        preview_run_dir=phase7_run,
        output_root=run_dir / "runs",
        run_id="phase7-evaluation",
        sample_limit=1,
        client=evaluation_client,
    )


def _manifest(
    run_dir: Path,
    detection_run_dir: str | Path,
    cleanup_dirs: list[Path],
    layout_run_dir: str | Path,
    font_selection_run_dir: str | Path,
    phase7_run: Path,
    evaluation_run: Path | None,
    phase8_run: Path,
    sample_limit: int,
    font_mapping_path: str | Path | None,
) -> dict:
    phase7_manifest = _read_json(phase7_run / "manifest.json")
    phase8_manifest = _read_json(phase8_run / "photoshop-manifest.json")
    evaluation = _evaluation_summary(evaluation_run)
    cleanup_summary = _cleanup_summary(phase8_manifest)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "inputs": {
            "detection_run_dir": str(detection_run_dir),
            "cleanup_run_dirs": [str(path) for path in cleanup_dirs],
            "layout_run_dir": str(layout_run_dir),
            "font_selection_run_dir": str(font_selection_run_dir),
            "font_mapping_path": str(font_mapping_path) if font_mapping_path else None,
            "sample_limit": sample_limit,
        },
        "outputs": {
            "phase7_preview_run_dir": str(phase7_run),
            "phase7_evaluation_run_dir": str(evaluation_run) if evaluation_run else None,
            "phase8_export_run_dir": str(phase8_run),
        },
        "summary": {
            "preview_page_count": phase7_manifest["summary"]["page_count"],
            "preview_record_count": phase7_manifest["summary"]["record_count"],
            "skipped_count": phase7_manifest["summary"]["skipped_count"],
            "evaluation_status": evaluation.get("status"),
            "evaluation_score": evaluation.get("score"),
            "evaluation_usable": evaluation.get("usable"),
            "exported_page_count": phase8_manifest["summary"]["page_count"],
            "exported_text_layer_count": phase8_manifest["summary"]["record_count"],
            "missing_cleanup_layers": cleanup_summary["missing_count"],
            "effective_cleanup_methods": cleanup_summary["effective_methods"],
        },
    }


def _evaluation_summary(evaluation_run: Path | None) -> dict:
    if evaluation_run is None:
        return {"status": "not_requested"}
    rows = _read_jsonl(evaluation_run / "preview-evaluation.jsonl")
    if not rows:
        return {"status": "missing"}
    row = rows[0]
    return {"status": row.get("status"), "score": row.get("score"), "usable": row.get("usable")}


def _cleanup_summary(phase8_manifest: dict) -> dict:
    missing_count = 0
    effective_methods: dict[str, int] = {}
    for page in phase8_manifest.get("pages", []):
        for layer in page.get("layers", []):
            cleanup = layer.get("cleanup", {})
            if cleanup.get("status") == "missing":
                missing_count += 1
            method = cleanup.get("effective_method")
            if method:
                effective_methods[method] = effective_methods.get(method, 0) + 1
    return {"missing_count": missing_count, "effective_methods": effective_methods}


def _write_report(output_path: Path, manifest: dict) -> None:
    summary = manifest["summary"]
    lines = [
        "# Phase 7/8 Integrated Smoke Report",
        "",
        "## Inputs",
        "",
        f"- Detection run: `{manifest['inputs']['detection_run_dir']}`",
        f"- Cleanup runs: `{', '.join(manifest['inputs']['cleanup_run_dirs'])}`",
        f"- Layout run: `{manifest['inputs']['layout_run_dir']}`",
        f"- Font selection run: `{manifest['inputs']['font_selection_run_dir']}`",
        f"- Sample limit: {manifest['inputs']['sample_limit']}",
        "",
        "## Summary",
        "",
        f"- Preview pages: {summary['preview_page_count']}",
        f"- Preview records: {summary['preview_record_count']}",
        f"- Skipped records: {summary['skipped_count']}",
        f"- Evaluation status: {summary['evaluation_status']}",
        f"- Evaluation score: {summary['evaluation_score']}",
        f"- Evaluation usable: {summary['evaluation_usable']}",
        f"- Exported pages: {summary['exported_page_count']}",
        f"- Exported text layers: {summary['exported_text_layer_count']}",
        f"- Missing cleanup layers: {summary['missing_cleanup_layers']}",
        f"- Effective cleanup methods: {_format_counts(summary['effective_cleanup_methods'])}",
        "",
        "## Outputs",
        "",
        f"- Phase 7 preview: `{manifest['outputs']['phase7_preview_run_dir']}`",
        f"- Phase 7 evaluation: `{manifest['outputs']['phase7_evaluation_run_dir']}`",
        f"- Phase 8 export: `{manifest['outputs']['phase8_export_run_dir']}`",
        "- `manifest.json`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"`{name}={counts[name]}`" for name in sorted(counts))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
