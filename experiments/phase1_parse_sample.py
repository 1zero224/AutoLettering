from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase1 import run_phase1


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a LabelPlus project and generate Phase 1 artifacts.")
    parser.add_argument(
        "--labelplus-file",
        default="GBC06 (已翻 斗笠)/翻译_0.txt",
        help="Path to the LabelPlus translation text file.",
    )
    parser.add_argument(
        "--output-root",
        default="outputs/runs",
        help="Directory where timestamped run outputs are written.",
    )
    parser.add_argument("--run-id", default=None, help="Optional deterministic run directory name.")
    parser.add_argument("--sample-limit", type=int, default=30, help="Maximum records in phase1 sample JSONL.")
    args = parser.parse_args()

    run_dir = run_phase1(
        Path(args.labelplus_file),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
