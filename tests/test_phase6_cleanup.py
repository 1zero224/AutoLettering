import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from autolettering.inpaint.bubble_fill import fill_text_box, mask_fill_text_pixels, region_fill_text_area, sample_border_color
from autolettering.phase6 import run_phase6_bubble_cleanup
from autolettering.phase6 import _text_bbox


def test_sample_border_color_uses_pixels_around_bbox(tmp_path: Path):
    image = Image.new("RGB", (80, 80), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 60, 60), fill="black")
    image_path = tmp_path / "page.png"
    image.save(image_path)

    color = sample_border_color(image_path, (20, 20, 60, 60), inset=2)

    assert all(channel >= 240 for channel in color)


def test_fill_text_box_writes_cleaned_crop_and_before_after(tmp_path: Path):
    image = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(image).rectangle((40, 30, 60, 70), fill="black")
    image_path = tmp_path / "page.png"
    image.save(image_path)

    result = fill_text_box(
        image_path=image_path,
        bbox=(35, 25, 65, 75),
        output_dir=tmp_path / "cleanup",
        record_id="page.png#1",
    )

    assert result.cleaned_crop_path.exists()
    assert result.before_after_path.exists()
    with Image.open(result.cleaned_crop_path) as cleaned:
        assert ImageChops.difference(cleaned.convert("RGB"), Image.new("RGB", cleaned.size, "white")).getbbox() is None


def test_mask_fill_text_pixels_preserves_dark_art_outside_text_mask(tmp_path: Path):
    image = Image.new("RGB", (120, 90), "white")
    draw = ImageDraw.Draw(image)
    draw.line((10, 10, 110, 10), fill="black", width=3)
    draw.rectangle((48, 35, 72, 60), fill="black")
    image_path = tmp_path / "page.png"
    image.save(image_path)

    result = mask_fill_text_pixels(
        image_path=image_path,
        bbox=(0, 0, 120, 90),
        text_bbox=(45, 30, 75, 65),
        output_dir=tmp_path / "cleanup",
        record_id="page.png#1",
    )

    with Image.open(result.cleaned_crop_path) as cleaned:
        assert cleaned.convert("L").getpixel((60, 45)) > 240
        assert cleaned.convert("L").getpixel((30, 10)) < 40


def test_region_fill_text_area_removes_light_glyph_ghosts(tmp_path: Path):
    image = Image.new("RGB", (120, 90), "white")
    draw = ImageDraw.Draw(image)
    draw.line((10, 10, 110, 10), fill="black", width=3)
    draw.rectangle((48, 35, 72, 60), fill=(40, 40, 40))
    draw.rectangle((50, 62, 70, 68), fill=(226, 226, 226))
    image_path = tmp_path / "page.png"
    image.save(image_path)

    result = region_fill_text_area(
        image_path=image_path,
        bbox=(0, 0, 120, 90),
        text_bbox=(45, 30, 75, 72),
        output_dir=tmp_path / "cleanup",
        record_id="page.png#1",
        padding_px=2,
    )

    with Image.open(result.cleaned_crop_path) as cleaned:
        assert result.method == "bubble_region_fill"
        assert cleaned.convert("L").getpixel((60, 65)) > 245
        assert cleaned.convert("L").getpixel((30, 10)) < 40


def test_run_phase6_bubble_cleanup_writes_results_and_artifacts(tmp_path: Path):
    image_path = _write_sample_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    layout_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    _write_layout(layout_run / "layout-results.jsonl")

    run_dir = run_phase6_bubble_cleanup(
        detection_run_dir=detection_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "cleaned"
    assert rows[0]["cleanup"]["method"] == "bubble_region_fill"
    assert Path(rows[0]["cleanup"]["cleaned_crop_path"]).exists()
    assert Path(rows[0]["cleanup"]["before_after_path"]).exists()
    assert (run_dir / "reports" / "phase6-report.md").exists()


def test_run_phase6_bubble_cleanup_expands_crop_to_full_text_bbox(tmp_path: Path):
    image = Image.new("RGB", (160, 160), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((110, 45, 130, 95), fill="black")
    draw.rectangle((70, 45, 92, 125), fill="black")
    image_path = tmp_path / "page.png"
    image.save(image_path)
    detection_run = tmp_path / "phase2"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    layout_run.mkdir()
    _write_jsonl(
        detection_run / "detections.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "ok",
                "image_name": "page.png",
                "image_path": str(image_path),
                "group_name": "框内",
                "search_region_xyxy": [50, 30, 145, 135],
                "selected_text_box_xyxy": [110, 45, 130, 95],
                "candidate_boxes": [
                    {"xyxy": [110, 45, 130, 95], "area": 1000, "score": 0.95, "polarity": "dark_on_light"},
                    {"xyxy": [70, 45, 92, 125], "area": 1760, "score": 0.91, "polarity": "dark_on_light"},
                ],
            }
        ],
    )
    _write_layout(layout_run / "layout-results.jsonl")

    run_dir = run_phase6_bubble_cleanup(
        detection_run_dir=detection_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-expanded-crop",
        sample_limit=1,
    )

    cleanup = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]["cleanup"]
    assert cleanup["bbox"] == [70, 45, 130, 125]
    with Image.open(cleanup["cleaned_crop_path"]).convert("L") as cleaned:
        assert cleaned.size == (60, 80)
        assert cleaned.getpixel((10, 10)) > 245
        assert cleaned.getpixel((50, 10)) > 245


