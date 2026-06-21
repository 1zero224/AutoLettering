from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.pipeline_coverage import write_pipeline_coverage_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a cross-phase pipeline coverage and gap report.")
    parser.add_argument("--phase1-run-dir", default=None)
    parser.add_argument("--detection-run-dir", default=None)
    parser.add_argument("--font-selection-run-dir", default=None)
    parser.add_argument("--layout-run-dir", default=None)
    parser.add_argument("--angle-run-dir", default=None)
    parser.add_argument("--cleanup-run-dir", action="append", default=None)
    parser.add_argument("--preview-run-dir", default=None)
    parser.add_argument("--export-run-dir", default=None)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--next-limit", type=int, default=10)
    args = parser.parse_args()

    run_dir = write_pipeline_coverage_report(
        output_root=Path(args.output_root),
        run_id=args.run_id,
        phase1_run_dir=_optional_path(args.phase1_run_dir),
        detection_run_dir=_optional_path(args.detection_run_dir),
        font_selection_run_dir=_optional_path(args.font_selection_run_dir),
        layout_run_dir=_optional_path(args.layout_run_dir),
        angle_run_dir=_optional_path(args.angle_run_dir),
        cleanup_run_dirs=[Path(value) for value in args.cleanup_run_dir or []],
        preview_run_dir=_optional_path(args.preview_run_dir),
        export_run_dir=_optional_path(args.export_run_dir),
        next_limit=args.next_limit,
    )
    print(run_dir)


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


if __name__ == "__main__":
    main()
