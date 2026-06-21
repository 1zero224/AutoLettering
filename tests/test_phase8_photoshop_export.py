import json
from pathlib import Path

from PIL import Image

from autolettering.phase8 import run_phase8_photoshop_export


def test_run_phase8_photoshop_export_writes_manifest_and_jsx(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / "cleaned.png")])

    run_dir = run_phase8_photoshop_export(
        detection_run_dir=detection_run,
        font_selection_run_dir=font_run,
        layout_run_dir=layout_run,
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="phase8-test",
        sample_limit=1,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    layer = manifest["pages"][0]["layers"][0]
    assert manifest["schema_version"] == "autolettering.photoshop.v1"
    assert manifest["summary"] == {"record_count": 1, "page_count": 1}
    assert layer["record_id"] == "page.png#1"
    assert layer["bbox"]["xyxy"] == [10, 20, 80, 90]
    assert layer["font"]["family_name"] == "TestFont"
    assert layer["layout"]["angle_degrees"] == -10.5
    assert layer["cleanup"]["method"] == "bubble_fill"
    assert layer["cleanup"]["effective_method"] == "bubble_fill"
    assert layer["cleanup"]["effective_crop_path"] == str(tmp_path / "cleaned.png")
    jsx = (run_dir / "photoshop-import.jsx").read_text(encoding="utf-8")
    assert "photoshop-manifest.json" in jsx
    assert "LayerKind.TEXT" in jsx
    assert "function addCleanupPatchLayer" in jsx
    assert "layerData.cleanup.effective_crop_path" in jsx
    assert "addCleanupPatchLayer(doc, layerData)" in jsx
    assert "AL cleanup " in jsx
    assert "TextType.PARAGRAPHTEXT" in jsx
    assert "item.width = UnitValue(layerData.bbox.width, 'px')" in jsx
    assert "item.height = UnitValue(layerData.bbox.height, 'px')" in jsx
    report = (run_dir / "reports" / "phase8-report.md").read_text(encoding="utf-8")
    assert "Missing cleanup layers: 0" in report
    assert "`bubble_fill=1`" in report
    assert "Places `cleanup.effective_crop_path` as a bitmap patch layer" in report
    assert "paragraph text layer" in report


def test_run_phase8_photoshop_export_preserves_replacement_cleanup(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run_a = _mkdir(tmp_path / "phase6-a")
    cleanup_run_b = _mkdir(tmp_path / "phase6-b")
    replacement_path = tmp_path / "replacement.png"
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run_a / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / "local.png")])
    _write_jsonl(cleanup_run_b / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / "local.png", replacement_path)])

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        [cleanup_run_a, cleanup_run_b],
        tmp_path / "outputs",
        sample_limit=1,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    cleanup = manifest["pages"][0]["layers"][0]["cleanup"]
    assert cleanup["method"] == "local_diffusion_inpaint"
    assert cleanup["replacement_method"] == "gpt_image2_masked_edit"
    assert cleanup["replacement_crop_path"] == str(replacement_path)
    assert cleanup["effective_method"] == "gpt_image2_masked_edit"
    assert cleanup["effective_crop_path"] == str(replacement_path)
    report = (run_dir / "reports" / "phase8-report.md").read_text(encoding="utf-8")
    assert str(cleanup_run_a) in report
    assert str(cleanup_run_b) in report
    assert "`gpt_image2_masked_edit=1`" in report


def test_run_phase8_photoshop_export_skips_records_without_font_selection(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [])

    run_dir = run_phase8_photoshop_export(detection_run, font_run, layout_run, cleanup_run, tmp_path / "outputs")

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    assert manifest["pages"] == []
    assert manifest["summary"] == {"record_count": 0, "page_count": 0}


def _mkdir(path: Path) -> Path:
    path.mkdir()
    return path


def _detection_payload(image_path: Path) -> dict:
    return {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "translated_text": "测试",
        "group_name": "框内",
        "selected_text_box_xyxy": [10, 20, 80, 90],
    }


def _font_payload(font_path: Path) -> dict:
    return {
        "record_id": "page.png#1",
        "status": "selected",
        "selected_font_id": "font-test",
        "selected_font": {
            "font_id": "font-test",
            "path": str(font_path),
            "filename": "font.ttf",
            "family_name": "TestFont",
        },
        "confidence": 0.9,
    }


def _layout_payload() -> dict:
    return {
        "record_id": "page.png#1",
        "status": "layout_generated",
        "layout": {
            "line_breaks": "测\n试",
            "font_size": 32,
            "orientation": "vertical",
            "angle_degrees": -10.5,
            "line_spacing": 4,
            "letter_spacing": 0,
            "target_width": 70,
            "target_height": 70,
            "overflow_ratio": 0.0,
            "validation": {"status": "deterministic_only"},
        },
    }


def _cleanup_payload(cleaned_path: Path, replacement_path: Path | None = None) -> dict:
    cleanup = {
        "method": "bubble_fill",
        "cleaned_crop_path": str(cleaned_path),
        "before_after_path": str(cleaned_path),
    }
    if replacement_path is not None:
        cleanup["method"] = "local_diffusion_inpaint"
        cleanup["replacement_method"] = "gpt_image2_masked_edit"
        cleanup["replacement_crop_path"] = str(replacement_path)
    return {
        "record_id": "page.png#1",
        "status": "cleaned",
        "cleanup": cleanup,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
