import json
import csv
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.detection.ctd_masks import CtdMaskComponent
from autolettering.phase2 import run_phase2


def test_run_phase2_ctd_strategy_uses_matched_mask_component_as_text_region(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = project_dir / "page.png"
    _write_project_image(image_path)
    _write_labelplus(project_dir / "翻译_0.txt")
    component_mask = tmp_path / "component.png"
    _write_component_mask(component_mask, (88, 70, 116, 151))

    monkeypatch.setattr(
        "autolettering.phase2.detect_ctd_mask_components_for_image",
        lambda image, output_dir, **kwargs: [
            CtdMaskComponent(
                component_id="component-0001",
                bbox_xyxy=(88, 70, 116, 151),
                area_px=2268,
                centroid_xy=(102.0, 110.0),
                mask_path=component_mask,
            )
        ],
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-ctd-test",
        sample_limit=1,
        detection_strategy="ctd_mask",
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    assert record["status"] == "ok"
    assert record["detection_method"] == "ctd_mask"
    assert record["selected_text_box_xyxy"] == [88, 70, 116, 151]
    assert record["ctd_match"]["status"] == "matched"
    assert record["ctd_match"]["component_id"] == "component-0001"
    assert record["ctd_match"]["mask_path"] == str(component_mask)


def test_run_phase2_cta_strategy_writes_mask_component_as_primary_text_region(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = project_dir / "page.png"
    _write_project_image(image_path)
    _write_labelplus(project_dir / "翻译_0.txt")
    component_mask = tmp_path / "component.png"
    _write_component_mask(component_mask, (88, 70, 116, 151))

    monkeypatch.setattr(
        "autolettering.phase2.detect_ctd_mask_components_for_image",
        lambda image, output_dir, **kwargs: [
            CtdMaskComponent(
                component_id="component-0001",
                bbox_xyxy=(88, 70, 116, 151),
                area_px=2268,
                centroid_xy=(102.0, 110.0),
                mask_path=component_mask,
            )
        ],
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-cta-test",
        sample_limit=1,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    assert record["status"] == "ok"
    assert record["detection_method"] == "cta_mask"
    assert record["selected_text_box_xyxy"] == [88, 70, 116, 151]
    assert record["selected_text_full_xyxy"] == [88, 70, 116, 151]
    assert record["selected_text_body_xyxy"] == [88, 70, 116, 151]
    assert record["text_region_kind"] == "cta_mask_matched"
    assert record["text_region_source"] == "ctd_refined_mask_component"
    assert record["text_region_user_strategy"] == "cta_mask"
    assert record["ballonstranslator_detector_module"] == "ctd"
    assert record["ballonstranslator_detector_class"] == "ComicTextDetector"
    assert record["mask_matching_metric"] == "labelplus_point_to_mask_edge"
    assert record["mask_matching_cardinality"] == "unique_component_claim"
    assert record["text_region_mask_path"] == str(component_mask)
    assert record["text_region_mask_bbox_xyxy"] == [88, 70, 116, 151]
    assert record["match_status"] == "matched"
    assert record["lettering_route"] == {
        "route": "cta_mask_lama_large_512px",
        "text_region_source": "ctd_refined_mask_component",
        "text_region_user_strategy": "cta_mask",
        "ballonstranslator_detector_module": "ctd",
        "repair_method": "lama_large_512px",
        "requires_mimo_locator": False,
        "requires_gpt_image2_replacement": False,
    }
    assert record["cta_match"]["status"] == "matched"
    assert record["cta_match"]["component_id"] == "component-0001"
    assert record["ctd_match"] == record["cta_match"]
    expected_diagnostics = {
        "schema_version": "autolettering.cta_mask_match_diagnostics.v1",
        "record_id": "page.png#1",
        "match_status": "matched",
        "failure_reason": None,
        "threshold_px": 30.0,
        "candidate_count": 1,
        "within_threshold_count": 1,
        "nearest_component_id": "component-0001",
        "nearest_edge_distance_px": 14.0,
        "selected_component_id": "component-0001",
        "top_candidates": [
            {
                "component_id": "component-0001",
                "component_bbox_xyxy": [88, 70, 116, 151],
                "component_mask_path": str(component_mask),
                "edge_distance_px": 14.0,
                "within_threshold": True,
            }
        ],
    }
    assert record["cta_match_diagnostics"] == expected_diagnostics
    assert record["ctd_match_diagnostics"] == expected_diagnostics
    ctd_dir = run_dir / "debug" / "ctd_masks" / "page"
    components = json.loads((ctd_dir / "cta-closed-mask-components.json").read_text(encoding="utf-8"))
    assert components["schema_version"] == "autolettering.cta_mask_components.v1"
    assert components["componentization"] == "8_connected_components_over_ballonstranslator_ctd_refined_mask"
    assert components["components"] == [
        {
            "component_id": "component-0001",
            "bbox_xyxy": [88, 70, 116, 151],
            "area_px": 2268,
            "centroid_xy": [102.0, 110.0],
            "mask_path": str(component_mask),
        }
    ]
    distances = _read_jsonl(ctd_dir / "ctd-mask-edge-distances.jsonl")
    assert distances == [
        {
            "record_id": "page.png#1",
            "labelplus_point_xy": [102, 110],
            "component_id": "component-0001",
            "component_bbox_xyxy": [88, 70, 116, 151],
            "component_mask_path": str(component_mask),
            "edge_distance_px": 14.0,
            "within_threshold": True,
            "threshold_px": 30.0,
        }
    ]
    with (run_dir / "reports" / "manual-review.csv").open("r", encoding="utf-8", newline="") as handle:
        review_row = next(csv.DictReader(handle))
    assert review_row["mask_match_status"] == "matched"
    assert review_row["mask_match_nearest_component_id"] == "component-0001"
    assert review_row["mask_match_nearest_edge_distance_px"] == "14.0"
    assert review_row["mask_match_within_threshold_count"] == "1"


def test_run_phase2_ctd_strategy_records_fallback_required_when_no_component_is_close(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = project_dir / "page.png"
    _write_project_image(image_path)
    _write_labelplus(project_dir / "翻译_0.txt")
    component_mask = tmp_path / "component.png"
    Image.new("L", (240, 240), 0).save(component_mask)

    monkeypatch.setattr(
        "autolettering.phase2.detect_ctd_mask_components_for_image",
        lambda image, output_dir, **kwargs: [
            CtdMaskComponent(
                component_id="component-0001",
                bbox_xyxy=(160, 20, 190, 50),
                area_px=900,
                centroid_xy=(175.0, 35.0),
                mask_path=component_mask,
            )
        ],
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-ctd-fallback-test",
        sample_limit=1,
        detection_strategy="ctd_mask",
        ctd_max_edge_distance_px=8,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    assert record["status"] == "fallback_required"
    assert record["detection_method"] == "ctd_mask"
    assert record["selected_text_box_xyxy"] is None
    assert record["failure_reason"] == "no_ctd_mask_within_threshold"
    assert record["text_region_kind"] == "fallback_context_only"
    assert record["text_region_source"] == "mimo_vision_model"
    assert record["text_region_user_strategy"] == "ctd_mask"
    assert record["ballonstranslator_detector_module"] == "ctd"
    assert record["mask_matching_metric"] == "labelplus_point_to_mask_edge"
    assert record["mask_matching_cardinality"] == "unique_component_claim"
    assert record["text_region_mask_path"] is None
    assert record["text_region_mask_bbox_xyxy"] is None
    assert record["match_status"] == "fallback_required"
    assert record["ctd_match_diagnostics"] == {
        "schema_version": "autolettering.cta_mask_match_diagnostics.v1",
        "record_id": "page.png#1",
        "match_status": "fallback_required",
        "failure_reason": "no_ctd_mask_within_threshold",
        "threshold_px": 8,
        "candidate_count": 1,
        "within_threshold_count": 0,
        "nearest_component_id": "component-0001",
        "nearest_edge_distance_px": 83.451,
        "selected_component_id": None,
        "top_candidates": [
            {
                "component_id": "component-0001",
                "component_bbox_xyxy": [160, 20, 190, 50],
                "component_mask_path": str(component_mask),
                "edge_distance_px": 83.451,
                "within_threshold": False,
            }
        ],
    }
    assert record["cta_match_diagnostics"] == record["ctd_match_diagnostics"]
    assert record["fallback"]["method"] == "mimo_crop_then_gpt_image2_masked_edit"
    assert record["fallback"]["trigger_reason"] == "no_ctd_mask_within_threshold"
    assert record["fallback"]["upstream_match_attempted"] is True
    assert record["fallback"]["upstream_match_metric"] == "point_to_mask_edge"
    assert record["fallback"]["upstream_match_threshold_px"] == 8
    assert record["fallback"]["context_bbox_xyxy"] == [0, 0, 240, 240]
    assert record["fallback"]["labelplus_point_xy"] == [102, 110]
    assert record["fallback"]["context_labelplus_point_xy"] == [102, 110]
    assert record["lettering_route"] == {
        "route": "mimo_locator_gpt_image2_masked_edit",
        "text_region_source": "mimo_vision_model",
        "text_region_user_strategy": "ctd_mask",
        "upstream_text_region_source": "ctd_refined_mask_component",
        "repair_method": "gpt_image2_masked_edit",
        "requires_mimo_locator": True,
        "requires_gpt_image2_replacement": True,
    }


def test_run_phase2_fallback_context_is_expanded_to_near_square_for_vision(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = project_dir / "page.png"
    _write_project_image(image_path)
    _write_labelplus(project_dir / "翻译_0.txt")

    monkeypatch.setattr("autolettering.phase2.detect_ctd_mask_components_for_image", lambda image, output_dir, **kwargs: [])

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-near-square-fallback",
        sample_limit=1,
        detection_strategy="ctd_mask",
        radius_x=110,
        radius_y=40,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    assert record["fallback"]["source_context_bbox_xyxy"] == [0, 70, 212, 150]
    assert record["fallback"]["context_bbox_xyxy"] == [0, 4, 212, 216]
    assert record["fallback"]["labelplus_point_xy"] == [102, 110]
    assert record["fallback"]["context_labelplus_point_xy"] == [102, 106]
    assert record["fallback"]["context_shape"] == "near_square"


def test_run_phase2_fallback_context_includes_nearby_ctd_candidate_for_mimo_locator(
    tmp_path: Path, monkeypatch
):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = project_dir / "page.png"
    _write_project_image(image_path, size=(1000, 1000))
    _write_labelplus(project_dir / "翻译_0.txt", position=(0.5, 0.7))
    component_mask = tmp_path / "component.png"
    _write_component_mask(component_mask, (480, 520, 540, 550), size=(1000, 1000))

    monkeypatch.setattr(
        "autolettering.phase2.detect_ctd_mask_components_for_image",
        lambda image, output_dir, **kwargs: [
            CtdMaskComponent(
                component_id="component-0001",
                bbox_xyxy=(480, 520, 540, 550),
                area_px=1800,
                centroid_xy=(510.0, 535.0),
                mask_path=component_mask,
            )
        ],
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-fallback-candidate-context",
        sample_limit=1,
        detection_strategy="ctd_mask",
        radius_x=140,
        radius_y=100,
        ctd_max_edge_distance_px=20,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    assert record["status"] == "fallback_required"
    assert record["ctd_match_diagnostics"]["nearest_edge_distance_px"] == 150.0
    assert record["fallback"]["source_context_bbox_xyxy"] == [360, 600, 640, 800]
    assert record["fallback"]["expanded_source_context_bbox_xyxy"] == [360, 520, 640, 800]
    assert record["fallback"]["context_bbox_xyxy"] == [360, 520, 640, 800]
    assert record["fallback"]["context_source"] == "labelplus_search_region_plus_ctd_candidates"
    assert record["fallback"]["context_candidate_component_ids"] == ["component-0001"]
    assert record["fallback"]["context_candidate_bboxes_xyxy"] == [[480, 520, 540, 550]]
    assert record["fallback"]["labelplus_point_xy"] == [500, 700]
    assert record["fallback"]["context_labelplus_point_xy"] == [140, 180]


def test_run_phase2_fallback_context_groups_nearby_ctd_candidates_for_large_sound_effect(
    tmp_path: Path, monkeypatch
):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = project_dir / "page.png"
    _write_project_image(image_path, size=(1000, 1000))
    _write_labelplus(project_dir / "翻译_0.txt", position=(0.52, 0.74))
    same_text_mask = tmp_path / "same-text.png"
    _write_component_mask(same_text_mask, (430, 500, 460, 620), size=(1000, 1000))
    same_text_mask_2 = tmp_path / "same-text-2.png"
    _write_component_mask(same_text_mask_2, (470, 505, 500, 625), size=(1000, 1000))
    far_bubble_mask = tmp_path / "far-bubble.png"
    _write_component_mask(far_bubble_mask, (800, 700, 840, 820), size=(1000, 1000))

    monkeypatch.setattr(
        "autolettering.phase2.detect_ctd_mask_components_for_image",
        lambda image, output_dir, **kwargs: [
            CtdMaskComponent(
                component_id="component-sound-a",
                bbox_xyxy=(430, 500, 460, 620),
                area_px=3600,
                centroid_xy=(445.0, 560.0),
                mask_path=same_text_mask,
            ),
            CtdMaskComponent(
                component_id="component-sound-b",
                bbox_xyxy=(470, 505, 500, 625),
                area_px=3600,
                centroid_xy=(485.0, 565.0),
                mask_path=same_text_mask_2,
            ),
            CtdMaskComponent(
                component_id="component-other",
                bbox_xyxy=(800, 700, 840, 820),
                area_px=4800,
                centroid_xy=(820.0, 760.0),
                mask_path=far_bubble_mask,
            ),
        ],
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-fallback-cluster-context",
        sample_limit=1,
        detection_strategy="ctd_mask",
        radius_x=120,
        radius_y=80,
        ctd_max_edge_distance_px=20,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    assert record["status"] == "fallback_required"
    assert record["fallback"]["source_context_bbox_xyxy"] == [400, 660, 640, 820]
    assert record["fallback"]["expanded_source_context_bbox_xyxy"] == [400, 500, 640, 820]
    assert record["fallback"]["context_bbox_xyxy"] == [360, 500, 680, 820]
    assert record["fallback"]["context_candidate_component_ids"] == [
        "component-sound-b",
        "component-sound-a",
    ]
    assert record["fallback"]["context_candidate_bboxes_xyxy"] == [
        [470, 505, 500, 625],
        [430, 500, 460, 620],
    ]


def test_run_phase2_defaults_ctd_mask_edge_distance_to_thirty(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = project_dir / "page.png"
    _write_project_image(image_path)
    _write_labelplus(project_dir / "翻译_0.txt")
    captured = {}

    monkeypatch.setattr(
        "autolettering.phase2.detect_ctd_mask_components_for_image",
        lambda image, output_dir, **kwargs: [],
    )

    def fake_assign(labels, components, max_edge_distance_px):
        captured["max_edge_distance_px"] = max_edge_distance_px
        return {}

    monkeypatch.setattr("autolettering.phase2.assign_labelplus_points_to_ctd_masks", fake_assign)

    run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-ctd-default-threshold",
        sample_limit=1,
        detection_strategy="ctd_mask",
    )

    assert captured["max_edge_distance_px"] == 30.0


def _write_project_image(path: Path, size: tuple[int, int] = (240, 240)) -> None:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 72, 115, 150), fill="black")
    image.save(path)


def _write_component_mask(
    path: Path,
    bbox: tuple[int, int, int, int],
    size: tuple[int, int] = (240, 240),
) -> None:
    image = Image.new("L", size, 0)
    ImageDraw.Draw(image).rectangle((bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1), fill=255)
    image.save(path)


def _write_labelplus(path: Path, position: tuple[float, float] = (0.425, 0.458)) -> None:
    path.write_text(
        f"""1,0
-
框外
-
Comment

>>>>>>>>[page.png]<<<<<<<<
----------------[1]----------------[{position[0]},{position[1]},1]
测试
""",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
