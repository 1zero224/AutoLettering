from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase2 import run_phase2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 2 text-region detection prototype.")
    parser.add_argument(
        "--labelplus-file",
        default="GBC06 (已翻 斗笠)/翻译_0.txt",
        help="Path to the LabelPlus translation text file.",
    )
    parser.add_argument("--output-root", default="outputs/runs", help="Directory for run outputs.")
    parser.add_argument("--run-id", default=None, help="Optional deterministic run directory name.")
    parser.add_argument("--sample-limit", type=int, default=30, help="Maximum records to detect.")
    parser.add_argument("--record-id", action="append", dest="record_ids", help="Record id to detect; repeatable.")
    parser.add_argument("--radius-x", type=int, default=220, help="Horizontal search radius in pixels.")
    parser.add_argument("--radius-y", type=int, default=180, help="Vertical search radius in pixels.")
    parser.add_argument(
        "--detection-strategy",
        default="cta_mask",
        choices=["cta_mask", "ctd_mask", "cv"],
        help="Detection strategy: BallonsTranslator CTA/CTD mask matching or the old local CV prototype.",
    )
    parser.add_argument(
        "--ctd-max-edge-distance-px",
        type=float,
        default=30.0,
        help="Maximum LabelPlus-point to CTD component edge distance for unique matching.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    run_dir = run_phase2(
        Path(args.labelplus_file),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        radius_x=args.radius_x,
        radius_y=args.radius_y,
        record_ids=args.record_ids,
        detection_strategy=args.detection_strategy,
        ctd_max_edge_distance_px=args.ctd_max_edge_distance_px,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
