import json
import csv
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from autolettering.phase7 import run_phase7_preview
from autolettering.rendering.compose import compose_page_preview, compose_page_records, compose_page_stages


def test_compose_page_preview_pastes_cleaned_crop_and_text_overlay(tmp_path: Path):
    image_path = tmp_path / "page.png"
    original = Image.new("RGB", (120, 100), "white")
    ImageDraw.Draw(original).rectangle((40, 20, 80, 70), fill="black")
    original.save(image_path)

    cleaned_crop = Image.new("RGB", (40, 50), "white")
    cleaned_crop_path = tmp_path / "cleaned.png"
    cleaned_crop.save(cleaned_crop_path)

    layout_preview = Image.new("RGBA", (40, 50), (255, 255, 255, 0))
    ImageDraw.Draw(layout_preview).rectangle((12, 18, 28, 32), fill=(0, 0, 0, 255))
    layout_preview_path = tmp_path / "layout.png"
    layout_preview.save(layout_preview_path)

    output_path = tmp_path / "preview.png"
    result = compose_page_preview(
        image_path=image_path,
        bbox=(40, 20, 80, 70),
        cleaned_crop_path=cleaned_crop_path,
        layout_preview_path=layout_preview_path,
        output_path=output_path,
    )

    assert result == output_path
    with Image.open(output_path).convert("RGB") as preview:
        assert preview.getpixel((50, 30)) == (255, 255, 255)
        assert preview.getpixel((60, 45)) == (0, 0, 0)
        assert ImageChops.difference(preview, original).getbbox() is not None


def test_compose_page_preview_can_place_text_in_smaller_overlay_bbox(tmp_path: Path):
    image_path = tmp_path / "page.png"
    original = Image.new("RGB", (120, 100), "white")
    ImageDraw.Draw(original).rectangle((40, 20, 100, 80), fill="black")
    original.save(image_path)

    cleaned_crop = Image.new("RGB", (60, 60), "white")
    cleaned_crop_path = tmp_path / "cleaned.png"
    cleaned_crop.save(cleaned_crop_path)
    layout_preview = Image.new("RGBA", (20, 30), (255, 255, 255, 0))
    ImageDraw.Draw(layout_preview).rectangle((6, 6, 14, 24), fill=(0, 0, 0, 255))
    layout_preview_path = tmp_path / "layout.png"
    layout_preview.save(layout_preview_path)

    output_path = tmp_path / "preview.png"
    compose_page_preview(
        image_path=image_path,
        bbox=(40, 20, 100, 80),
        cleaned_crop_path=cleaned_crop_path,
        layout_preview_path=layout_preview_path,
        output_path=output_path,
        text_bbox=(60, 30, 80, 60),
    )

    with Image.open(output_path).convert("RGB") as preview:
        assert preview.getpixel((50, 30)) == (255, 255, 255)
        assert preview.getpixel((68, 43)) == (0, 0, 0)
        assert preview.getpixel((90, 70)) == (255, 255, 255)


def test_compose_page_stages_applies_all_cleanups_before_text_overlays(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (80, 80), "white").save(image_path)
    cleaned_crop_path = _solid_rgb(tmp_path / "cleaned.png", (30, 30), "white")
    red_overlay_path = _solid_rgba(tmp_path / "red-text.png", (10, 10), (255, 0, 0, 255))
    transparent_overlay_path = _solid_rgba(tmp_path / "transparent-text.png", (10, 10), (255, 255, 255, 0))

    records = [
        {
            "bbox": [10, 10, 40, 40],
            "text_bbox": [20, 20, 30, 30],
            "cleaned_crop_path": str(cleaned_crop_path),
            "layout_preview_path": str(red_overlay_path),
        },
        {
            "bbox": [15, 15, 45, 45],
            "text_bbox": [50, 50, 60, 60],
            "cleaned_crop_path": str(cleaned_crop_path),
            "layout_preview_path": str(transparent_overlay_path),
        },
    ]

    outputs = compose_page_stages(
        image_path,
        records,
        tmp_path / "original.png",
        tmp_path / "cleaned-page.png",
        tmp_path / "final.png",
    )

    with Image.open(outputs["page_preview_path"]).convert("RGB") as final:
        assert final.getpixel((25, 25)) == (255, 0, 0)


