import json
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops

from autolettering.layout.candidates import generate_line_break_candidates
from autolettering.layout.measure import measure_text_layout, search_fitting_layout
from autolettering.layout.render_text import measure_preview_alignment, render_layout_preview
from autolettering.phase4 import run_phase4


def test_generate_line_break_candidates_includes_single_line_and_wrapped_forms():
    candidates = generate_line_break_candidates("街头演出？", max_lines=3)

    assert "街头演出？" in candidates
    assert any("\n" in candidate for candidate in candidates)
    assert len(candidates) == len(set(candidates))


def test_search_fitting_layout_selects_largest_font_with_bounded_overflow(tmp_path: Path):
    font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="街头演出？",
        font_path=font_path,
        target_size=(150, 80),
        min_font_size=12,
        max_font_size=64,
        allow_overflow_ratio=0.05,
    )

    measured = measure_text_layout(result.line_breaks, font_path, result.font_size)
    assert result.orientation == "horizontal"
    assert result.font_size >= 12
    assert result.overflow_ratio <= 0.05
    assert measured.width <= int(150 * 1.05)
    assert measured.height <= int(80 * 1.05)


def test_search_fitting_layout_accounts_for_rotation_footprint(tmp_path: Path):
    font_path = _copy_font(tmp_path)

    unrotated = search_fitting_layout(
        text="那个当然也要做哦",
        font_path=font_path,
        target_size=(190, 80),
        min_font_size=12,
        max_font_size=72,
        orientation="horizontal",
        angle_degrees=0.0,
    )
    rotated = search_fitting_layout(
        text="那个当然也要做哦",
        font_path=font_path,
        target_size=(190, 80),
        min_font_size=12,
        max_font_size=72,
        orientation="horizontal",
        angle_degrees=35.0,
    )

    assert rotated.font_size < unrotated.font_size
    assert rotated.measured_width <= 190
    assert rotated.measured_height <= 80


def test_search_fitting_layout_uses_vertical_for_tall_narrow_targets(tmp_path: Path):
    font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="街头演出？",
        font_path=font_path,
        target_size=(90, 220),
        min_font_size=12,
        max_font_size=64,
    )

    measured = measure_text_layout(result.line_breaks, font_path, result.font_size, orientation="vertical")
    assert result.orientation == "vertical"
    assert measured.height > measured.width
    assert result.overflow_ratio <= 0.08


def test_search_fitting_layout_preserves_vertical_line_breaks_as_columns(tmp_path: Path):
    font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="是的\n我想刚开始还是这样比较好",
        font_path=font_path,
        target_size=(48, 188),
        min_font_size=12,
        max_font_size=18,
        orientation="vertical",
    )

    assert "\n" in result.line_breaks
    assert result.status == "ok"
    assert result.measured_height <= 188


