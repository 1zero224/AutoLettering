import json
from pathlib import Path

from autolettering.cta_first_pipeline import run_cta_first_cleanup_pipeline


def test_run_cta_first_cleanup_pipeline_routes_matched_and_fallback_records(tmp_path: Path, monkeypatch):
    calls = {}

    def fake_phase2(**kwargs):
        calls["phase2"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        _write_jsonl(
            run_dir / "detections.jsonl",
            [
                {
                    "record_id": "page.png#1",
                    "status": "ok",
                    "image_name": "page.png",
                    "group_name": "框外",
                    "lettering_route": {"route": "cta_mask_lama_large_512px"},
                    "cta_match": {"status": "matched", "mask_path": "component-0001.png"},
                    "ctd_match": {"status": "matched", "mask_path": "component-0001.png"},
                },
                {
                    "record_id": "page.png#2",
                    "status": "fallback_required",
                    "image_name": "page.png",
                    "group_name": "框外",
                    "lettering_route": {"route": "mimo_locator_gpt_image2_masked_edit"},
                    "fallback": {"method": "mimo_crop_then_gpt_image2_masked_edit"},
                },
            ],
        )
        return run_dir

    def fake_phase6(**kwargs):
        calls["phase6"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        _write_jsonl(
            run_dir / "cleanup-results.jsonl",
            [
                {
                    "record_id": "page.png#1",
                    "status": "cleaned",
                    "cleanup": {
                        "method": "bt_lama_large_inpaint",
                        "route": "cta_mask_lama_large_512px",
                        "text_overlay_required": True,
                    },
                    "gpt_image2_edit": {"status": "not_applicable"},
                },
                {
                    "record_id": "page.png#2",
                    "status": "failed",
                    "cleanup": {
                        "method": "gpt_image2_masked_edit",
                        "text_overlay_required": True,
                        "failure_reason": "gpt_image2_replacement_not_completed",
                    },
                    "fallback_locator": {"status": "ok"},
                    "gpt_image2_edit": {"status": "dry_run"},
                },
            ],
        )
        return run_dir

    monkeypatch.setattr("autolettering.cta_first_pipeline.run_phase2", fake_phase2)
    monkeypatch.setattr("autolettering.cta_first_pipeline.run_phase6_nonbubble_cleanup", fake_phase6)

    run_dir = run_cta_first_cleanup_pipeline(
        labelplus_file=tmp_path / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="cta-first",
        sample_limit=2,
        record_ids=["page.png#1", "page.png#2"],
        ctd_max_edge_distance_px=20,
        call_gpt_image=True,
        gpt_config=object(),
        mimo_client=object(),
    )

    assert calls["phase2"]["detection_strategy"] == "cta_mask"
    assert calls["phase2"]["ctd_max_edge_distance_px"] == 20
    assert calls["phase6"]["detection_run_dir"] == run_dir / "runs" / "phase2-cta-mask"
    assert calls["phase6"]["inpaint_method"] == "bt_lama_large"
    assert calls["phase6"]["call_gpt_image"] is True

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "autolettering.cta_first_pipeline.v1"
    assert manifest["phase2_detection_run_dir"] == str(run_dir / "runs" / "phase2-cta-mask")
    assert manifest["phase6_cleanup_run_dir"] == str(run_dir / "runs" / "phase6-cta-first-cleanup")
    assert manifest["text_detection_plan"] == {
        "user_requested_strategy": "cta",
        "project_strategy": "cta_mask",
        "ballonstranslator_detector_module": "ctd",
        "ballonstranslator_detector_class": "ComicTextDetector",
        "ballonstranslator_config_path": "BallonsTranslator/config/config.json",
        "ballonstranslator_config_key": "module.textdetector_params.ctd",
        "mask_artifact": "debug/ctd_masks/<page>/ctd-refined-mask.png",
        "component_manifest": "debug/ctd_masks/<page>/cta-closed-mask-components.json",
        "distance_artifact": "debug/ctd_masks/<page>/ctd-mask-edge-distances.jsonl",
        "componentization": "connected_components_over_refined_mask",
        "matching_metric": "labelplus_point_to_mask_edge",
        "matching_cardinality": "unique_mask_component_claim",
        "fallback_trigger": "no_unique_ctd_mask_match_within_threshold",
    }
    assert manifest["cleanup_plan"]["matched_ctd_mask"] == {
        "text_region_source": "ctd_refined_mask_component",
        "inpaint_method": "lama_large_512px",
        "lettering": "programmatic_editable_text_layer",
    }
    assert manifest["cleanup_plan"]["unmatched_labelplus_point"] == {
        "context_crop": "near_square_labelplus_context_crop",
        "locator": "mimo_vision_model_returns_crop_local_bbox",
        "replacement": "gpt-image-2_transparent_masked_edit",
        "lettering": "gpt-image-2_direct_replacement_when_call_succeeds",
    }
    assert manifest["photoshop_export_contract"]["project_manifest"] == "photoshop-manifest.json"
    assert manifest["photoshop_export_contract"]["import_script"] == "photoshop-import.jsx"
    assert manifest["photoshop_export_contract"]["layer_order_top_to_bottom"] == [
        "嵌字图层1",
        "嵌字图层2",
        "...",
        "修复图像",
        "原图",
    ]
    assert "lama_large_512px" in manifest["photoshop_export_contract"]["repaired_image_source"]
    assert "gpt-image-2" in manifest["photoshop_export_contract"]["repaired_image_source"]
    assert manifest["review_image_contract"] == {
        "font_and_effect_grids": "use near_square_columns instead of long strips",
        "fallback_locator_grid": "visuals/fallback-locator-grid.png",
        "mimo_review_policy": "readable near-square contact sheets",
    }
    assert manifest["summary"]["matched_cta_records"] == 1
    assert manifest["summary"]["matched_ctd_records"] == 1
    assert manifest["summary"]["fallback_required_records"] == 1
    assert manifest["summary"]["lama_large_cleanup_records"] == 1
    assert manifest["summary"]["gpt_image2_replacement_records"] == 0
    assert manifest["summary"]["gpt_image2_pending_or_failed_records"] == 1
    assert manifest["summary"]["text_overlay_required_records"] == 2
    report = (run_dir / "reports" / "cta-first-pipeline-report.md").read_text(encoding="utf-8")
    assert "BallonsTranslator detector: `ctd` / `ComicTextDetector`" in report
    assert "CTA-first means CTD refined-mask connected components first" in report
    assert "Matched CTD mask -> `lama_large_512px` cleanup -> editable lettering layer" in report
    assert "Unmatched LabelPlus point -> near-square MIMO locator crop -> `gpt-image-2` transparent masked replacement" in report
    assert "`photoshop-import.jsx` reads `photoshop-manifest.json`, not the LabelPlus txt directly" in report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
