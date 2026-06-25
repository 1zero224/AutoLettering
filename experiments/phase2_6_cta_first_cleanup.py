from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.cta_first_pipeline import run_cta_first_cleanup_pipeline
from autolettering.models.gpt_image import GptImageConfig
from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run CTA-first Phase 2/6 cleanup. CTA-first uses BallonsTranslator CTD refined masks first."
    )
    parser.add_argument("--labelplus-file", default="GBC06 (已翻 斗笠)/翻译_0.txt")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    parser.add_argument("--radius-x", type=int, default=220)
    parser.add_argument("--radius-y", type=int, default=180)
    parser.add_argument("--ctd-max-edge-distance-px", type=float, default=20.0)
    parser.add_argument("--call-gpt-image", action="store_true")
    parser.add_argument("--skip-mimo", action="store_true")
    parser.add_argument("--env-file", default=".env")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    _load_env_file(Path(args.env_file))
    run_dir = run_cta_first_cleanup_pipeline(
        labelplus_file=Path(args.labelplus_file),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        record_ids=args.record_ids,
        radius_x=args.radius_x,
        radius_y=args.radius_y,
        ctd_max_edge_distance_px=args.ctd_max_edge_distance_px,
        gpt_config=_gpt_config_from_env() if args.call_gpt_image else None,
        call_gpt_image=args.call_gpt_image,
        mimo_client=None if args.skip_mimo else MimoVisionClient(_mimo_config_from_env()),
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