def test_render_layout_preview_writes_non_empty_transparent_png(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    output_path = tmp_path / "preview.png"
    layout = search_fitting_layout("街头演出？", font_path, (160, 90), max_font_size=42)

    result = render_layout_preview(layout, font_path, output_path, canvas_size=(160, 90))

    assert result == output_path
    assert output_path.exists()
    with Image.open(output_path) as image:
        assert image.mode == "RGBA"
        assert image.getbbox() is not None


def test_measure_preview_alignment_reports_alpha_ink_offsets(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    output_path = tmp_path / "preview.png"
    layout = search_fitting_layout("街头演出？", font_path, (160, 90), max_font_size=42)
    render_layout_preview(layout, font_path, output_path, canvas_size=(160, 90))

    alignment = measure_preview_alignment(output_path)

    assert alignment["ink_bbox"] is not None
    assert alignment["canvas_width"] == 160
    assert alignment["canvas_height"] == 90
    assert abs(alignment["horizontal_center_offset_px"]) <= 2.0
    assert abs(alignment["vertical_center_offset_px"]) <= 2.0


def test_render_layout_preview_recenters_visible_ink_when_font_bbox_is_unbalanced(tmp_path: Path):
    font_path = _find_font_with_visible_ink_offset()
    output_path = tmp_path / "preview.png"
    layout = search_fitting_layout(
        "街头演出？",
        font_path,
        (375, 342),
        min_font_size=72,
        max_font_size=72,
        orientation="horizontal",
    )

    render_layout_preview(layout, font_path, output_path, canvas_size=(375, 342))
    alignment = measure_preview_alignment(output_path)

    assert alignment["ink_bbox"] is not None
    assert abs(alignment["horizontal_center_offset_px"]) <= 2.0


def test_render_layout_preview_supports_vertical_text(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    output_path = tmp_path / "vertical-preview.png"
    layout = search_fitting_layout("街头演出？", font_path, (90, 220), max_font_size=42)

    result = render_layout_preview(layout, font_path, output_path, canvas_size=(90, 220))

    assert result == output_path
    with Image.open(output_path) as image:
        assert image.mode == "RGBA"
        assert image.getbbox() is not None
        assert layout.orientation == "vertical"


def test_render_layout_preview_supports_vertical_text_columns(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    output_path = tmp_path / "vertical-columns.png"
    layout = search_fitting_layout(
        "是的\n我想刚开始还是这样比较好",
        font_path,
        (48, 188),
        min_font_size=12,
        max_font_size=18,
        orientation="vertical",
    )

    render_layout_preview(layout, font_path, output_path, canvas_size=(48, 188))
    alignment = measure_preview_alignment(output_path)

    assert alignment["ink_bbox"] is not None
    assert alignment["ink_width"] > 12
    assert alignment["ink_height"] <= 188


def test_render_layout_preview_applies_layout_angle(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    base_path = tmp_path / "angle-0.png"
    rotated_path = tmp_path / "angle-20.png"
    layout = search_fitting_layout("街头演出？", font_path, (180, 100), max_font_size=42)

    render_layout_preview(layout, font_path, base_path, canvas_size=(180, 100))
    render_layout_preview(replace(layout, angle_degrees=20.0), font_path, rotated_path, canvas_size=(180, 100))

    with Image.open(base_path) as base, Image.open(rotated_path) as rotated:
        assert ImageChops.difference(base, rotated).getbbox() is not None


def test_run_phase4_writes_layout_results_and_previews(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (90, 44), "white").save(source_crop_path)
    phase3_run = tmp_path / "phase3-selection"
    phase3_run.mkdir()
    _write_font_selection(phase3_run / "font-selections.jsonl", font_path, source_crop_path)

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "layout-results.jsonl")
    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "layout_generated"
    assert rows[0]["layout"]["font_size"] >= 12
    assert rows[0]["layout"]["orientation"] == "horizontal"
    assert rows[0]["layout"]["target_width"] == 90
    assert rows[0]["layout"]["target_height"] == 44
    assert rows[0]["layout"]["validation"]["status"] == "deterministic_only"
    assert rows[0]["layout"]["alignment"]["ink_bbox"] is not None
    assert abs(rows[0]["layout"]["alignment"]["horizontal_center_offset_px"]) <= 2.0
    assert Path(rows[0]["layout"]["preview_path"]).exists()
    assert (run_dir / "reports" / "phase4-report.md").exists()


def test_run_phase4_uses_angle_run_orientation_and_angle(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (90, 220), "white").save(source_crop_path)
    phase3_run = tmp_path / "phase3-selection"
    phase5_run = tmp_path / "phase5-angle"
    phase3_run.mkdir()
    phase5_run.mkdir()
    _write_font_selection(phase3_run / "font-selections.jsonl", font_path, source_crop_path)
    _write_angle_result(phase5_run / "angle-results.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        angle_run_dir=phase5_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-angle-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "layout-results.jsonl")
    assert rows[0]["layout"]["orientation"] == "vertical"
    assert rows[0]["layout"]["angle_degrees"] == -12.5
    assert Path(rows[0]["layout"]["preview_path"]).exists()


def test_run_phase4_can_use_tight_detection_text_bbox_for_layout_target(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (375, 342), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    phase2_run.mkdir()
    phase3_run.mkdir()
    _write_font_selection(phase3_run / "font-selections.jsonl", font_path, source_crop_path)
    _write_detection_with_tight_candidates(phase2_run / "detections.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-tight-target",
        sample_limit=1,
    )

    row = _read_jsonl(run_dir / "layout-results.jsonl")[0]
    layout = row["layout"]
    assert layout["target_bbox"] == [799, 145, 874, 300]
    assert layout["target_width"] == 75
    assert layout["target_height"] == 155
    assert layout["orientation"] == "vertical"
    assert layout["font_size"] < 72


def test_run_phase4_prefers_tight_target_orientation_over_stale_angle(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (375, 342), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    phase5_run = tmp_path / "phase5-angle"
    for path in [phase2_run, phase3_run, phase5_run]:
        path.mkdir()
    _write_font_selection(phase3_run / "font-selections.jsonl", font_path, source_crop_path)
    _write_detection_with_tight_candidates(phase2_run / "detections.jsonl")
    _write_horizontal_angle_result(phase5_run / "angle-results.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        angle_run_dir=phase5_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-target-orientation",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [799, 145, 874, 300]
    assert layout["orientation"] == "vertical"
    assert layout["angle_degrees"] == 0.0


def test_run_phase4_ignores_low_confidence_rotation_angle(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (375, 342), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    phase5_run = tmp_path / "phase5-angle"
    for path in [phase2_run, phase3_run, phase5_run]:
        path.mkdir()
    _write_font_selection(phase3_run / "font-selections.jsonl", font_path, source_crop_path)
    _write_detection_with_tight_candidates(phase2_run / "detections.jsonl")
    _write_low_confidence_vertical_angle_result(phase5_run / "angle-results.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        angle_run_dir=phase5_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-low-confidence-angle",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["orientation"] == "vertical"
    assert layout["angle_degrees"] == 0.0


def test_run_phase4_prefers_high_confidence_angle_orientation_for_wide_multicolumn_text(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (260, 160), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    phase5_run = tmp_path / "phase5-angle"
    for path in [phase2_run, phase3_run, phase5_run]:
        path.mkdir()
    _write_font_selection(phase3_run / "font-selections.jsonl", font_path, source_crop_path)
    _write_detection_with_wide_multicolumn_target(phase2_run / "detections.jsonl")
    _write_high_confidence_vertical_angle_result(phase5_run / "angle-results.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        angle_run_dir=phase5_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-angle-orientation-priority",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [50, 40, 250, 170]
    assert layout["orientation"] == "vertical"
    assert layout["angle_degrees"] == 1.5


def test_run_phase4_expands_tight_target_inside_selected_box_when_layout_overflows(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (260, 240), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    phase5_run = tmp_path / "phase5-angle"
    for path in [phase2_run, phase3_run, phase5_run]:
        path.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        translated_text="这是一段很长的测试文字\n这也是另一段很长文字",
    )
    _write_detection_with_short_tight_target(phase2_run / "detections.jsonl")
    _write_high_confidence_vertical_angle_result(phase5_run / "angle-results.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        angle_run_dir=phase5_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-expand-tight-target",
        sample_limit=1,
    )

    row = _read_jsonl(run_dir / "layout-results.jsonl")[0]
    layout = row["layout"]
    assert row["status"] == "layout_generated"
    assert layout["target_bbox"][3] > 160
    assert layout["target_bbox"][3] <= 220
    assert layout["target_bbox"][0] >= 20
    assert layout["target_bbox"][2] <= 230
    assert layout["orientation"] == "vertical"


def test_run_phase4_caps_short_vertical_text_to_source_column_width(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (375, 342), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    for path in [phase2_run, phase3_run]:
        path.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        translated_text="锵~锵",
    )
    _write_detection_with_tight_candidates(phase2_run / "detections.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-short-vertical-cap",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [799, 145, 874, 300]
    assert layout["orientation"] == "vertical"
    assert layout["font_size"] <= 48


def test_run_phase4_keeps_short_vertical_translation_close_to_source_glyph_width(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (120, 160), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    for path in [phase2_run, phase3_run]:
        path.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        translated_text="循环器",
    )
    _write_detection_like_gbc06_02_record_8(phase2_run / "detections.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-short-vertical-source-scale",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [725, 1001, 802, 1128]
    assert layout["orientation"] == "vertical"
    assert layout["font_size"] <= 38


def test_run_phase4_renders_light_text_for_light_on_dark_detection(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (120, 90), "black").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    phase2_run.mkdir()
    phase3_run.mkdir()
    _write_font_selection(phase3_run / "font-selections.jsonl", font_path, source_crop_path)
    _write_light_on_dark_detection(phase2_run / "detections.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-light-text",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["text_color"] == [255, 255, 255, 255]
    with Image.open(layout["preview_path"]).convert("RGBA") as preview:
        bbox = preview.getchannel("A").getbbox()
        assert bbox is not None
        x = (bbox[0] + bbox[2]) // 2
        y = (bbox[1] + bbox[3]) // 2
        assert preview.getpixel((x, y))[:3] == (255, 255, 255)


def test_run_phase4_filters_selected_fonts_by_record_id_before_sample_limit(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (90, 44), "white").save(source_crop_path)
    phase3_run = tmp_path / "phase3-selection"
    phase3_run.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        record_ids=["page.png#1", "page.png#2"],
    )

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-filter-test",
        sample_limit=1,
        record_ids=["page.png#2"],
    )

    rows = _read_jsonl(run_dir / "layout-results.jsonl")
    assert [row["record_id"] for row in rows] == ["page.png#2"]


def _copy_font(tmp_path: Path) -> Path:
    source = sorted(Path("C:/Windows/Fonts").glob("*.ttf"))[0]
    target = tmp_path / source.name
    target.write_bytes(source.read_bytes())
    return target


def _find_font_with_visible_ink_offset() -> Path:
    candidates = [
        Path("C:/Windows/Fonts/[toolbox]韩敏小楷-简繁(v2.4).ttf"),
        Path("C:/Windows/Fonts/[toolbox]宋体-简繁-Regular(v2.4).ttf"),
        Path("C:/Windows/Fonts/[toolbox]黑体-简繁-DemiBold(v2.5).ttf"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return sorted(Path("C:/Windows/Fonts").glob("*.ttf"))[0]


def _write_font_selection(
    path: Path,
    font_path: Path,
    source_crop_path: Path,
    record_ids: list[str] | None = None,
    translated_text: str = "街头演出？",
) -> None:
    rows = []
    for record_id in record_ids or ["page.png#1"]:
        rows.append(
            {
                "record_id": record_id,
                "image_name": "page.png",
                "translated_text": translated_text,
                "status": "selected",
                "selected_font_id": "font-test",
                "selected_font": {"font_id": "font-test", "path": str(font_path), "family_name": "Test"},
                "source_crop_path": str(source_crop_path),
                "comparison_image_path": str(path.parent / "comparison.png"),
            }
        )
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_angle_result(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "angle_estimated",
        "orientation": {
            "detected_orientation": "vertical",
            "selected_angle_degrees": -12.5,
            "confidence": 0.9,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_horizontal_angle_result(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "angle_estimated",
        "orientation": {
            "detected_orientation": "horizontal",
            "selected_angle_degrees": -10.4,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_high_confidence_vertical_angle_result(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "angle_estimated",
        "orientation": {
            "detected_orientation": "vertical",
            "selected_angle_degrees": 1.5,
            "confidence": 0.86,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_low_confidence_vertical_angle_result(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "angle_estimated",
        "orientation": {
            "detected_orientation": "vertical",
            "selected_angle_degrees": -22.7,
            "confidence": 0.67,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_detection_with_tight_candidates(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "selected_text_box_xyxy": [674, 0, 1049, 342],
        "candidate_boxes": [
            {"xyxy": [674, 0, 1049, 342], "area": 87035},
            {"xyxy": [840, 145, 874, 300], "area": 3858},
            {"xyxy": [799, 145, 837, 271], "area": 3481},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_detection_with_wide_multicolumn_target(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "selected_text_box_xyxy": [0, 0, 280, 200],
        "candidate_boxes": [
            {"xyxy": [50, 40, 75, 170], "area": 3250},
            {"xyxy": [105, 40, 130, 170], "area": 3250},
            {"xyxy": [225, 40, 250, 170], "area": 3250},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_detection_with_short_tight_target(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "selected_text_box_xyxy": [20, 20, 230, 220],
        "candidate_boxes": [
            {"xyxy": [20, 20, 230, 220], "area": 42000, "score": 0.99},
            {"xyxy": [80, 40, 105, 160], "area": 3000, "score": 0.95},
            {"xyxy": [125, 40, 150, 160], "area": 3000, "score": 0.94},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_detection_like_gbc06_02_record_8(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "search_region_xyxy": [594, 903, 1034, 1263],
        "selected_text_box_xyxy": [764, 1001, 802, 1094],
        "candidate_boxes": [
            {"xyxy": [764, 1001, 802, 1094], "area": 2206, "score": 0.9378, "polarity": "dark_on_light"},
            {"xyxy": [725, 1002, 761, 1128], "area": 3221, "score": 0.9034, "polarity": "dark_on_light"},
            {"xyxy": [793, 903, 893, 959], "area": 4520, "score": 0.7959, "polarity": "dark_on_light"},
            {"xyxy": [594, 903, 679, 1263], "area": 13599, "score": 0.7658, "polarity": "dark_on_light"},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_light_on_dark_detection(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "selected_text_box_xyxy": [10, 10, 110, 90],
        "candidate_boxes": [
            {"xyxy": [10, 10, 110, 90], "area": 8000, "score": 0.95, "polarity": "light_on_dark"},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
