from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase5 import run_phase5_orientation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 5 orientation and angle estimation.")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-smoke")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    args = parser.parse_args()

    run_dir = run_phase5_orientation(
        detection_run_dir=Path(args.detection_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        record_ids=args.record_ids,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
