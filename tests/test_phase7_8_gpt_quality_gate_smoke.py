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
    evidence_grid_path = Path(summary["evidence_grid_path"])
    assert summary["records"][0]["record_id"] == "page.png#1"
    assert summary["records"][0]["gpt_quality_accepted"] is False
    assert summary["records"][0]["gpt_replacement_crop_path"] == str(replacement_path)
    assert summary["records"][0]["phase7_cleanup_crop_path"] == str(cleaned_path)
    assert summary["records"][0]["phase7_text_overlay_required"] is True
    assert summary["records"][0]["phase8_effective_crop_path"] == str(cleaned_path)
    assert summary["records"][0]["phase8_effective_method"] == "gpt_image2_masked_edit"
    assert summary["records"][0]["phase8_replacement_method"] is None
    assert summary["records"][0]["phase8_text_layer_exported"] is True
    assert Path(summary["phase7_run_dir"]).parts[-2:] == ("runs", "phase7-preview")
    assert Path(summary["phase8_run_dir"]).parts[-2:] == ("runs", "phase8-export")
    assert evidence_grid_path == run_dir / "visuals" / "quality-gate-evidence-grid.png"
    with Image.open(evidence_grid_path) as grid:
        ratio = grid.width / grid.height
    assert 0.5 <= ratio <= 2.0
    report = (run_dir / "reports" / "quality-gate-smoke-report.md").read_text(encoding="utf-8")
    assert "quality-gate-evidence-grid.png" in report


def test_run_quality_gate_smoke_consumes_fallback_cleaned_crop_without_gpt_replacement(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 100), "white").save(image_path)
    fallback_cleaned_path = tmp_path / "fallback_cleaned" / "page-1.png"
    fallback_mask_path = tmp_path / "fallback_mask" / "page-1.png"
    fallback_cleaned_path.parent.mkdir()
    fallback_mask_path.parent.mkdir()
    Image.new("RGB", (40, 50), "white").save(fallback_cleaned_path)
    Image.new("L", (40, 50), 255).save(fallback_mask_path)
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    quality_run = tmp_path / "quality"
    quality_run.mkdir()
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
                    "method": "bt_lama_large_inpaint",
                    "bbox": [40, 20, 80, 70],
                    "text_bbox": [42, 22, 78, 68],
                    "mask_bbox": [42, 22, 78, 68],
                    "layout_text_bbox": [42, 22, 78, 68],
                    "cleaned_crop_path": str(fallback_cleaned_path),
                    "cleanup_mask_path": str(fallback_mask_path),
                    "text_overlay_required": True,
                    "replacement_failure_reason": "gpt_image2_replacement_not_completed",
                },
                "gpt_image2_edit": {"status": "dry_run"},
            }
        ],
    )

    run_dir = run_quality_gate_smoke(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        phase6_gpt_quality_run_dir=quality_run,
        output_root=tmp_path / "outputs",
        run_id="fallback-cleaned-smoke",
        sample_limit=1,
    )

    summary = json.loads((run_dir / "quality-gate-smoke-summary.json").read_text(encoding="utf-8"))
    record = summary["records"][0]
    assert record["gpt_replacement_crop_path"] is None
    assert record["gpt_quality_accepted"] is None
    assert record["phase7_cleanup_method"] == "bt_lama_large_inpaint"
    assert record["phase7_cleanup_crop_path"] == str(fallback_cleaned_path)
    assert record["phase7_text_overlay_required"] is True
    assert record["phase8_effective_method"] == "bt_lama_large_inpaint"
    assert record["phase8_effective_crop_path"] == str(fallback_cleaned_path)
    assert record["phase8_replacement_method"] is None
    assert record["phase8_text_layer_exported"] is True
    assert record["phase8_text_overlay_required"] is True


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
