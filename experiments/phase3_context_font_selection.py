from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.phase3_context_font_selection import run_phase3_context_font_selection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run context-aware MIMO font selection on repaired preview crops.")
    parser.add_argument("--font-comparison-run-dir", required=True)
    parser.add_argument("--layout-run-dir", required=True)
    parser.add_argument("--cleanup-run-dir", required=True)
    parser.add_argument("--font-dir", default=None)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=1)
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    parser.add_argument("--candidate-limit", type=int, default=16)
    parser.add_argument("--call-mimo", action="store_true")
    parser.add_argument("--env-file", default=".env")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    _load_env_file(Path(args.env_file))
    run_dir = run_phase3_context_font_selection(
        font_comparison_run_dir=Path(args.font_comparison_run_dir),
        layout_run_dir=Path(args.layout_run_dir),
        cleanup_run_dir=Path(args.cleanup_run_dir),
        font_dir=Path(args.font_dir) if args.font_dir else None,
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        record_ids=args.record_ids,
        candidate_limit=args.candidate_limit,
        client=MimoVisionClient(_mimo_config_from_env()) if args.call_mimo else None,
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