def test_compose_page_records_applies_all_cleanups_before_text_overlays(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (80, 80), "white").save(image_path)
    cleaned_crop_path = _solid_rgb(tmp_path / "cleaned.png", (30, 30), "white")
    red_overlay_path = _solid_rgba(tmp_path / "red-text.png", (10, 10), (255, 0, 0, 255))
    transparent_overlay_path = _solid_rgba(tmp_path / "transparent-text.png", (10, 10), (255, 255, 255, 0))

    compose_page_records(
        image_path,
        [
            {
                "bbox": [10, 10, 40, 40],
                "text_bbox": [20, 20, 30, 30],
                "cleaned_crop_path": str(cleaned_crop_path),
                "layout_preview_path": str(red_overlay_path),
            },
            {
                "bbox": [15, 15, 45, 45],
                "text_bbox": [50, 50, 60, 60],
                "cleaned_crop_path": str(cleaned_crop_path),
                "layout_preview_path": str(transparent_overlay_path),
            },
        ],
        tmp_path / "records-preview.png",
    )

    with Image.open(tmp_path / "records-preview.png").convert("RGB") as final:
        assert final.getpixel((25, 25)) == (255, 0, 0)


def test_compose_page_records_can_apply_cleanup_crop_through_mask(tmp_path: Path):
    image_path = tmp_path / "page.png"
    source = Image.new("RGB", (80, 80), "white")
    ImageDraw.Draw(source).rectangle((20, 20, 30, 30), fill="black")
    source.save(image_path)

    first_cleaned = _solid_rgb(tmp_path / "first-cleaned.png", (30, 30), "white")
    first_mask = _solid_l(tmp_path / "first-mask.png", (30, 30), 255)
    second_cleaned = Image.new("RGB", (30, 30), "white")
    ImageDraw.Draw(second_cleaned).rectangle((5, 5, 15, 15), fill="black")
    second_cleaned_path = tmp_path / "second-cleaned.png"
    second_cleaned.save(second_cleaned_path)
    second_mask = _solid_l(tmp_path / "second-mask.png", (30, 30), 0)
    transparent_overlay_path = _solid_rgba(tmp_path / "transparent-text.png", (10, 10), (255, 255, 255, 0))

    compose_page_records(
        image_path,
        [
            {
                "bbox": [20, 20, 50, 50],
                "text_bbox": [60, 60, 70, 70],
                "cleaned_crop_path": str(first_cleaned),
                "cleanup_mask_path": str(first_mask),
                "layout_preview_path": str(transparent_overlay_path),
            },
            {
                "bbox": [15, 15, 45, 45],
                "text_bbox": [60, 60, 70, 70],
                "cleaned_crop_path": str(second_cleaned_path),
                "cleanup_mask_path": str(second_mask),
                "layout_preview_path": str(transparent_overlay_path),
            },
        ],
        tmp_path / "masked-preview.png",
    )

    with Image.open(tmp_path / "masked-preview.png").convert("RGB") as final:
        assert final.getpixel((25, 25)) == (255, 255, 255)


def test_run_phase7_preview_groups_multiple_records_on_one_page(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_detections(detection_run / "detections.jsonl", page_path)
    _write_cleanups(cleanup_run / "cleanup-results.jsonl", tmp_path)
    _write_layouts(layout_run / "layout-results.jsonl", tmp_path)

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-test",
        sample_limit=2,
    )

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    assert len(rows) == 1
    assert rows[0]["image_name"] == "page.png"
    assert rows[0]["status"] == "page_preview_generated"
    assert [record["record_id"] for record in rows[0]["records"]] == ["page.png#1", "page.png#2"]
    preview_path = Path(rows[0]["preview"]["page_preview_path"])
    assert preview_path.exists()
    with Image.open(preview_path).convert("RGB") as preview:
        assert preview.getpixel((60, 45)) == (0, 0, 0)
        assert preview.getpixel((30, 25)) == (0, 0, 0)
    assert (run_dir / "reports" / "phase7-report.md").exists()


