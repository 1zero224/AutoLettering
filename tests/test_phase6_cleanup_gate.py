import json
from pathlib import Path

from autolettering.phase6_cleanup_gate import run_phase6_cleanup_gate


def test_run_phase6_cleanup_gate_writes_gpt_escalation_candidate_for_failed_cta_lama(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    quality_run = tmp_path / "quality"
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#1",
                "image_name": "page.png",
                "translated_text": "漫画第一卷",
                "status": "cleaned",
                "cleanup": {
                    "method": "bt_lama_large_inpaint",
                    "route": "cta_mask_lama_large_512px",
                    "text_region_source": "ctd_refined_mask_component",
                    "bbox": [10, 20, 40, 80],
                    "source_mask_path": "component-mask.png",
                    "before_after_path": "before-after.png",
                    "cleaned_crop_path": "cleaned.png",
                },
            }
        ],
    )
    _write_jsonl(
        quality_run / "cleanup-quality.jsonl",
        [
            {
                "record_id": "page.png#1",
                "image_name": "page.png",
                "status": "evaluated",
                "score": 2,
                "usable": False,
                "original_text_removed": False,
                "art_preserved": True,
                "issues": ["heavy_ghosting"],
                "summary": "Visible original text remains.",
                "evaluation_image_path": "quality-sheet.png",
            }
        ],
    )

    run_dir = run_phase6_cleanup_gate(
        cleanup_run,
        quality_run,
        output_root=tmp_path / "outputs",
        run_id="gate-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "cleanup-escalation-candidates.jsonl")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    report = (run_dir / "reports" / "phase6-cleanup-gate-report.md").read_text(encoding="utf-8")

    assert manifest["candidate_count"] == 1
    assert manifest["candidate_record_ids"] == ["page.png#1"]
    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["recommended_route"] == "quality_gate_gpt_image2_masked_edit"
    assert rows[0]["recommended_action"] == "run_gpt_image2_transparent_masked_replacement"
    assert rows[0]["reason_codes"] == [
        "phase6_cleanup_unusable",
        "phase6_cleanup_original_text_visible",
        "phase6_cleanup_low_score",
    ]
    assert rows[0]["cleanup"]["source_mask_path"] == "component-mask.png"
    assert rows[0]["gpt_image2_contract"]["target_text"] == "漫画第一卷"
    assert "page.png#1" in report
    assert "quality_gate_gpt_image2_masked_edit" in report


def test_run_phase6_cleanup_gate_skips_usable_lama_quality(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    quality_run = tmp_path / "quality"
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "cleaned",
                "cleanup": {
                    "method": "bt_lama_large_inpaint",
                    "route": "cta_mask_lama_large_512px",
                    "source_mask_path": "component-mask.png",
                },
            }
        ],
    )
    _write_jsonl(
        quality_run / "cleanup-quality.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "evaluated",
                "score": 9,
                "usable": True,
                "original_text_removed": True,
                "art_preserved": True,
            }
        ],
    )

    run_dir = run_phase6_cleanup_gate(cleanup_run, quality_run, output_root=tmp_path / "outputs", run_id="gate-pass")

    assert _read_jsonl(run_dir / "cleanup-escalation-candidates.jsonl") == []
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_count"] == 0


def test_run_phase6_cleanup_gate_skips_non_cta_lama_failures(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    quality_run = tmp_path / "quality"
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "cleaned",
                "cleanup": {
                    "method": "opencv_telea",
                    "bbox": [10, 20, 40, 80],
                },
            }
        ],
    )
    _write_jsonl(
        quality_run / "cleanup-quality.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "evaluated",
                "score": 2,
                "usable": False,
                "original_text_removed": False,
                "art_preserved": True,
            }
        ],
    )

    run_dir = run_phase6_cleanup_gate(cleanup_run, quality_run, output_root=tmp_path / "outputs", run_id="gate-skip")

    assert _read_jsonl(run_dir / "cleanup-escalation-candidates.jsonl") == []


def test_run_phase6_cleanup_gate_requires_cta_or_ctd_provenance(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    quality_run = tmp_path / "quality"
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "cleaned",
                "cleanup": {
                    "method": "bt_lama_large_inpaint",
                    "source_mask_path": "some-mask.png",
                },
            }
        ],
    )
    _write_jsonl(
        quality_run / "cleanup-quality.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "evaluated",
                "score": 2,
                "usable": False,
                "original_text_removed": False,
                "art_preserved": True,
            }
        ],
    )

    run_dir = run_phase6_cleanup_gate(cleanup_run, quality_run, output_root=tmp_path / "outputs", run_id="gate-source-mask")

    assert _read_jsonl(run_dir / "cleanup-escalation-candidates.jsonl") == []


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
