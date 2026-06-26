import json
from pathlib import Path

from PIL import Image

from experiments.phase7_8_gpt_quality_gate_smoke import run_quality_gate_smoke


def test_run_quality_gate_smoke_rejects_bad_gpt_replacement(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 100), "white").save(image_path)
    cleaned_path = tmp_path / "cleaned.png"
    replacement_path = tmp_path / "bad-gpt.png"
    Image.new("RGB", (40, 50), "white").save(cleaned_path)
    Image.new("RGB", (40, 50), "red").save(replacement_path)
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    quality_run = tmp_path / "quality"
    _write_jsonl(
        detection_run / "detections.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "fallback_required",
                "image_name": "page.png",
                "image_path": str(image_path),
                "translated_text": "啪嗒啪嗒啪嗒",
                "selected_text_box_xyxy": None,
            }
        ],
    )
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "cleaned",
                "cleanup": {
                    "method": "gpt_image2_masked_edit",
                    "bbox": [40, 20, 80, 70],
                    "layout_text_bbox": [40, 20, 80, 70],
                    "cleaned_crop_path": str(cleaned_path),
                    "replacement_method": "gpt_image2_masked_edit",
                    "replacement_crop_path": str(replacement_path),
                    "text_overlay_required": False,
                },
                "gpt_image2_edit": {"status": "ok"},
            }
        ],
    )
    _write_jsonl(
        quality_run / "replacement-quality.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "evaluated",
                "usable": False,
                "exact_text_correct": False,
                "simplified_chinese_correct": False,
                "no_japanese_remaining": True,
                "region_correct": True,
                "issues": ["wrong_text"],
            }
        ],
    )

    run_dir = run_quality_gate_smoke(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        phase6_gpt_quality_run_dir=quality_run,
        output_root=tmp_path / "outputs",
        run_id="quality-gate-smoke",
        sample_limit=1,
    )

    summary = json.loads((run_dir / "quality-gate-smoke-summary.json").read_text(encoding="utf-8"))
    assert summary["records"][0]["record_id"] == "page.png#1"
    assert summary["records"][0]["gpt_quality_accepted"] is False
    assert summary["records"][0]["phase7_cleanup_crop_path"] == str(cleaned_path)
    assert summary["records"][0]["phase7_text_overlay_required"] is True
    assert summary["records"][0]["phase8_effective_crop_path"] == str(cleaned_path)
    assert summary["records"][0]["phase8_effective_method"] == "gpt_image2_masked_edit"
    assert summary["records"][0]["phase8_replacement_method"] is None
    assert summary["records"][0]["phase8_text_layer_exported"] is True
    assert Path(summary["phase7_run_dir"]).parts[-2:] == ("runs", "phase7-preview")
    assert Path(summary["phase8_run_dir"]).parts[-2:] == ("runs", "phase8-export")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