def test_run_phase7_preview_writes_page_stage_images(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_detections(detection_run / "detections.jsonl", page_path)
    _write_cleanups(cleanup_run / "cleanup-results.jsonl", tmp_path)
    _write_layouts(layout_run / "layout-results.jsonl", tmp_path)

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-stages",
        sample_limit=2,
    )

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    preview = rows[0]["preview"]
    original_path = Path(preview["original_page_path"])
    cleaned_path = Path(preview["cleaned_page_path"])
    final_path = Path(preview["page_preview_path"])
    assert original_path == run_dir / "pages" / "original" / "page-png.png"
    assert cleaned_path == run_dir / "pages" / "cleaned" / "page-png.png"
    assert final_path == run_dir / "pages" / "page-png.png"
    assert original_path.exists()
    assert cleaned_path.exists()

    with Image.open(page_path).convert("RGB") as source, Image.open(original_path).convert("RGB") as original:
        assert ImageChops.difference(source, original).getbbox() is None
    with Image.open(cleaned_path).convert("RGB") as cleaned, Image.open(final_path).convert("RGB") as final:
        assert cleaned.getpixel((60, 45)) == (255, 255, 255)
        assert cleaned.getpixel((30, 25)) == (255, 255, 255)
        assert final.getpixel((60, 45)) == (0, 0, 0)

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["pages"][0]["original_page_path"] == str(original_path)
    assert manifest["pages"][0]["cleaned_page_path"] == str(cleaned_path)
    report = (run_dir / "reports" / "phase7-report.md").read_text(encoding="utf-8")
    assert "- `pages/original/*.png`" in report
    assert "- `pages/cleaned/*.png`" in report


def test_run_phase7_preview_writes_page_debug_overlay(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_detections(detection_run / "detections.jsonl", page_path)
    _write_cleanups(cleanup_run / "cleanup-results.jsonl", tmp_path)
    _write_layouts(layout_run / "layout-results.jsonl", tmp_path)

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-debug-overlay",
        sample_limit=2,
    )

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    debug_path = Path(rows[0]["preview"]["debug_overlay_path"])
    assert debug_path == run_dir / "debug" / "page_overlays" / "page-png.png"
    assert debug_path.exists()
    with Image.open(rows[0]["preview"]["page_preview_path"]).convert("RGB") as final:
        with Image.open(debug_path).convert("RGB") as debug:
            assert debug.size == final.size
            assert ImageChops.difference(debug, final).getbbox() is not None
            assert debug.getpixel((40, 20)) == (255, 0, 0)

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["pages"][0]["debug_overlay_path"] == str(debug_path)
    report = (run_dir / "reports" / "phase7-report.md").read_text(encoding="utf-8")
    assert "- `debug/page_overlays/*.png`" in report


def test_run_phase7_preview_writes_run_manifest(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_detections(detection_run / "detections.jsonl", page_path)
    _write_cleanups(cleanup_run / "cleanup-results.jsonl", tmp_path)
    _write_layouts(layout_run / "layout-results.jsonl", tmp_path)

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-manifest",
        sample_limit=2,
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "autolettering.phase7.preview.v1"
    assert manifest["run_id"] == "phase7-manifest"
    assert manifest["inputs"]["detection_run_dir"] == str(detection_run)
    assert manifest["inputs"]["cleanup_run_dirs"] == [str(cleanup_run)]
    assert manifest["inputs"]["layout_run_dir"] == str(layout_run)
    assert manifest["summary"] == {"record_count": 2, "page_count": 1, "skipped_count": 0}
    assert manifest["artifacts"]["preview_results_jsonl"] == str(run_dir / "preview-results.jsonl")
    assert manifest["artifacts"]["manual_review_csv"] == str(run_dir / "reports" / "manual-review.csv")
    assert manifest["artifacts"]["phase7_report"] == str(run_dir / "reports" / "phase7-report.md")
    assert manifest["pages"][0]["image_name"] == "page.png"
    assert manifest["pages"][0]["page_preview_path"] == str(run_dir / "pages" / "page-png.png")
    assert [record["record_id"] for record in manifest["pages"][0]["records"]] == ["page.png#1", "page.png#2"]
    report = (run_dir / "reports" / "phase7-report.md").read_text(encoding="utf-8")
    assert "- `manifest.json`" in report


def test_run_phase7_preview_writes_manual_review_csv(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_detections(detection_run / "detections.jsonl", page_path)
    _write_cleanups(cleanup_run / "cleanup-results.jsonl", tmp_path)
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload("page.png#1", _write_layout_preview(tmp_path / "layout-1.png"))])

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-review",
        sample_limit=2,
    )

    rows = _read_csv(run_dir / "reports" / "manual-review.csv")
    assert [row["record_id"] for row in rows] == ["page.png#1", "page.png#2"]
    assert rows[0]["status"] == "page_preview_generated"
    assert rows[0]["image_name"] == "page.png"
    assert Path(rows[0]["page_preview_path"]).name == "page-png.png"
    assert Path(rows[0]["page_preview_path"]).parent.name == "pages"
    assert rows[0]["cleanup_method"] == "bubble_fill"
    assert rows[0]["cleanup_crop_path"].endswith("cleaned-1.png")
    assert rows[0]["layout_preview_path"].endswith("layout-1.png")
    assert rows[0]["preview_before_after_path"].endswith("page-png-1.png")
    assert rows[0]["failure_reason"] == ""
    assert rows[0]["manual_decision"] == ""
    assert rows[0]["review_notes"] == ""
    assert rows[1]["status"] == "skipped"
    assert rows[1]["failure_reason"] == "missing_layout"
    assert rows[1]["page_preview_path"] == ""
    assert rows[1]["preview_before_after_path"] == ""


