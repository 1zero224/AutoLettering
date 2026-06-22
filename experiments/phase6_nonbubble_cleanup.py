from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.gpt_image import GptImageConfig
from autolettering.phase6_nonbubble import run_phase6_nonbubble_cleanup


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6 non-bubble cleanup with local inpaint and GPT mask package.")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-smoke")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=1)
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--call-gpt-image", action="store_true")
    parser.add_argument(
        "--inpaint-method",
        default="bt_lama_large",
        choices=[
            "local_diffusion",
            "flat_median_fill",
            "opencv_telea",
            "opencv_ns",
            "dark_panel_fill",
            "bt_lama_large",
            "bt_patchmatch",
        ],
    )
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))
    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=Path(args.detection_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        record_ids=args.record_ids,
        gpt_config=_gpt_config_from_env() if args.call_gpt_image else None,
        call_gpt_image=args.call_gpt_image,
        inpaint_method=args.inpaint_method,
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
