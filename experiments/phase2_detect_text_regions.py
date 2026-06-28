from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase2 import run_phase2
from autolettering.detection.comic_text_bubble import DEFAULT_COMIC_DETECTOR_MODEL_PATH
from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 2 text-region detection prototype.")
    parser.add_argument(
        "--labelplus-file",
        default="GBC06 (已翻 斗笠)/翻译_0.txt",
        help="Path to the LabelPlus translation text file.",
    )
    parser.add_argument("--output-root", default="outputs/runs", help="Directory for run outputs.")
    parser.add_argument("--run-id", default=None, help="Optional deterministic run directory name.")
    parser.add_argument("--sample-limit", type=int, default=30, help="Maximum records to detect.")
    parser.add_argument("--record-id", action="append", dest="record_ids", help="Record id to detect; repeatable.")
    parser.add_argument("--radius-x", type=int, default=220, help="Horizontal search radius in pixels.")
    parser.add_argument("--radius-y", type=int, default=180, help="Vertical search radius in pixels.")
    parser.add_argument(
        "--detection-strategy",
        default="cta_mask",
        choices=["cta_mask", "ctd_mask", "cv", "comic_rtdetrv2", "comic_text_bubble_rtdetrv2"],
        help="Detection strategy: BallonsTranslator CTA/CTD masks, comic RT-DETRv2, or the old local CV prototype.",
    )
    parser.add_argument(
        "--ctd-max-edge-distance-px",
        type=float,
        default=30.0,
        help="Maximum LabelPlus-point to CTD component edge distance for unique matching.",
    )
    parser.add_argument(
        "--call-mimo-recognition",
        action="store_true",
        help="Directly call MIMO vision to recognize the source text region for each Phase 2 record.",
    )
    parser.add_argument(
        "--comic-detector-model-path",
        default=str(DEFAULT_COMIC_DETECTOR_MODEL_PATH),
        help="Path to the comic text/bubble RT-DETRv2 ONNX model.",
    )
    parser.add_argument(
        "--comic-detector-conf-threshold",
        type=_comic_conf_threshold_arg,
        default=0.5,
        help="Confidence threshold for comic text/bubble RT-DETRv2 detections.",
    )
    parser.add_argument(
        "--comic-detector-max-distance-px",
        type=_nonnegative_float_arg,
        default=120.0,
        help="Maximum LabelPlus-point distance to a text_bubble/text_free detection.",
    )
    parser.add_argument("--env-file", default=".env", help="Load API environment variables from this file.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    _load_env_file(Path(args.env_file))

    run_dir = run_phase2(
        Path(args.labelplus_file),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        radius_x=args.radius_x,
        radius_y=args.radius_y,
        record_ids=args.record_ids,
        detection_strategy=args.detection_strategy,
        ctd_max_edge_distance_px=args.ctd_max_edge_distance_px,
        call_model_text_recognition=args.call_mimo_recognition,
        model_text_recognition_client=MimoVisionClient(_mimo_config_from_env())
        if args.call_mimo_recognition
        else None,
        comic_detector_model_path=Path(args.comic_detector_model_path),
        comic_detector_conf_threshold=args.comic_detector_conf_threshold,
        comic_detector_max_distance_px=args.comic_detector_max_distance_px,
    )
    print(run_dir)


def _finite_float_arg(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a finite number") from exc
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be a finite number")
    return parsed


def _comic_conf_threshold_arg(value: str) -> float:
    parsed = _finite_float_arg(value)
    if parsed < 0.0 or parsed > 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def _nonnegative_float_arg(value: str) -> float:
    parsed = _finite_float_arg(value)
    if parsed < 0.0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


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
