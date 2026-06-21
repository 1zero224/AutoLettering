from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase4 import run_phase4


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 4 deterministic layout search.")
    parser.add_argument("--selection-run-dir", default="outputs/runs/phase3-gbc06-mimo-font-smoke")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=5)
    args = parser.parse_args()

    run_dir = run_phase4(
        selection_run_dir=Path(args.selection_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
