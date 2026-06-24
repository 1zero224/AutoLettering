import json
from pathlib import Path

from PIL import Image

from autolettering.phase8 import run_phase8_photoshop_export


def test_run_phase8_photoshop_export_writes_manifest_and_jsx(tmp_path: Path):
    run_dir = _run_standard_phase8_export(tmp_path)

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    layer = manifest["pages"][0]["layers"][0]
    assert manifest["schema_version"] == "autolettering.photoshop.v1"
    assert manifest["summary"] == {"record_count": 1, "page_count": 1}
    assert manifest["pages"][0]["layer_order"] == ["text_layers", "repaired_image", "original_image"]
    assert layer["record_id"] == "page.png#1"
    assert layer["text_layer_name"] == "嵌字图层1"
    assert layer["cleanup_layer_name"] == "修复区域 page.png#1"
    assert layer["bbox"]["xyxy"] == [10, 20, 80, 90]
    assert layer["text_bbox"]["xyxy"] == [30, 40, 60, 85]
    assert layer["text_position"]["x_px"] == 30
    assert layer["text_position"]["y_px"] == 40
    assert layer["font"]["family_name"] == "TestFont"
    assert layer["font"]["photoshop_font_name"] == "TestFontPS"
    assert layer["font"]["font_name_candidates"] == ["TestFontPS", "TestFont"]
    assert layer["layout"]["angle_degrees"] == -10.5
    assert layer["layout"]["vertical_align"] == "top"
    assert layer["photoshop"]["vertical_top_anchor_y_px"] == 40
    assert layer["photoshop"]["text_layer_name_suffix"] == " vertical_align=top"
    assert layer["layout"]["text_color"] == [255, 255, 255, 255]
    assert layer["cleanup"]["method"] == "bubble_fill"
    assert layer["cleanup"]["effective_method"] == "bubble_fill"
    assert layer["cleanup"]["effective_crop_path"] == str(tmp_path / "cleaned.png")
    assert layer["cleanup"]["text_bbox"] is None
    assert layer["cleanup"]["mask_bbox"] is None
    assert layer["cleanup"]["layout_text_bbox"] is None
    jsx = (run_dir / "photoshop-import.jsx").read_text(encoding="utf-8")
    _assert_rich_jsx_importer(jsx)
    main_name_original = jsx.rindex("nameOriginalLayer(doc);")
    main_add_repaired = jsx.rindex("var hasRepairedImage = addRepairedImageLayer(doc, page);")
    main_add_text = jsx.rindex("addTextLayer(doc, page.layers[j]);")
    assert main_name_original < main_add_repaired < main_add_text
    report = (run_dir / "reports" / "phase8-report.md").read_text(encoding="utf-8")
    assert "Missing cleanup layers: 0" in report
    assert "`bubble_fill=1`" in report
    assert "Places `cleanup.effective_crop_path` as a bitmap patch layer" in report
    assert "paragraph text layer" in report
    assert "layout.line_spacing" in report
    assert "layout.text_color" in report
    assert "layout.vertical_align" in report
    assert "font.photoshop_font_name" in report
    assert "JSON font mapping file" in report
    checklist = (run_dir / "reports" / "photoshop-validation-checklist.md").read_text(encoding="utf-8")
    assert "Run `photoshop-import.jsx` from this export directory" in checklist
    assert "Expected PSD output folder: `psd/`" in checklist
    assert "- Expected editable text layers: 1" in checklist
    assert "- Expected cleanup patch layers: 1" in checklist
    assert "Font mapping file: none" in checklist
    assert "vertical_align=top" in checklist


