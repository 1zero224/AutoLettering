from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase7_compare import PreviewMethodInput, run_phase7_method_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Phase 7 page-preview method comparison package.")
    parser.add_argument("--method", action="append", required=True, help="Method spec as label=preview_run_dir.")
    parser.add_argument("--evaluation", action="append", default=[], help="Optional eval spec as label=evaluation_run_dir.")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    evaluations = dict(_parse_spec(value) for value in args.evaluation)
    methods = [
        PreviewMethodInput(label=label, preview_run_dir=Path(run_dir), evaluation_run_dir=evaluations.get(label))
        for label, run_dir in (_parse_spec(value) for value in args.method)
    ]
    run_dir = run_phase7_method_comparison(methods, output_root=Path(args.output_root), run_id=args.run_id)
    print(run_dir)


def _parse_spec(value: str) -> tuple[str, Path]:
    if "=" not in value:
        path = Path(value)
        return path.name, path
    label, path = value.split("=", 1)
    label = label.strip()
    if not label:
        raise SystemExit(f"Invalid empty label in spec: {value}")
    return label, Path(path.strip())


if __name__ == "__main__":
    main()
