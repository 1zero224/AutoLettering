from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase6 import run_phase6_bubble_cleanup


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6 deterministic bubble text cleanup.")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-smoke")
    parser.add_argument("--layout-run-dir", default="outputs/runs/phase4-gbc06-layout-smoke")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument(
        "--cleanup-method",
        default="region_fill",
        choices=["region_fill", "soft_region_fill", "mask_fill", "text_mask_inpaint"],
    )
    parser.add_argument(
        "--inpaint-method",
        default="opencv_telea",
        choices=["local_diffusion", "flat_median_fill", "opencv_telea", "opencv_ns", "bt_patchmatch", "bt_aot", "bt_lama_large"],
    )
    parser.add_argument(
        "--mask-dilate-px",
        type=int,
        default=3,
        help="Text-mask dilation size for cleanup-method=text_mask_inpaint.",
    )
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    args = parser.parse_args()

    run_dir = run_phase6_bubble_cleanup(
        detection_run_dir=Path(args.detection_run_dir),
        layout_run_dir=Path(args.layout_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
        cleanup_method=args.cleanup_method,
        record_ids=args.record_ids,
        inpaint_method=args.inpaint_method,
        mask_dilate_px=args.mask_dilate_px,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