def test_run_phase8_photoshop_export_preserves_replacement_cleanup(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run_a = _mkdir(tmp_path / "phase6-a")
    cleanup_run_b = _mkdir(tmp_path / "phase6-b")
    replacement_path = tmp_path / "replacement.png"
    Image.new("RGB", (70, 70), "gray").save(replacement_path)
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
    assert manifest["summary"] == {"record_count": 0, "page_count": 1}
    assert manifest["pages"][0]["layers"] == []
    report = (run_dir / "reports" / "phase8-report.md").read_text(encoding="utf-8")
    assert str(cleanup_run_a) in report
    assert str(cleanup_run_b) in report
    checklist = (run_dir / "reports" / "photoshop-validation-checklist.md").read_text(encoding="utf-8")
    assert "- Expected editable text layers: 0" in checklist


def test_run_phase8_photoshop_export_keeps_text_layer_when_replacement_crop_missing(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    local_path = tmp_path / "local.png"
    Image.new("RGB", (70, 70), "gray").save(local_path)
    cleanup = _cleanup_payload(local_path)
    cleanup["cleanup"]["replacement_method"] = "gpt_image2_masked_edit"
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [cleanup])

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    page = manifest["pages"][0]
    assert [layer["text_layer_name"] for layer in page["layers"]] == ["嵌字图层1"]
    assert page["repaired_image_path"]


def test_run_phase8_photoshop_export_uses_phase7_cleaned_page_as_repaired_image_layer(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    repaired_page = tmp_path / "cleaned-page.png"
    Image.new("RGB", (120, 160), "gray").save(repaired_page)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    preview_run = _mkdir(tmp_path / "phase7")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / "local.png")])
    _write_jsonl(
        preview_run / "preview-results.jsonl",
        [
            {
                "image_name": "page.png",
                "status": "page_preview_generated",
                "preview": {"cleaned_page_path": str(repaired_page)},
            }
        ],
    )

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
        preview_run_dir=preview_run,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    page = manifest["pages"][0]
    assert page["repaired_image_path"] == str(repaired_page)
    assert page["layers"][0]["cleanup"]["effective_crop_path"] == str(tmp_path / "local.png")
    report = (run_dir / "reports" / "phase8-report.md").read_text(encoding="utf-8")
    checklist = (run_dir / "reports" / "photoshop-validation-checklist.md").read_text(encoding="utf-8")
    assert "Adds page-level `repaired_image_path`" in report
    assert "Synthesizes page-level `repaired_image_path`" in report
    assert "Skips per-record cleanup patch layers" in report
    assert "Expected page-level repaired image layers: 1" in checklist
    assert "Expected cleanup patch layers: 0" in checklist


def test_run_phase8_photoshop_export_synthesizes_repaired_page_from_cleanup_rows(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    cleaned_crop = tmp_path / "cleaned.png"
    Image.new("RGB", (30, 40), "gray").save(cleaned_crop)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [_cleanup_payload(cleaned_crop, cleanup_bbox=[10, 20, 40, 60])])

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    page = manifest["pages"][0]
    repaired_path = Path(page["repaired_image_path"])
    assert repaired_path.parent.name == "repaired_pages"
    assert page["layers"][0]["text_layer_name"] == "嵌字图层1"
    with Image.open(repaired_path).convert("RGB") as repaired:
        assert repaired.getpixel((12, 22)) == (128, 128, 128)
    checklist = (run_dir / "reports" / "photoshop-validation-checklist.md").read_text(encoding="utf-8")
    assert "- Expected page-level repaired image layers: 1" in checklist
    assert "- Expected cleanup patch layers: 0" in checklist


def test_run_phase8_photoshop_export_skips_text_layer_for_gpt_replacement_cleanup(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    replacement_path = tmp_path / "replacement.png"
    Image.new("RGB", (70, 70), "gray").save(replacement_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / "local.png", replacement_path)])

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    page = manifest["pages"][0]
    assert manifest["summary"] == {"record_count": 0, "page_count": 1}
    assert page["layers"] == []
    assert page["repaired_image_path"]
    checklist = (run_dir / "reports" / "photoshop-validation-checklist.md").read_text(encoding="utf-8")
    assert "- Expected editable text layers: 0" in checklist
    assert "- Expected page-level repaired image layers: 1" in checklist