def test_run_phase7_preview_writes_record_before_after_crops(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_detections(detection_run / "detections.jsonl", page_path)
    _write_cleanups(cleanup_run / "cleanup-results.jsonl", tmp_path)
    _write_layouts(layout_run / "layout-results.jsonl", tmp_path)

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-before-after",
        sample_limit=2,
    )

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    crop_path = Path(rows[0]["records"][0]["preview_before_after_path"])
    assert crop_path.exists()
    assert crop_path.parent.name == "before_after"
    with Image.open(crop_path).convert("RGB") as crop:
        assert crop.size == (80, 50)
        assert crop.getpixel((5, 5)) == (0, 0, 0)
        assert crop.getpixel((45, 5)) == (255, 255, 255)
        assert crop.getpixel((60, 25)) == (0, 0, 0)


def test_run_phase7_preview_uses_layout_target_bbox_for_text_overlay(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_jsonl(
        detection_run / "detections.jsonl",
        [_detection_payload("page.png#1", page_path, [40, 20, 100, 80])],
    )
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [_cleanup_payload("page.png#1", _write_cleaned_crop(tmp_path / "cleaned.png"), [40, 20, 100, 80])],
    )
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload_with_target_bbox(tmp_path)])

    run_dir = run_phase7_preview(detection_run, cleanup_run, layout_run, tmp_path / "outputs", "phase7-text-bbox", 1)

    row = _read_jsonl(run_dir / "preview-results.jsonl")[0]
    record = row["records"][0]
    assert record["bbox"] == [40, 20, 100, 80]
    assert record["text_bbox"] == [60, 30, 80, 60]
    with Image.open(row["preview"]["page_preview_path"]).convert("RGB") as preview:
        assert preview.getpixel((50, 30)) == (255, 255, 255)
        assert preview.getpixel((68, 43)) == (0, 0, 0)
        assert preview.getpixel((90, 70)) == (255, 255, 255)


def test_run_phase7_preview_prefers_cleanup_layout_text_bbox_for_text_overlay(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_jsonl(
        detection_run / "detections.jsonl",
        [_detection_payload("page.png#1", page_path, [40, 20, 100, 80])],
    )
    cleanup = _cleanup_payload("page.png#1", _write_cleaned_crop(tmp_path / "cleaned.png"), [40, 20, 100, 80])
    cleanup["cleanup"]["layout_text_bbox"] = [60, 30, 80, 60]
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [cleanup])
    layout = _layout_payload("page.png#1", _small_layout_preview(tmp_path))
    layout["layout"]["target_bbox"] = [40, 20, 100, 80]
    _write_jsonl(layout_run / "layout-results.jsonl", [layout])

    run_dir = run_phase7_preview(detection_run, cleanup_run, layout_run, tmp_path / "outputs", "phase7-cleanup-text-bbox", 1)

    row = _read_jsonl(run_dir / "preview-results.jsonl")[0]
    record = row["records"][0]
    assert record["bbox"] == [40, 20, 100, 80]
    assert record["text_bbox"] == [60, 30, 80, 60]
    with Image.open(row["preview"]["page_preview_path"]).convert("RGB") as preview:
        assert preview.getpixel((68, 43)) == (0, 0, 0)
        assert preview.getpixel((90, 70)) == (255, 255, 255)


