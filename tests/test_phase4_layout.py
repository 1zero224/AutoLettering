import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

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


def test_search_fitting_layout_prefers_single_line_for_short_horizontal_title(tmp_path: Path):
    font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="新川崎（暂）",
        font_path=font_path,
        target_size=(116, 57),
        min_font_size=12,
        max_font_size=48,
        orientation="horizontal",
    )

    assert "\n" not in result.line_breaks
    assert result.orientation == "horizontal"
    assert result.status == "ok"


def test_search_fitting_layout_prefers_single_line_for_short_horizontal_title_with_toolbox_font(tmp_path: Path):
    font_path = Path("D:/work/autolettering/工具箱漫画字体V2.5/[toolbox]伪角明-简体-Bold(v2.4).ttf")
    if not font_path.exists():
        font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="新川崎（暂）",
        font_path=font_path,
        target_size=(116, 57),
        min_font_size=12,
        max_font_size=48,
        orientation="horizontal",
    )

    assert "\n" not in result.line_breaks
    assert result.orientation == "horizontal"
    assert result.status == "ok"


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


def test_search_fitting_layout_prefers_phrase_preserving_vertical_breaks_over_larger_split_text(tmp_path: Path):
    font_path = Path("D:/work/autolettering/工具箱漫画字体V2.5/[toolbox]伪角明-简体-Bold(v2.4).ttf")
    if not font_path.exists():
        font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="-快看\n接下来登场的乐队\n竟然！",
        font_path=font_path,
        target_size=(115, 192),
        min_font_size=12,
        max_font_size=33,
        orientation="vertical",
    )

    assert result.status == "ok"
    assert result.line_breaks == "-快看\n接下来登场的乐队\n竟然！"
    assert "接下\n来" not in result.line_breaks
    assert result.font_size <= 25
    assert result.overflow_ratio == 0.0


def test_search_fitting_layout_accepts_min_font_bounded_overflow(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    measured = measure_text_layout("所谓的街头表演\n就是在别人面前唱歌吗？", font_path, 12, orientation="vertical")
    target_height = measured.height - max(1, int(round(measured.height * 0.04)))

    result = search_fitting_layout(
        text="所谓的街头表演\n就是在别人面前唱歌吗？",
        font_path=font_path,
        target_size=(measured.width, target_height),
        min_font_size=12,
        max_font_size=12,
        allow_overflow_ratio=0.08,
        max_lines=1,
        orientation="vertical",
    )

    assert result.status == "ok"
    assert 0.0 < result.overflow_ratio <= 0.08


def test_search_fitting_layout_reflows_long_vertical_text_into_more_columns(tmp_path: Path):
    font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="所谓的街头表演\n就是在别人面前唱歌吗？",
        font_path=font_path,
        target_size=(112, 159),
        min_font_size=12,
        max_font_size=36,
        orientation="vertical",
    )

    assert result.status == "ok"
    assert result.font_size > 12
    assert result.line_breaks.count("\n") >= 2


def test_search_fitting_layout_keeps_short_vertical_text_single_column(tmp_path: Path):
    font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="那是必然的",
        font_path=font_path,
        target_size=(73, 96),
        min_font_size=12,
        max_font_size=30,
        orientation="vertical",
    )

    assert result.status == "ok"
    assert "\n" not in result.line_breaks


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


