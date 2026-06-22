import json
from pathlib import Path

from autolettering.phase8_export_audit import audit_phase8_export, write_phase8_export_audit


def test_audit_phase8_export_flags_vertical_top_anchor_gaps(tmp_path: Path):
    run_dir = tmp_path / "phase8"
    _write_manifest(
        run_dir / "photoshop-manifest.json",
        [
            _layer("r1", "vertical", "top", 40, " vertical_align=top", [10, 40, 30, 90]),
            _layer("r2", "vertical", "top", None, "", [20, 50, 40, 100]),
            _layer("r3", "horizontal", "top", 60, " vertical_align=top", [30, 60, 90, 85]),
        ],
    )
    (run_dir / "photoshop-import.jsx").write_text(
        "function applyVerticalTopAnchor() { moveLayerTop(layer, layerData.photoshop.vertical_top_anchor_y_px); }",
        encoding="utf-8",
    )

    report = audit_phase8_export(run_dir)

    assert report["summary"]["record_count"] == 3
    assert report["summary"]["passed"] is False
    assert report["summary"]["missing_vertical_top_anchor_count"] == 1
    assert report["summary"]["unexpected_vertical_top_anchor_count"] == 1
    assert report["summary"]["jsx_anchor_logic_present"] is True
    records = {row["record_id"]: row for row in report["records"]}
    assert records["r1"]["issues"] == []
    assert "missing_vertical_top_anchor_y_px" in records["r2"]["issues"]
    assert "unexpected_vertical_top_anchor_y_px" in records["r3"]["issues"]


def test_write_phase8_export_audit_writes_json_and_markdown(tmp_path: Path):
    source = tmp_path / "source"
    _write_manifest(source / "photoshop-manifest.json", [_layer("r1", "vertical", "top", 40, " vertical_align=top")])
    (source / "photoshop-import.jsx").write_text(
        "function applyVerticalTopAnchor() { moveLayerTop(layer, layerData.photoshop.vertical_top_anchor_y_px); }",
        encoding="utf-8",
    )

    run_dir = write_phase8_export_audit(source, tmp_path / "outputs", "audit-test")

    payload = json.loads((run_dir / "phase8-export-audit.json").read_text(encoding="utf-8"))
    markdown = (run_dir / "reports" / "phase8-export-audit-report.md").read_text(encoding="utf-8")
    assert payload["summary"]["passed"] is True
    assert payload["summary"]["vertical_top_layer_count"] == 1
    assert "Phase 8 Photoshop Export Quality Audit" in markdown
    assert "`r1`" in markdown


def _write_manifest(path: Path, layers: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pages": [{"image_name": "page.png", "layers": layers}], "summary": {"record_count": len(layers)}}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _layer(
    record_id: str,
    orientation: str,
    vertical_align: str,
    anchor_y: int | None,
    suffix: str,
    bbox: list[int] | None = None,
) -> dict:
    xyxy = bbox or [10, 40, 30, 90]
    return {
        "record_id": record_id,
        "text_bbox": {"xyxy": xyxy, "x": xyxy[0], "y": xyxy[1], "width": xyxy[2] - xyxy[0], "height": xyxy[3] - xyxy[1]},
        "text_position": {"x_px": xyxy[0], "y_px": xyxy[1]},
        "layout": {"orientation": orientation, "vertical_align": vertical_align},
        "photoshop": {"vertical_top_anchor_y_px": anchor_y, "text_layer_name_suffix": suffix},
    }
