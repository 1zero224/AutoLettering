import json
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from autolettering.assets.font_comparison import build_font_comparison_grid
from autolettering.assets.font_render import render_text_preview
from autolettering.assets.fonts import FontRecord, font_record_to_dict, scan_font_directory, select_font_candidates
from autolettering.phase3 import run_phase3


def _copy_test_font(tmp_path: Path) -> Path:
    fonts_root = Path("C:/Windows/Fonts")
    candidates = sorted(list(fonts_root.glob("*.ttf")) + list(fonts_root.glob("*.otf")))
    if not candidates:
        pytest.skip("No system TTF/OTF font available for font rendering tests")

    target = tmp_path / candidates[0].name
    shutil.copy2(candidates[0], target)
    return target


def _has_non_white_pixels(path: Path) -> bool:
    image = Image.open(path).convert("RGB")
    white = Image.new("RGB", image.size, "white")
    return ImageChops.difference(image, white).getbbox() is not None


def _font_record(font_id: str, style_hints: list[str], tmp_path: Path) -> FontRecord:
    return FontRecord(
        font_id=font_id,
        path=tmp_path / f"{font_id}.ttf",
        filename=f"{font_id}.ttf",
        family_name=font_id,
        postscript_name=f"{font_id}-PS",
        style_hints=style_hints,
        supports_sample_text=True,
        unsupported_chars=[],
    )


def test_scan_font_directory_reads_metadata_and_sample_coverage(tmp_path: Path):
    font_path = _copy_test_font(tmp_path)

    records = scan_font_directory(tmp_path, sample_text="ABC")

    assert len(records) == 1
    record = records[0]
    assert record.font_id
    assert record.path == font_path.resolve()
    assert record.filename == font_path.name
    assert record.family_name
    assert record.postscript_name
    assert font_record_to_dict(record)["postscript_name"] == record.postscript_name
    assert record.supports_sample_text is True
    assert record.unsupported_chars == []


def test_render_text_preview_writes_non_empty_image(tmp_path: Path):
    font_path = _copy_test_font(tmp_path)
    record = scan_font_directory(tmp_path, sample_text="ABC")[0]
    output_path = tmp_path / "preview.png"

    result = render_text_preview(record, "ABC", output_path, font_size=42)

    assert result == output_path
    assert output_path.exists()
    assert _has_non_white_pixels(output_path)


def test_select_font_candidates_prefers_distinct_primary_style_hints(tmp_path: Path):
    fonts = [
        _font_record("heiti-bold", ["黑体", "Bold"], tmp_path),
        _font_record("heiti-light", ["黑体", "Light"], tmp_path),
        _font_record("kaiti", ["楷体"], tmp_path),
        _font_record("yuanti", ["圆体"], tmp_path),
    ]

    selected = select_font_candidates(fonts, limit=3)

    assert [font.font_id for font in selected] == ["heiti-bold", "kaiti", "yuanti"]