def test_run_phase7_preview_merges_multiple_cleanup_runs(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run_a = tmp_path / "phase6-a"
    cleanup_run_b = tmp_path / "phase6-b"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run_a.mkdir()
    cleanup_run_b.mkdir()
    layout_run.mkdir()
    _write_detections(detection_run / "detections.jsonl", page_path)
    _write_jsonl(
        cleanup_run_a / "cleanup-results.jsonl",
        [_cleanup_payload("page.png#1", _write_cleaned_crop(tmp_path / "cleaned-1.png"), [40, 20, 80, 70])],
    )
    _write_jsonl(
        cleanup_run_b / "cleanup-results.jsonl",
        [_cleanup_payload("page.png#2", _write_cleaned_crop(tmp_path / "cleaned-2.png"), [10, 10, 50, 40])],
    )
    _write_layouts(layout_run / "layout-results.jsonl", tmp_path)

    run_dir = run_phase7_preview(
        detection_run,
        [cleanup_run_a, cleanup_run_b],
        layout_run,
        tmp_path / "outputs",
        "phase7-merged-cleanups",
        2,
    )

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    assert [record["record_id"] for record in rows[0]["records"]] == ["page.png#1", "page.png#2"]
    report = (run_dir / "reports" / "phase7-report.md").read_text(encoding="utf-8")
    assert str(cleanup_run_a) in report
    assert str(cleanup_run_b) in report


def test_run_phase7_preview_records_missing_layout_as_skipped(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    bbox = [40, 20, 80, 70]
    _write_jsonl(
        detection_run / "detections.jsonl",
        [_detection_payload("page.png#1", page_path, bbox)],
    )
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [_cleanup_payload("page.png#1", _write_cleaned_crop(tmp_path / "cleaned.png"), bbox)],
    )
    _write_jsonl(layout_run / "layout-results.jsonl", [])

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    assert rows == [_skipped_payload("page.png#1", "missing_layout")]
    report = (run_dir / "reports" / "phase7-report.md").read_text(encoding="utf-8")
    assert "- Records processed: 1" in report
    assert "- Page previews generated: 0" in report
    assert "- Skipped: 1" in report
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"] == {"record_count": 0, "page_count": 0, "skipped_count": 1}
    assert manifest["pages"] == []
    assert manifest["skipped_records"] == [_skipped_payload("page.png#1", "missing_layout")]


def test_run_phase7_preview_prefers_replacement_crop_when_available(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    bbox = [40, 20, 80, 70]
    replacement_path = tmp_path / "replacement.png"
    Image.new("RGB", (40, 50), "red").save(replacement_path)
    _write_jsonl(
        detection_run / "detections.jsonl",
        [_detection_payload("page.png#1", page_path, bbox)],
    )
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [_cleanup_payload("page.png#1", _write_cleaned_crop(tmp_path / "local.png"), bbox, replacement_path)],
    )
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload("page.png#1", _transparent_layout(tmp_path))])

    run_dir = run_phase7_preview(detection_run, cleanup_run, layout_run, tmp_path / "outputs", "phase7-replacement", 1)

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    assert rows[0]["records"][0]["cleanup_method"] == "gpt_image2_masked_edit"
    with Image.open(rows[0]["preview"]["page_preview_path"]).convert("RGB") as preview:
        assert preview.getpixel((50, 30)) == (255, 0, 0)


def test_run_phase7_preview_does_not_require_or_overlay_layout_for_gpt_direct_replacement(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    bbox = [40, 20, 80, 70]
    replacement_path = tmp_path / "replacement-with-text.png"
    replacement = Image.new("RGB", (40, 50), "red")
    ImageDraw.Draw(replacement).rectangle((12, 18, 28, 32), fill="blue")
    replacement.save(replacement_path)
    _write_jsonl(
        detection_run / "detections.jsonl",
        [_detection_payload("page.png#1", page_path, bbox, status="fallback_required")],
    )
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [_cleanup_payload("page.png#1", _write_cleaned_crop(tmp_path / "local.png"), bbox, replacement_path)],
    )
    _write_jsonl(layout_run / "layout-results.jsonl", [])

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-gpt-direct",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    assert rows[0]["status"] == "page_preview_generated"
    assert rows[0]["records"][0]["layout_preview_path"] == ""
    assert rows[0]["records"][0]["text_overlay_required"] is False
    with Image.open(rows[0]["preview"]["page_preview_path"]).convert("RGB") as preview:
        assert preview.getpixel((50, 30)) == (255, 0, 0)
        assert preview.getpixel((60, 45)) == (0, 0, 255)


