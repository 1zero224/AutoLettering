from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.phase7_compare import PreviewMethodInput, run_phase7_method_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Phase 7 page-preview method comparison package.")
    parser.add_argument("--method", action="append", required=True, help="Method spec as label=preview_run_dir.")
    parser.add_argument("--evaluation", action="append", default=[], help="Optional eval spec as label=evaluation_run_dir.")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--crop-mode", choices=["text", "record"], default="text")
    parser.add_argument("--mimo", action="store_true", help="Submit the near-square result grid to MIMO vision.")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))
    evaluations = dict(_parse_spec(value) for value in args.evaluation)
    methods = [
        PreviewMethodInput(label=label, preview_run_dir=Path(run_dir), evaluation_run_dir=evaluations.get(label))
        for label, run_dir in (_parse_spec(value) for value in args.method)
    ]
    client = MimoVisionClient(_mimo_config_from_env()) if args.mimo else None
    run_dir = run_phase7_method_comparison(
        methods,
        output_root=Path(args.output_root),
        run_id=args.run_id,
        client=client,
        crop_mode=args.crop_mode,
    )
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
        max_completion_tokens=1200,
    )


if __name__ == "__main__":
    main()
