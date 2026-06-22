from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase8_export_audit import write_phase8_export_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Phase 8 Photoshop manifest/JSX export quality.")
    parser.add_argument("--phase8-run-dir", required=True)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    run_dir = write_phase8_export_audit(
        phase8_run_dir=Path(args.phase8_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
