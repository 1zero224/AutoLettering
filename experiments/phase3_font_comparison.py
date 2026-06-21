from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase3 import run_phase3


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 3 font comparison grid generation.")
    parser.add_argument("--labelplus-file", default="GBC06 (已翻 斗笠)/翻译_0.txt")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-smoke")
    parser.add_argument("--font-dir", default="工具箱漫画字体V2.5")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--font-limit", type=int, default=12)
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    args = parser.parse_args()

    run_dir = run_phase3(
        Path(args.labelplus_file),
        detection_run_dir=Path(args.detection_run_dir),
        font_dir=Path(args.font_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        font_limit=args.font_limit,
        record_ids=args.record_ids,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
