import json
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
    Image.new("L", (240, 240), 0).save(component_mask)

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
    Image.new("L", (240, 240), 0).save(component_mask)

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
    assert record["text_region_source"] == "cta_mask"
    assert record["text_region_mask_path"] == str(component_mask)
    assert record["text_region_mask_bbox_xyxy"] == [88, 70, 116, 151]
    assert record["match_status"] == "matched"
    assert record["lettering_route"] == {
        "route": "cta_mask_lama_large_512px",
        "text_region_source": "cta_mask",
        "repair_method": "lama_large_512px",
        "requires_mimo_locator": False,
        "requires_gpt_image2_replacement": False,
    }
    assert record["cta_match"]["status"] == "matched"
    assert record["cta_match"]["component_id"] == "component-0001"
    assert record["ctd_match"] == record["cta_match"]


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
    assert record["text_region_mask_path"] is None
    assert record["text_region_mask_bbox_xyxy"] is None
    assert record["match_status"] == "fallback_required"
    assert record["fallback"]["method"] == "mimo_crop_then_gpt_image2_masked_edit"
    assert record["fallback"]["trigger_reason"] == "no_ctd_mask_within_threshold"
    assert record["fallback"]["upstream_match_attempted"] is True
    assert record["fallback"]["upstream_match_metric"] == "point_to_mask_edge"
    assert record["fallback"]["upstream_match_threshold_px"] == 8
    assert record["fallback"]["context_bbox_xyxy"] == [0, 0, 240, 240]
    assert record["lettering_route"] == {
        "route": "mimo_locator_gpt_image2_masked_edit",
        "text_region_source": "mimo_vision_model",
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
    assert record["fallback"]["context_shape"] == "near_square"


def test_run_phase2_defaults_ctd_mask_edge_distance_to_twenty(tmp_path: Path, monkeypatch):
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

    assert captured["max_edge_distance_px"] == 20.0


def _write_project_image(path: Path) -> None:
    image = Image.new("RGB", (240, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 72, 115, 150), fill="black")
    image.save(path)


def _write_labelplus(path: Path) -> None:
    path.write_text(
        """1,0
-
框外
-
Comment

>>>>>>>>[page.png]<<<<<<<<
----------------[1]----------------[0.425,0.458,1]
测试
""",
        encoding="utf-8",
    )
