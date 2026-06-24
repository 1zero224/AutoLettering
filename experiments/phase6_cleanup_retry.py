from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.phase6_cleanup_retry import DEFAULT_RETRY_METHODS, run_phase6_cleanup_retry


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry failed Phase 6 cleanup records with candidate methods and MIMO quality checks.")
    parser.add_argument("--detection-run-dir", required=True)
    parser.add_argument("--cleanup-quality-run-dir", required=True)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--method", action="append", dest="methods", default=None)
    parser.add_argument("--sample-limit", type=int, default=3)
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))
    run_dir = run_phase6_cleanup_retry(
        detection_run_dir=Path(args.detection_run_dir),
        cleanup_quality_run_dir=Path(args.cleanup_quality_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        methods=args.methods or DEFAULT_RETRY_METHODS,
        sample_limit=args.sample_limit,
        quality_client=MimoVisionClient(_mimo_config_from_env()),
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
        max_completion_tokens=900,
        thinking_type="disabled",
    )


if __name__ == "__main__":
    main()
