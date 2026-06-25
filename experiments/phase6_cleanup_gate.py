from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase6_cleanup_gate import DEFAULT_MIN_USABLE_SCORE, run_phase6_cleanup_gate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create GPT escalation candidates from failed CTA/LaMA Phase 6 cleanup quality rows."
    )
    parser.add_argument("--cleanup-run-dir", required=True)
    parser.add_argument("--cleanup-quality-run-dir", required=True)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    parser.add_argument("--min-usable-score", type=int, default=DEFAULT_MIN_USABLE_SCORE)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_dir = run_phase6_cleanup_gate(
        cleanup_run_dir=Path(args.cleanup_run_dir),
        cleanup_quality_run_dir=Path(args.cleanup_quality_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        record_ids=args.record_ids,
        min_usable_score=args.min_usable_score,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
