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


def _write_font_selection(path: Path, font_path: Path, source_crop_path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "街头演出？",
        "status": "selected",
        "selected_font_id": "font-test",
        "selected_font": {"font_id": "font-test", "path": str(font_path), "family_name": "Test"},
        "source_crop_path": str(source_crop_path),
        "comparison_image_path": str(path.parent / "comparison.png"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_angle_result(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "angle_estimated",
        "orientation": {
            "detected_orientation": "vertical",
            "selected_angle_degrees": -12.5,
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


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
