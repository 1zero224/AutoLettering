from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase8 import run_phase8_photoshop_export


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 8 Photoshop JSON/JSX export.")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-smoke")
    parser.add_argument("--font-selection-run-dir", default="outputs/runs/phase3-gbc06-mimo-font-smoke")
    parser.add_argument("--layout-run-dir", default="outputs/runs/phase4-gbc06-angle-layout-smoke")
    parser.add_argument("--cleanup-run-dir", action="append", default=None)
    parser.add_argument("--preview-run-dir", default=None)
    parser.add_argument("--phase6-gpt-quality-run-dir", action="append", default=None)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--font-mapping", default=None)
    args = parser.parse_args()
    cleanup_run_dirs = args.cleanup_run_dir or ["outputs/runs/phase6-gbc06-bubble-smoke"]

    run_dir = run_phase8_photoshop_export(
        detection_run_dir=Path(args.detection_run_dir),
        font_selection_run_dir=Path(args.font_selection_run_dir),
        layout_run_dir=Path(args.layout_run_dir),
        cleanup_run_dir=[Path(value) for value in cleanup_run_dirs],
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        font_mapping_path=Path(args.font_mapping) if args.font_mapping else None,
        preview_run_dir=Path(args.preview_run_dir) if args.preview_run_dir else None,
        phase6_gpt_quality_run_dir=[Path(value) for value in args.phase6_gpt_quality_run_dir]
        if args.phase6_gpt_quality_run_dir
        else None,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