def test_run_phase8_photoshop_export_uses_phase7_manifest_for_repaired_page_without_text_layers(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    repaired_page = tmp_path / "cleaned-page.png"
    Image.new("RGB", (120, 160), "gray").save(repaired_page)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    preview_run = _mkdir(tmp_path / "phase7")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path, status="fallback_required", selected_bbox=None)])
    _write_jsonl(font_run / "font-selections.jsonl", [])
    _write_jsonl(layout_run / "layout-results.jsonl", [])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / "local.png", repaired_page)])
    (preview_run / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "autolettering.phase7.preview.v1",
                "pages": [
                    {
                        "image_name": "page.png",
                        "original_page_path": str(image_path),
                        "cleaned_page_path": str(repaired_page),
                        "record_count": 1,
                        "records": [
                            {
                                "record_id": "page.png#1",
                                "cleanup_method": "gpt_image2_masked_edit",
                                "text_overlay_required": False,
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
        preview_run_dir=preview_run,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    page = manifest["pages"][0]
    assert manifest["summary"] == {"record_count": 0, "page_count": 1}
    assert page["image_name"] == "page.png"
    assert page["image_path"] == str(image_path)
    assert page["repaired_image_path"] == str(repaired_page)
    assert page["layers"] == []
    checklist = (run_dir / "reports" / "photoshop-validation-checklist.md").read_text(encoding="utf-8")
    assert "- Expected editable text layers: 0" in checklist
    assert "- Expected page-level repaired image layers: 1" in checklist


def test_run_phase8_photoshop_export_names_text_layers_sequentially_per_page(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    record_ids = ["page.png#1", "page.png#2"]
    _write_jsonl(
        detection_run / "detections.jsonl",
        [_detection_payload(image_path, record_id=record_id) for record_id in record_ids],
    )
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf", record_id) for record_id in record_ids])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload(record_id) for record_id in record_ids])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / f"cleaned-{index}.png", record_id=record_id) for index, record_id in enumerate(record_ids, start=1)])

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=2,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    layers = manifest["pages"][0]["layers"]
    assert [layer["text_layer_name"] for layer in layers] == ["嵌字图层1", "嵌字图层2"]
    assert [layer["record_id"] for layer in layers] == record_ids


def test_run_phase8_photoshop_export_uses_cleanup_bbox_for_fallback_detection_when_layout_exists(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path, status="fallback_required", selected_bbox=None)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [_cleanup_payload(tmp_path / "cleaned.png", cleanup_bbox=[35, 25, 62, 55], method="bt_lama_large_inpaint")],
    )

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    layer = manifest["pages"][0]["layers"][0]
    assert layer["record_id"] == "page.png#1"
    assert layer["bbox"]["xyxy"] == [35, 25, 62, 55]
    assert layer["cleanup"]["method"] == "bt_lama_large_inpaint"
    assert layer["text_layer_name"] == "嵌字图层1"


def test_run_phase8_photoshop_export_places_cleanup_patch_by_cleanup_bbox(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / "cleaned.png", cleanup_bbox=[0, 10, 90, 110])])

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    layer = manifest["pages"][0]["layers"][0]
    assert layer["bbox"]["xyxy"] == [10, 20, 80, 90]
    assert layer["cleanup"]["bbox"]["xyxy"] == [0, 10, 90, 110]
    assert layer["cleanup"]["position"]["x_px"] == 0
    assert layer["cleanup"]["position"]["y_px"] == 10
    jsx = (run_dir / "photoshop-import.jsx").read_text(encoding="utf-8")
    assert "var patchPosition = (layerData.cleanup && layerData.cleanup.position) || layerData.position" in jsx
    assert "moveLayerTopLeft(layer, patchPosition.x_px, patchPosition.y_px)" in jsx


def test_run_phase8_photoshop_export_prefers_cleanup_layout_text_bbox(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            _cleanup_payload(
                tmp_path / "cleaned.png",
                cleanup_bbox=[10, 20, 80, 90],
                text_bbox=[10, 20, 80, 90],
                mask_bbox=[42, 44, 70, 110],
                layout_text_bbox=[42, 44, 70, 110],
            )
        ],
    )

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    layer = manifest["pages"][0]["layers"][0]
    assert layer["layout"]["target_width"] == 70
    assert layer["layout"]["target_height"] == 70
    assert layer["text_bbox"]["xyxy"] == [42, 44, 70, 110]
    assert layer["text_position"]["x_px"] == 42
    assert layer["text_position"]["y_px"] == 44
    assert layer["photoshop"]["vertical_top_anchor_y_px"] == 44
    assert layer["cleanup"]["bbox"]["xyxy"] == [10, 20, 80, 90]
    assert layer["cleanup"]["text_bbox"]["xyxy"] == [10, 20, 80, 90]
    assert layer["cleanup"]["mask_bbox"]["xyxy"] == [42, 44, 70, 110]
    assert layer["cleanup"]["layout_text_bbox"]["xyxy"] == [42, 44, 70, 110]


def test_run_phase8_photoshop_export_applies_font_mapping_file(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 160), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    mapping_path = tmp_path / "font-map.json"
    _write_jsonl(detection_run / "detections.jsonl", [_detection_payload(image_path)])
    _write_jsonl(font_run / "font-selections.jsonl", [_font_payload(tmp_path / "font.ttf")])
    _write_jsonl(layout_run / "layout-results.jsonl", [_layout_payload()])
    _write_jsonl(cleanup_run / "cleanup-results.jsonl", [_cleanup_payload(tmp_path / "cleaned.png")])
    mapping_path.write_text(json.dumps({"TestFontPS": "InstalledTestFont-Regular"}), encoding="utf-8")

    run_dir = run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        sample_limit=1,
        font_mapping_path=mapping_path,
    )

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    font = manifest["pages"][0]["layers"][0]["font"]
    assert font["photoshop_font_name"] == "InstalledTestFont-Regular"
    assert font["font_name_candidates"] == ["InstalledTestFont-Regular", "TestFontPS", "TestFont"]
    assert font["mapped_from"] == "TestFontPS"
    report = (run_dir / "reports" / "phase8-report.md").read_text(encoding="utf-8")
    assert f"Font mapping file: `{mapping_path}`" in report


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


def _run_standard_phase8_export(tmp_path: Path) -> Path:
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
    return run_phase8_photoshop_export(
        detection_run,
        font_run,
        layout_run,
        cleanup_run,
        tmp_path / "outputs",
        "phase8-test",
        1,
    )


def _assert_rich_jsx_importer(jsx: str) -> None:
    for expected in [
        "photoshop-manifest.json",
        "function nameOriginalLayer",
        "layer.name = '原图'",
        "LayerKind.TEXT",
        "function addRepairedImageLayer",
        "page.repaired_image_path",
        "layer.name = '修复图像'",
        "function addCleanupPatchLayer",
        "layerData.cleanup.effective_crop_path",
        "addCleanupPatchLayer(doc, layerData)",
        "layerData.text_layer_name",
        "layerData.cleanup_layer_name",
        "AL cleanup ",
        "TextType.PARAGRAPHTEXT",
        "item.width = UnitValue(layerData.text_bbox.width, 'px')",
        "item.height = UnitValue(layerData.text_bbox.height, 'px')",
        "layerData.text_position.x_px",
        "layerData.photoshop.vertical_top_anchor_y_px",
        "function applyVerticalTopAnchor",
        "moveLayerTop(layer, layerData.photoshop.vertical_top_anchor_y_px)",
        "function setTextSpacing",
        "function setTextColor",
        "var color = new SolidColor()",
        "textItem.color = color",
        "textItem.leading",
        "textItem.tracking",
        "layerData.font.photoshop_font_name || layerData.font.family_name",
    ]:
        assert expected in jsx
    assert jsx.index("layer.rotate(layerData.layout.angle_degrees)") < jsx.rindex("applyVerticalTopAnchor(layer, layerData)")


def _detection_payload(
    image_path: Path,
    record_id: str = "page.png#1",
    status: str = "ok",
    selected_bbox: list[int] | None = None,
) -> dict:
    if selected_bbox is None and status == "ok":
        selected_bbox = [10, 20, 80, 90]
    return {
        "record_id": record_id,
        "status": status,
        "image_name": "page.png",
        "image_path": str(image_path),
        "translated_text": "测试",
        "group_name": "框内",
        "selected_text_box_xyxy": selected_bbox,
    }


def _font_payload(font_path: Path, record_id: str = "page.png#1") -> dict:
    return {
        "record_id": record_id,
        "status": "selected",
        "selected_font_id": "font-test",
        "selected_font": {
            "font_id": "font-test",
            "path": str(font_path),
            "filename": "font.ttf",
            "family_name": "TestFont",
            "postscript_name": "TestFontPS",
        },
        "confidence": 0.9,
    }


def _layout_payload(record_id: str = "page.png#1") -> dict:
    return {
        "record_id": record_id,
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
            "target_bbox": [30, 40, 60, 85],
            "vertical_align": "top",
            "text_color": [255, 255, 255, 255],
            "overflow_ratio": 0.0,
            "validation": {"status": "deterministic_only"},
        },
    }


def _cleanup_payload(
    cleaned_path: Path,
    replacement_path: Path | None = None,
    cleanup_bbox: list[int] | None = None,
    text_bbox: list[int] | None = None,
    mask_bbox: list[int] | None = None,
    layout_text_bbox: list[int] | None = None,
    record_id: str = "page.png#1",
    method: str = "bubble_fill",
) -> dict:
    cleanup = {
        "method": method,
        "cleaned_crop_path": str(cleaned_path),
        "before_after_path": str(cleaned_path),
    }
    if cleanup_bbox is not None:
        cleanup["bbox"] = cleanup_bbox
    if text_bbox is not None:
        cleanup["text_bbox"] = text_bbox
    if mask_bbox is not None:
        cleanup["mask_bbox"] = mask_bbox
    if layout_text_bbox is not None:
        cleanup["layout_text_bbox"] = layout_text_bbox
    if replacement_path is not None:
        cleanup["method"] = "local_diffusion_inpaint"
        cleanup["replacement_method"] = "gpt_image2_masked_edit"
        cleanup["replacement_crop_path"] = str(replacement_path)
    return {
        "record_id": record_id,
        "status": "cleaned",
        "cleanup": cleanup,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
