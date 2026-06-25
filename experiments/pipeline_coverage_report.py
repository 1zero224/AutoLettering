from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.pipeline_coverage import write_pipeline_coverage_report
from autolettering.pipeline_registry import PipelineRegistryValidationError, load_pipeline_registry_entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a cross-phase pipeline coverage and gap report.")
    parser.add_argument("--registry-file", default=None, help="Optional JSON registry of accepted pipeline run directories.")
    parser.add_argument("--registry-entry", default=None, help="Entry name inside --registry-file.")
    parser.add_argument("--phase1-run-dir", default=None)
    parser.add_argument("--detection-run-dir", action="append", default=None)
    parser.add_argument("--font-selection-run-dir", action="append", default=None)
    parser.add_argument("--layout-run-dir", action="append", default=None)
    parser.add_argument("--angle-run-dir", action="append", default=None)
    parser.add_argument("--cleanup-run-dir", action="append", default=None)
    parser.add_argument("--preview-run-dir", action="append", default=None)
    parser.add_argument("--export-run-dir", action="append", default=None)
    parser.add_argument("--phase6-cleanup-quality-run-dir", action="append", default=None)
    parser.add_argument("--phase6-gpt-quality-run-dir", action="append", default=None)
    parser.add_argument("--phase7-preview-evaluation-run-dir", action="append", default=None)
    parser.add_argument("--phase8-export-audit-run-dir", action="append", default=None)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--next-limit", type=int, default=None)
    args = parser.parse_args()

    kwargs = _coverage_kwargs(args)
    registry_run_id = kwargs.pop("run_id", None)
    run_dir = write_pipeline_coverage_report(
        output_root=Path(args.output_root),
        run_id=args.run_id or registry_run_id,
        **kwargs,
    )
    print(run_dir)


def _coverage_kwargs(args: argparse.Namespace) -> dict:
    if args.registry_file or args.registry_entry:
        if not args.registry_file or not args.registry_entry:
            raise SystemExit("--registry-file and --registry-entry must be passed together")
        try:
            entry = load_pipeline_registry_entry(args.registry_file, args.registry_entry, validate=True)
        except PipelineRegistryValidationError as exc:
            raise SystemExit(str(exc)) from exc
        entry.pop("schema_version", None)
        if args.next_limit is not None:
            entry["next_limit"] = args.next_limit
        return entry
    return {
        "phase1_run_dir": _optional_path(args.phase1_run_dir),
        "detection_run_dir": _optional_paths(args.detection_run_dir),
        "font_selection_run_dir": _optional_paths(args.font_selection_run_dir),
        "layout_run_dir": _optional_paths(args.layout_run_dir),
        "angle_run_dir": _optional_paths(args.angle_run_dir),
        "cleanup_run_dirs": [Path(value) for value in args.cleanup_run_dir or []],
        "preview_run_dir": _optional_paths(args.preview_run_dir),
        "export_run_dir": _optional_paths(args.export_run_dir),
        "phase6_cleanup_quality_run_dir": _optional_paths(args.phase6_cleanup_quality_run_dir),
        "phase6_gpt_quality_run_dir": _optional_paths(args.phase6_gpt_quality_run_dir),
        "phase7_preview_evaluation_run_dir": _optional_paths(args.phase7_preview_evaluation_run_dir),
        "phase8_export_audit_run_dir": _optional_paths(args.phase8_export_audit_run_dir),
        "next_limit": args.next_limit or 10,
    }


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def _optional_paths(values: list[str] | None) -> list[Path]:
    return [Path(value) for value in values or []]


if __name__ == "__main__":
    main()
