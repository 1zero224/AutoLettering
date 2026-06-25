from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase2_threshold_sweep import run_phase2_threshold_sweep


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep CTA/CTD mask edge-distance thresholds from an existing Phase 2 run.")
    parser.add_argument("--phase2-run-dir", required=True, help="Existing Phase 2 run directory with CTD distance artifacts.")
    parser.add_argument("--output-root", default="outputs/runs", help="Directory for threshold sweep outputs.")
    parser.add_argument("--run-id", default=None, help="Optional deterministic run id.")
    parser.add_argument(
        "--threshold",
        action="append",
        type=float,
        dest="thresholds",
        help="Threshold in pixels; repeatable. Defaults to 20/40/60/80.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_dir = run_phase2_threshold_sweep(
        phase2_run_dir=Path(args.phase2_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        thresholds=args.thresholds,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
