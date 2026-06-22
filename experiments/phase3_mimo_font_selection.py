from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.phase3_vision import run_phase3_vision_selection


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled MIMO vision font selection.")
    parser.add_argument("--input-run-dir", default="outputs/runs/phase3-gbc06-font-smoke")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=1)
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))
    client = MimoVisionClient(_mimo_config_from_env())
    run_dir = run_phase3_vision_selection(
        input_run_dir=Path(args.input_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        client=client,
        record_ids=args.record_ids,
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
        max_completion_tokens=1024,
        thinking_type="disabled",
    )


if __name__ == "__main__":
    main()
