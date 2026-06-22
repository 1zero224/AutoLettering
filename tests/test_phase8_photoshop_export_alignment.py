import json
from pathlib import Path

from PIL import Image

from autolettering.phase8 import run_phase8_photoshop_export


def test_run_phase8_photoshop_export_only_top_anchors_vertical_top_layouts(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (120, 180), "white").save(image_path)
    detection_run = _mkdir(tmp_path / "phase2")
    font_run = _mkdir(tmp_path / "phase3")
    layout_run = _mkdir(tmp_path / "phase4")
    cleanup_run = _mkdir(tmp_path / "phase6")
    records = [
        ("page.png#vertical-top", "vertical", "top", [30, 40, 60, 85]),
        ("page.png#vertical-center", "vertical", "center", [30, 70, 60, 115]),
        ("page.png#horizontal-top", "horizontal", "top", [20, 100, 90, 130]),
    ]
    _write_jsonl(
        detection_run / "detections.jsonl",
        [_detection_payload(image_path, record_id) for record_id, _, _, _ in records],
    )
    _write_jsonl(
        font_run / "font-selections.jsonl",
        [_font_payload(tmp_path / "font.ttf", record_id) for record_id, _, _, _ in records],
    )
    _write_jsonl(
        layout_run / "layout-results.jsonl",
        [
            _layout_payload(record_id, orientation, vertical_align, target_bbox)
            for record_id, orientation, vertical_align, target_bbox in records
        ],
    )
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [_cleanup_payload(tmp_path / f"{record_id.replace('#', '-')}.png", record_id) for record_id, _, _, _ in records],
    )

    run_dir = run_phase8_photoshop_export(detection_run, font_run, layout_run, cleanup_run, tmp_path / "outputs", sample_limit=3)

    manifest = json.loads((run_dir / "photoshop-manifest.json").read_text(encoding="utf-8"))
    layers = {layer["record_id"]: layer for layer in manifest["pages"][0]["layers"]}
    assert layers["page.png#vertical-top"]["photoshop"]["vertical_top_anchor_y_px"] == 40
    assert layers["page.png#vertical-top"]["photoshop"]["text_layer_name_suffix"] == " vertical_align=top"
    assert layers["page.png#vertical-center"]["photoshop"]["vertical_top_anchor_y_px"] is None
    assert layers["page.png#vertical-center"]["photoshop"]["text_layer_name_suffix"] == ""
    assert layers["page.png#horizontal-top"]["photoshop"]["vertical_top_anchor_y_px"] is None
    assert layers["page.png#horizontal-top"]["photoshop"]["text_layer_name_suffix"] == ""
    jsx = (run_dir / "photoshop-import.jsx").read_text(encoding="utf-8")
    assert "layerData.photoshop.vertical_top_anchor_y_px" in jsx


def _mkdir(path: Path) -> Path:
    path.mkdir()
    return path


def _detection_payload(image_path: Path, record_id: str) -> dict:
    return {
        "record_id": record_id,
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "translated_text": "test",
        "group_name": "bubble",
        "selected_text_box_xyxy": [10, 20, 80, 90],
    }


def _font_payload(font_path: Path, record_id: str) -> dict:
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


def _layout_payload(record_id: str, orientation: str, vertical_align: str, target_bbox: list[int]) -> dict:
    return {
        "record_id": record_id,
        "status": "layout_generated",
        "layout": {
            "line_breaks": "te\nst",
            "font_size": 32,
            "orientation": orientation,
            "angle_degrees": -10.5,
            "line_spacing": 4,
            "letter_spacing": 0,
            "target_width": 70,
            "target_height": 70,
            "target_bbox": target_bbox,
            "vertical_align": vertical_align,
            "text_color": [255, 255, 255, 255],
            "overflow_ratio": 0.0,
            "validation": {"status": "deterministic_only"},
        },
    }


def _cleanup_payload(cleaned_path: Path, record_id: str) -> dict:
    return {
        "record_id": record_id,
        "status": "cleaned",
        "cleanup": {
            "method": "bubble_fill",
            "cleaned_crop_path": str(cleaned_path),
            "before_after_path": str(cleaned_path),
        },
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