def _write_page(path: Path) -> Path:
    image = Image.new("RGB", (120, 100), "white")
    ImageDraw.Draw(image).rectangle((40, 20, 80, 70), fill="black")
    ImageDraw.Draw(image).rectangle((10, 10, 50, 40), fill="black")
    image.save(path)
    return path


def _write_cleaned_crop(path: Path) -> Path:
    Image.new("RGB", (40, 50), "white").save(path)
    return path


def _solid_rgb(path: Path, size: tuple[int, int], color: str) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def _solid_rgba(path: Path, size: tuple[int, int], color: tuple[int, int, int, int]) -> Path:
    Image.new("RGBA", size, color).save(path)
    return path


def _solid_l(path: Path, size: tuple[int, int], value: int) -> Path:
    Image.new("L", size, value).save(path)
    return path


def _write_layout_preview(path: Path) -> Path:
    image = Image.new("RGBA", (40, 50), (255, 255, 255, 0))
    ImageDraw.Draw(image).rectangle((12, 18, 28, 32), fill=(0, 0, 0, 255))
    image.save(path)
    return path


def _write_detections(path: Path, page_path: Path) -> None:
    payloads = [
        _detection_payload("page.png#1", page_path, [40, 20, 80, 70]),
        _detection_payload("page.png#2", page_path, [10, 10, 50, 40]),
    ]
    _write_jsonl(path, payloads)


def _write_cleanups(path: Path, tmp_path: Path) -> None:
    payloads = [
        _cleanup_payload(
            "page.png#1",
            _write_cleaned_crop(tmp_path / "cleaned-1.png"),
            [40, 20, 80, 70],
        ),
        _cleanup_payload(
            "page.png#2",
            _write_cleaned_crop(tmp_path / "cleaned-2.png"),
            [10, 10, 50, 40],
        ),
    ]
    _write_jsonl(path, payloads)


def _write_layouts(path: Path, tmp_path: Path) -> None:
    payloads = [
        _layout_payload("page.png#1", _write_layout_preview(tmp_path / "layout-1.png")),
        _layout_payload("page.png#2", _write_layout_preview(tmp_path / "layout-2.png")),
    ]
    _write_jsonl(path, payloads)


def _detection_payload(record_id: str, page_path: Path, bbox: list[int], status: str = "ok") -> dict:
    return {
        "record_id": record_id,
        "status": status,
        "image_name": "page.png",
        "image_path": str(page_path),
        "selected_text_box_xyxy": bbox,
    }


def _cleanup_payload(record_id: str, cleaned_path: Path, bbox: list[int], replacement_path: Path | None = None) -> dict:
    payload = {
        "record_id": record_id,
        "status": "cleaned",
        "cleanup": {"method": "bubble_fill", "cleaned_crop_path": str(cleaned_path), "bbox": bbox},
    }
    if replacement_path is not None:
        payload["cleanup"]["replacement_method"] = "gpt_image2_masked_edit"
        payload["cleanup"]["replacement_crop_path"] = str(replacement_path)
    return payload


def _transparent_layout(tmp_path: Path) -> Path:
    path = tmp_path / "transparent-layout.png"
    Image.new("RGBA", (40, 50), (255, 255, 255, 0)).save(path)
    return path


def _small_layout_preview(tmp_path: Path) -> Path:
    path = tmp_path / "small-layout.png"
    image = Image.new("RGBA", (20, 30), (255, 255, 255, 0))
    ImageDraw.Draw(image).rectangle((6, 6, 14, 24), fill=(0, 0, 0, 255))
    image.save(path)
    return path


def _layout_payload(record_id: str, layout_path: Path) -> dict:
    return {
        "record_id": record_id,
        "status": "layout_generated",
        "layout": {"preview_path": str(layout_path)},
    }


def _layout_payload_with_target_bbox(tmp_path: Path) -> dict:
    payload = _layout_payload("page.png#1", _small_layout_preview(tmp_path))
    payload["layout"]["target_bbox"] = [60, 30, 80, 60]
    return payload


def _skipped_payload(record_id: str, reason: str) -> dict:
    return {
        "record_id": record_id,
        "status": "skipped",
        "preview": {"failure_reason": reason},
    }


def _write_jsonl(path: Path, payloads: list[dict]) -> None:
    path.write_text(_jsonl(payloads), encoding="utf-8")


def _jsonl(payloads: list[dict]) -> str:
    return "".join(json.dumps(payload, ensure_ascii=False) + "\n" for payload in payloads)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