def test_render_layout_preview_defaults_vertical_text_to_top_align(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    output_path = tmp_path / "vertical-top-default.png"
    layout = search_fitting_layout(
        "街头演出？",
        font_path,
        (90, 260),
        min_font_size=24,
        max_font_size=24,
        orientation="vertical",
    )

    render_layout_preview(layout, font_path, output_path, canvas_size=(90, 260))
    alignment = measure_preview_alignment(output_path)

    assert alignment["ink_bbox"] is not None
    assert alignment["ink_bbox"][1] <= 2
    assert alignment["vertical_center_offset_px"] < -20


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


def test_render_layout_preview_can_switch_vertical_column_order(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    layout = search_fitting_layout(
        "昴也好\n仁菜也好",
        font_path,
        (85, 128),
        min_font_size=31,
        max_font_size=31,
        orientation="vertical",
    )
    rtl_path = tmp_path / "vertical-rtl.png"
    ltr_path = tmp_path / "vertical-ltr.png"

    render_layout_preview(layout, font_path, rtl_path, canvas_size=(85, 128), vertical_column_order="rtl")
    render_layout_preview(layout, font_path, ltr_path, canvas_size=(85, 128), vertical_column_order="ltr")

    with Image.open(rtl_path) as rtl, Image.open(ltr_path) as ltr:
        assert ImageChops.difference(rtl, ltr).getbbox() is not None


def test_render_layout_preview_rejects_unknown_vertical_column_order(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    layout = search_fitting_layout("昴也好\n仁菜也好", font_path, (85, 128), orientation="vertical")

    with pytest.raises(ValueError, match="vertical_column_order"):
        render_layout_preview(layout, font_path, tmp_path / "bad.png", vertical_column_order="middle")


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


def test_run_phase4_ignores_high_confidence_micro_rotation_angle(tmp_path: Path):
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
    _write_micro_angle_result(phase5_run / "angle-results.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        angle_run_dir=phase5_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-micro-angle",
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
    assert layout["angle_degrees"] == 5.0


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
        translated_text="这是一段很长的测试文字这也是另一段很长文字还要更多内容\n第二列也继续补充更多测试内容",
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


def test_run_phase4_uses_body_bbox_below_diamond_for_decorated_caption(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (58, 170), "white").save(source_crop_path)
    phase3_run = tmp_path / "phase3"
    phase3_run.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        translated_text="来自桃香的唐突的提案",
    )
    phase2_run = tmp_path / "phase2"
    phase2_run.mkdir()
    _write_decorated_caption_detection(phase2_run / "detections.jsonl", tmp_path / "page.png")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-decorated-caption",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [10, 80, 68, 250]
    assert layout["orientation"] == "vertical"
    assert layout["vertical_align"] == "top"
    assert layout["alignment"]["ink_bbox"][1] <= 2
    assert layout["alignment"]["ink_height"] < layout["target_height"]


def test_run_phase4_prefers_phase2_full_bbox_for_plain_multicolumn_bubble(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (193, 159), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2"
    phase3_run = tmp_path / "phase3"
    phase5_run = tmp_path / "phase5"
    phase2_run.mkdir()
    phase3_run.mkdir()
    phase5_run.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        translated_text="毫无保留地\n只要把现在的感受\n唱出来就好了",
    )
    _write_plain_multicolumn_bubble_detection_with_phase2_bboxes(phase2_run / "detections.jsonl")
    _write_micro_angle_result(phase5_run / "angle-results.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        angle_run_dir=phase5_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-plain-multicolumn-bubble",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [557, 490, 750, 649]
    assert layout["target_width"] == 193
    assert layout["target_height"] == 159
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


def test_run_phase4_caps_very_short_vertical_translation_below_source_glyph_width(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (90, 120), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    phase5_run = tmp_path / "phase5-angle"
    for path in [phase2_run, phase3_run, phase5_run]:
        path.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        translated_text="诶？",
    )
    _write_detection_like_gbc06_02_record_10(phase2_run / "detections.jsonl")
    _write_micro_angle_result(phase5_run / "angle-results.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        angle_run_dir=phase5_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-very-short-vertical-source-scale",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [343, 1215, 381, 1302]
    assert layout["orientation"] == "vertical"
    assert layout["angle_degrees"] == 0.0
    assert layout["vertical_align"] == "top"
    assert layout["alignment"]["ink_bbox"][1] <= 2
    assert layout["font_size"] <= 34


def test_run_phase4_caps_multicolumn_vertical_translation_below_source_column_width(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (90, 220), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2-detection"
    phase3_run = tmp_path / "phase3-selection"
    for path in [phase2_run, phase3_run]:
        path.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        translated_text="那个\n莫非是要…",
    )
    _write_detection_like_gbc06_02_record_11(phase2_run / "detections.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-multicolumn-vertical-cap",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [157, 1158, 230, 1347]
    assert layout["orientation"] == "vertical"
    assert layout["font_size"] <= 31


def test_run_phase4_uses_mask_bbox_for_overlapping_bubble_layout_target(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    source_crop_path = tmp_path / "source-crop.png"
    Image.new("RGB", (225, 286), "white").save(source_crop_path)
    phase2_run = tmp_path / "phase2"
    phase3_run = tmp_path / "phase3"
    phase2_run.mkdir()
    phase3_run.mkdir()
    _write_font_selection(
        phase3_run / "font-selections.jsonl",
        font_path,
        source_crop_path,
        translated_text="-快看\n接下来登场的乐队\n竟然！",
    )
    _write_detection_like_gbc06_18_record_3(phase2_run / "detections.jsonl")

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        detection_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-gbc06-18-mask-layout",
        sample_limit=1,
    )

    layout = _read_jsonl(run_dir / "layout-results.jsonl")[0]["layout"]
    assert layout["target_bbox"] == [1197, 1335, 1312, 1527]
    assert layout["target_width"] == 115
    assert layout["target_height"] == 192
    assert layout["orientation"] == "vertical"


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
            "selected_angle_degrees": 5.0,
            "confidence": 0.86,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_micro_angle_result(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "angle_estimated",
        "orientation": {
            "detected_orientation": "vertical",
            "selected_angle_degrees": 2.4,
            "confidence": 0.88,
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


def _write_decorated_caption_detection(path: Path, image_path: Path) -> None:
    image = Image.new("RGB", (80, 280), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([(39, 16), (64, 41), (39, 66), (14, 41)], fill="black")
    for y in (80, 126, 172, 218):
        draw.rectangle((24, y, 54, y + 6), fill="black")
        draw.rectangle((36, y, 42, y + 30), fill="black")
    image.save(image_path)
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "group_name": "框外",
        "selected_text_box_xyxy": [10, 10, 68, 250],
        "candidate_boxes": [
            {"xyxy": [10, 10, 68, 250], "score": 0.95, "polarity": "dark_on_light"},
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


def _write_detection_like_gbc06_02_record_10(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "search_region_xyxy": [177, 1116, 617, 1476],
        "selected_text_box_xyxy": [177, 1116, 617, 1376],
        "candidate_boxes": [
            {"xyxy": [177, 1116, 617, 1376], "area": 44005, "score": 0.934, "polarity": "dark_on_light"},
            {"xyxy": [350, 1243, 380, 1302], "area": 1184, "score": 0.8939, "polarity": "dark_on_light"},
            {"xyxy": [343, 1215, 381, 1243], "area": 696, "score": 0.7528, "polarity": "dark_on_light"},
            {"xyxy": [338, 1209, 387, 1308], "area": 3682, "score": 0.9328, "polarity": "light_on_dark"},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_detection_like_gbc06_02_record_11(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "search_region_xyxy": [13, 1051, 453, 1411],
        "selected_text_box_xyxy": [196, 1158, 230, 1222],
        "candidate_boxes": [
            {"xyxy": [196, 1158, 230, 1222], "area": 1796, "score": 0.9398, "polarity": "dark_on_light"},
            {"xyxy": [157, 1158, 191, 1347], "area": 3908, "score": 0.9172, "polarity": "dark_on_light"},
            {"xyxy": [350, 1243, 380, 1302], "area": 1184, "score": 0.7637, "polarity": "dark_on_light"},
            {"xyxy": [116, 1402, 453, 1411], "area": 3033, "score": 0.7587, "polarity": "dark_on_light"},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_detection_like_gbc06_18_record_3(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "group_name": "框内",
        "search_region_xyxy": [1049, 1168, 1440, 1768],
        "selected_text_box_xyxy": [1237, 1337, 1273, 1527],
        "candidate_boxes": [
            {"xyxy": [1237, 1337, 1273, 1527], "area": 5383, "score": 0.932, "polarity": "dark_on_light"},
            {"xyxy": [1191, 1329, 1317, 1533], "area": 17522, "score": 0.9306, "polarity": "light_on_dark"},
            {"xyxy": [1277, 1335, 1312, 1435], "area": 2342, "score": 0.9118, "polarity": "dark_on_light"},
            {"xyxy": [1197, 1337, 1233, 1463], "area": 3087, "score": 0.8785, "polarity": "dark_on_light"},
            {"xyxy": [1127, 1464, 1164, 1561], "area": 2813, "score": 0.8225, "polarity": "dark_on_light"},
            {"xyxy": [1087, 1464, 1125, 1621], "area": 3745, "score": 0.7735, "polarity": "dark_on_light"},
            {"xyxy": [1049, 1692, 1369, 1768], "area": 17534, "score": 0.7063, "polarity": "light_on_dark"},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_plain_multicolumn_bubble_detection_with_phase2_bboxes(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "group_name": "框内",
        "selected_text_box_xyxy": [713, 491, 750, 619],
        "selected_text_full_xyxy": [557, 490, 750, 649],
        "selected_text_body_xyxy": [557, 490, 750, 649],
        "candidate_boxes": [
            {"xyxy": [713, 491, 750, 619], "area": 3603, "score": 0.9541, "polarity": "dark_on_light"},
            {"xyxy": [673, 490, 711, 649], "area": 4334, "score": 0.9171, "polarity": "dark_on_light"},
            {"xyxy": [636, 493, 670, 619], "area": 3298, "score": 0.8901, "polarity": "dark_on_light"},
            {"xyxy": [595, 490, 632, 587], "area": 2883, "score": 0.8575, "polarity": "dark_on_light"},
            {"xyxy": [557, 525, 591, 649], "area": 2985, "score": 0.8099, "polarity": "dark_on_light"},
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
