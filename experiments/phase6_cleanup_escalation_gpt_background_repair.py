from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.gpt_image import GptImageConfig
from autolettering.phase6_cleanup_escalation_gpt_background_repair import (
    run_phase6_cleanup_escalation_gpt_background_repair,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consume Phase 6 cleanup escalation candidates and run GPT image-2 background-only repair."
    )
    parser.add_argument("--gate-run-dir", required=True)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    parser.add_argument("--call-gpt-image", action="store_true")
    parser.add_argument("--mask-dilation-px", type=int, default=6)
    parser.add_argument("--env-file", default=".env")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    _load_env_file(Path(args.env_file))
    run_dir = run_phase6_cleanup_escalation_gpt_background_repair(
        gate_run_dir=Path(args.gate_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        record_ids=args.record_ids,
        gpt_config=_gpt_config_from_env() if args.call_gpt_image else None,
        call_gpt_image=args.call_gpt_image,
        mask_dilation_px=args.mask_dilation_px,
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


def _gpt_config_from_env() -> GptImageConfig:
    required = ["GPT_IMAGE_API_KEY", "GPT_IMAGE_MODEL"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    return GptImageConfig(
        base_url=os.environ.get("GPT_IMAGE_BASE_URL") or None,
        api_key=os.environ["GPT_IMAGE_API_KEY"],
        model=os.environ["GPT_IMAGE_MODEL"],
    )


if __name__ == "__main__":
    main()