def test_build_font_comparison_grid_writes_source_and_candidate_previews(tmp_path: Path):
    source_crop = tmp_path / "source.png"
    source_image = Image.new("RGB", (80, 120), "white")
    ImageDraw.Draw(source_image).rectangle((24, 20, 56, 100), fill="black")
    source_image.save(source_crop)

    preview_a = tmp_path / "a.png"
    preview_b = tmp_path / "b.png"
    Image.new("RGB", (120, 80), "white").save(preview_a)
    Image.new("RGB", (120, 80), "white").save(preview_b)
    output_path = tmp_path / "comparison.png"

    result = build_font_comparison_grid(
        source_crop_path=source_crop,
        candidates=[
            ("font-a", preview_a),
            ("font-b", preview_b),
        ],
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.exists()
    with Image.open(output_path) as grid:
        assert grid.width > 120
        assert grid.height > 120


def test_run_phase3_writes_font_index_comparisons_and_report(tmp_path: Path):
    font_dir = tmp_path / "fonts"
    font_dir.mkdir()
    _copy_test_font(font_dir)

    labelplus_file, detection_run = _write_phase3_fixture(tmp_path)

    run_dir = run_phase3(
        labelplus_file,
        detection_run_dir=detection_run,
        font_dir=font_dir,
        output_root=tmp_path / "outputs",
        run_id="phase3-test",
        sample_limit=1,
        font_limit=1,
    )

    assert (run_dir / "font-index.jsonl").exists()
    assert (run_dir / "font-comparisons.jsonl").exists()
    rows = [json.loads(line) for line in (run_dir / "font-comparisons.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "candidates_generated"
    assert Path(rows[0]["source_crop_path"]).exists()
    assert Path(rows[0]["comparison_image_path"]).exists()
    assert len(rows[0]["candidate_fonts"]) == 1
    assert Path(rows[0]["candidate_fonts"][0]["preview_path"]).exists()
    assert (run_dir / "reports" / "phase3-report.md").exists()


def test_run_phase3_filters_detections_by_record_id_before_sample_limit(tmp_path: Path):
    font_dir = tmp_path / "fonts"
    font_dir.mkdir()
    _copy_test_font(font_dir)
    labelplus_file, detection_run = _write_phase3_fixture(tmp_path)
    image_path = tmp_path / "sample_project" / "page.png"
    _write_sample_detection_file(
        detection_run / "detections.jsonl",
        image_path,
        record_ids=["page.png#1", "page.png#2"],
    )

    run_dir = run_phase3(
        labelplus_file,
        detection_run_dir=detection_run,
        font_dir=font_dir,
        output_root=tmp_path / "outputs",
        run_id="phase3-filter-test",
        sample_limit=1,
        font_limit=1,
        record_ids=["page.png#2"],
    )

    rows = [json.loads(line) for line in (run_dir / "font-comparisons.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["record_id"] for row in rows] == ["page.png#2"]


def test_run_phase3_crops_body_bbox_for_decorated_nonbubble_caption(tmp_path: Path):
    font_dir = tmp_path / "fonts"
    font_dir.mkdir()
    _copy_test_font(font_dir)
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = _write_decorated_caption_page(project_dir / "page.png")
    labelplus_file = project_dir / "翻译_0.txt"
    _write_sample_labelplus_file(labelplus_file)
    detection_run = tmp_path / "detections"
    detection_run.mkdir()
    row = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "translated_text": "标题文字",
        "group_name": "框外",
        "selected_text_box_xyxy": [10, 10, 68, 250],
        "candidate_boxes": [
            {"xyxy": [10, 10, 68, 250], "score": 0.95, "polarity": "dark_on_light"},
        ],
    }
    (detection_run / "detections.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    run_dir = run_phase3(
        labelplus_file,
        detection_run_dir=detection_run,
        font_dir=font_dir,
        output_root=tmp_path / "outputs",
        run_id="phase3-decorated-caption",
        sample_limit=1,
        font_limit=1,
    )

    rows = [json.loads(line) for line in (run_dir / "font-comparisons.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["source_text_bbox"] == [10, 80, 68, 250]
    with Image.open(rows[0]["source_crop_path"]) as crop:
        assert crop.size == (58, 170)


def _write_phase3_fixture(tmp_path: Path) -> tuple[Path, Path]:
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    image_path = _write_sample_page(project_dir)
    labelplus_file = project_dir / "翻译_0.txt"
    _write_sample_labelplus_file(labelplus_file)
    detection_run = tmp_path / "detections"
    detection_run.mkdir()
    _write_sample_detection_file(detection_run / "detections.jsonl", image_path)
    return labelplus_file, detection_run


def _write_sample_page(project_dir: Path) -> Path:
    image_path = project_dir / "page.png"
    image = Image.new("RGB", (240, 240), "white")
    ImageDraw.Draw(image).rectangle((88, 70, 118, 154), fill="black")
    image.save(image_path)
    return image_path


def _write_decorated_caption_page(path: Path) -> Path:
    image = Image.new("RGB", (80, 280), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([(39, 16), (64, 41), (39, 66), (14, 41)], fill="black")
    for y in (80, 126, 172, 218):
        draw.rectangle((24, y, 54, y + 6), fill="black")
        draw.rectangle((36, y, 42, y + 30), fill="black")
    image.save(path)
    return path


def _write_sample_labelplus_file(path: Path) -> None:
    path.write_text(
        """1,0
-
框内
-
Comment

>>>>>>>>[page.png]<<<<<<<<
----------------[1]----------------[0.425,0.458,1]
ABC
""",
        encoding="utf-8",
    )


def _write_sample_detection_file(path: Path, image_path: Path, record_ids: list[str] | None = None) -> None:
    rows = []
    for record_id in record_ids or ["page.png#1"]:
        rows.append(
            {
                "record_id": record_id,
                "status": "ok",
                "image_name": "page.png",
                "image_path": str(image_path),
                "translated_text": "ABC",
                "group_name": "框内",
                "selected_text_box_xyxy": [88, 70, 118, 154],
            }
        )
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