def test_run_phase6_bubble_cleanup_uses_actual_text_bbox_instead_of_large_selected_bbox(tmp_path: Path):
    image = Image.new("RGB", (220, 140), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 40, 80, 90), fill="black")
    draw.rectangle((150, 30, 190, 100), fill="black")
    image_path = tmp_path / "page.png"
    image.save(image_path)
    detection_run = tmp_path / "phase2"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    layout_run.mkdir()
    _write_jsonl(
        detection_run / "detections.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "ok",
                "image_name": "page.png",
                "image_path": str(image_path),
                "group_name": "框内",
                "search_region_xyxy": [0, 0, 200, 120],
                "selected_text_box_xyxy": [0, 0, 200, 120],
                "candidate_boxes": [
                    {"xyxy": [0, 0, 200, 120], "area": 24000, "score": 0.96, "polarity": "dark_on_light"},
                    {"xyxy": [50, 40, 80, 90], "area": 1500, "score": 0.92, "polarity": "dark_on_light"},
                ],
            }
        ],
    )
    _write_layout(layout_run / "layout-results.jsonl")

    run_dir = run_phase6_bubble_cleanup(
        detection_run_dir=detection_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-tight-crop",
        sample_limit=1,
    )

    cleanup = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]["cleanup"]
    assert cleanup["bbox"] == [50, 40, 80, 90]
    with Image.open(cleanup["cleaned_crop_path"]).convert("L") as cleaned:
        assert cleaned.size == (30, 50)
        assert cleaned.getpixel((15, 25)) > 245


def test_run_phase6_bubble_cleanup_can_keep_mask_fill_for_comparison(tmp_path: Path):
    image_path = _write_sample_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    layout_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    _write_layout(layout_run / "layout-results.jsonl")

    run_dir = run_phase6_bubble_cleanup(
        detection_run_dir=detection_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-mask-test",
        sample_limit=1,
        cleanup_method="mask_fill",
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["cleanup"]["method"] == "bubble_mask_fill"


def test_run_phase6_bubble_cleanup_filters_by_record_id_before_sample_limit(tmp_path: Path):
    image_path = _write_sample_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    layout_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path, record_ids=["page.png#1", "page.png#2"])
    _write_layout(layout_run / "layout-results.jsonl", record_ids=["page.png#1", "page.png#2"])

    run_dir = run_phase6_bubble_cleanup(
        detection_run_dir=detection_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-filter-test",
        sample_limit=1,
        record_ids=["page.png#2"],
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert [row["record_id"] for row in rows] == ["page.png#2"]
    assert rows[0]["status"] == "cleaned"


def test_text_bbox_unions_small_text_candidates_inside_large_detection():
    detection = {
        "selected_text_box_xyxy": [0, 0, 200, 200],
        "candidate_boxes": [
            {"xyxy": [0, 0, 200, 200], "area": 40000},
            {"xyxy": [60, 40, 90, 160], "area": 3600},
            {"xyxy": [105, 42, 135, 155], "area": 3390},
        ],
    }

    assert _text_bbox(detection) == (60, 40, 135, 160)


def _write_sample_image(path: Path) -> Path:
    image = Image.new("RGB", (120, 120), "white")
    ImageDraw.Draw(image).rectangle((42, 35, 72, 85), fill="black")
    image.save(path)
    return path


def _write_detection(path: Path, image_path: Path, record_ids: list[str] | None = None) -> None:
    rows = []
    for record_id in record_ids or ["page.png#1"]:
        rows.append(
            {
                "record_id": record_id,
                "status": "ok",
                "image_name": "page.png",
                "image_path": str(image_path),
                "group_name": "框内",
                "selected_text_box_xyxy": [35, 25, 80, 90],
                "candidate_boxes": [
                    {"xyxy": [42, 35, 72, 85], "area": 1500, "dark_pixel_count": 600},
                    {"xyxy": [35, 25, 80, 90], "area": 2925, "dark_pixel_count": 700},
                ],
            }
        )
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_layout(path: Path, record_ids: list[str] | None = None) -> None:
    rows = [
        {
            "record_id": record_id,
            "status": "layout_generated",
            "layout": {"preview_path": "unused.png"},
        }
        for record_id in record_ids or ["page.png#1"]
    ]
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
