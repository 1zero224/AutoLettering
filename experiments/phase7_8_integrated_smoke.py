from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.phase7_8_smoke import run_phase7_8_smoke


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run integrated Phase 7 preview, MIMO evaluation, and Phase 8 export.")
    parser.add_argument("--detection-run-dir", required=True)
    parser.add_argument("--cleanup-run-dir", action="append", required=True)
    parser.add_argument("--layout-run-dir", required=True)
    parser.add_argument("--font-selection-run-dir", required=True)
    parser.add_argument("--phase6-gpt-quality-run-dir", action="append", default=None)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=2)
    parser.add_argument("--font-mapping", default=None)
    parser.add_argument("--skip-mimo-evaluation", action="store_true")
    parser.add_argument("--env-file", default=".env")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    _load_env_file(Path(args.env_file))
    client = None if args.skip_mimo_evaluation else MimoVisionClient(_mimo_config_from_env())
    run_dir = run_phase7_8_smoke(
        detection_run_dir=Path(args.detection_run_dir),
        cleanup_run_dirs=[Path(value) for value in args.cleanup_run_dir],
        layout_run_dir=Path(args.layout_run_dir),
        font_selection_run_dir=Path(args.font_selection_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        evaluation_client=client,
        font_mapping_path=Path(args.font_mapping) if args.font_mapping else None,
        phase6_gpt_quality_run_dir=[Path(value) for value in args.phase6_gpt_quality_run_dir]
        if args.phase6_gpt_quality_run_dir
        else None,
    )
    print(run_dir)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _mimo_config_from_env() -> MimoVisionConfig:
    required = ["MIMO_BASE_URL", "MIMO_API_KEY", "MIMO_VISION_MODEL"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    return MimoVisionConfig(
        base_url=os.environ["MIMO_BASE_URL"],
        api_key=os.environ["MIMO_API_KEY"],
        model=os.environ["MIMO_VISION_MODEL"],
        thinking_type="disabled",
    )


if __name__ == "__main__":
    main()
