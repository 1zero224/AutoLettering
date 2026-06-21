import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.phase7_8_smoke import run_phase7_8_smoke


class FakePreviewEvaluationClient:
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        assert Path(image_path).exists()
        assert kind == "phase7_preview_evaluation"
        assert max_completion_tokens == 512
        return {
            "raw_text": json.dumps(
                {
                    "score": 8,
                    "usable": True,
                    "original_text_removed": True,
                    "art_preserved": True,
                    "lettering_readable": True,
                    "issues": [],
                    "summary": "Integrated preview is usable.",
                }
            ),
            "request": {
                "model": "mimo-v2.5",
                "image_path": str(image_path),
                "prompt_chars": len(prompt),
            },
            "response": {"status": "ok"},
        }


def test_run_phase7_8_smoke_writes_integrated_manifest_and_reports(tmp_path: Path):
    fixture = _write_integrated_smoke_inputs(tmp_path)

    run_dir = run_phase7_8_smoke(
        detection_run_dir=fixture["detection_run"],
        cleanup_run_dirs=[fixture["cleanup_a"], fixture["cleanup_b"]],
        layout_run_dir=fixture["layout_run"],
        font_selection_run_dir=fixture["font_run"],
        output_root=tmp_path / "outputs",
        run_id="integrated-smoke",
        sample_limit=2,
        evaluation_client=FakePreviewEvaluationClient(),
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    report = (run_dir / "reports" / "phase7-8-smoke-report.md").read_text(encoding="utf-8")
    preview_run = Path(manifest["outputs"]["phase7_preview_run_dir"])
    evaluation_run = Path(manifest["outputs"]["phase7_evaluation_run_dir"])
    export_run = Path(manifest["outputs"]["phase8_export_run_dir"])

    assert manifest["schema_version"] == "autolettering.phase7_8.smoke.v1"
    assert manifest["run_id"] == "integrated-smoke"
    assert manifest["summary"]["preview_page_count"] == 1
    assert manifest["summary"]["preview_record_count"] == 2
    assert manifest["summary"]["evaluation_score"] == 8
    assert manifest["summary"]["exported_text_layer_count"] == 2
    assert manifest["summary"]["missing_cleanup_layers"] == 0
    assert preview_run == run_dir / "runs" / "phase7-preview"
    assert (preview_run / "pages" / "page-png.png").exists()
    assert (evaluation_run / "preview-evaluation.jsonl").exists()
    assert (export_run / "photoshop-manifest.json").exists()
    assert "- Evaluation score: 8" in report
    assert "- Missing cleanup layers: 0" in report


def _write_integrated_smoke_inputs(tmp_path: Path) -> dict[str, Path]:
    page_path = _write_page(tmp_path / "page.png")
    paths = _make_input_dirs(tmp_path)
    _write_jsonl(
        paths["detection_run"] / "detections.jsonl",
        [
            _detection_payload("page.png#1", page_path, [40, 20, 80, 70], "街头演出？"),
            _detection_payload("page.png#2", page_path, [10, 10, 50, 40], "来自桃香的唐突的提案"),
        ],
    )
    _write_cleanup_inputs(tmp_path, paths)
    _write_layout_inputs(tmp_path, paths["layout_run"])
    _write_jsonl(paths["font_run"] / "font-selections.jsonl", [_font_payload("page.png#1"), _font_payload("page.png#2")])
    return paths


def _make_input_dirs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "detection_run": tmp_path / "phase2",
        "cleanup_a": tmp_path / "phase6-a",
        "cleanup_b": tmp_path / "phase6-b",
        "layout_run": tmp_path / "phase4",
        "font_run": tmp_path / "phase3",
    }
    for path in paths.values():
        path.mkdir()
    return paths


def _write_cleanup_inputs(tmp_path: Path, paths: dict[str, Path]) -> None:
    _write_jsonl(
        paths["cleanup_a"] / "cleanup-results.jsonl",
        [_cleanup_payload("page.png#1", _write_cleaned_crop(tmp_path / "cleaned-1.png"), [40, 20, 80, 70])],
    )
    _write_jsonl(
        paths["cleanup_b"] / "cleanup-results.jsonl",
        [_cleanup_payload("page.png#2", _write_cleaned_crop(tmp_path / "cleaned-2.png"), [10, 10, 50, 40])],
    )


def _write_layout_inputs(tmp_path: Path, layout_run: Path) -> None:
    _write_jsonl(
        layout_run / "layout-results.jsonl",
        [
            _layout_payload("page.png#1", _write_layout_preview(tmp_path / "layout-1.png"), "horizontal"),
            _layout_payload("page.png#2", _write_layout_preview(tmp_path / "layout-2.png"), "vertical"),
        ],
    )


def _write_page(path: Path) -> Path:
    image = Image.new("RGB", (120, 100), "white")
    ImageDraw.Draw(image).rectangle((40, 20, 80, 70), fill="black")
    ImageDraw.Draw(image).rectangle((10, 10, 50, 40), fill="black")
    image.save(path)
    return path


def _write_cleaned_crop(path: Path) -> Path:
    Image.new("RGB", (40, 50), "white").save(path)
    return path


def _write_layout_preview(path: Path) -> Path:
    image = Image.new("RGBA", (40, 50), (255, 255, 255, 0))
    ImageDraw.Draw(image).rectangle((12, 18, 28, 32), fill=(0, 0, 0, 255))
    image.save(path)
    return path


def _detection_payload(record_id: str, page_path: Path, bbox: list[int], text: str) -> dict:
    return {
        "record_id": record_id,
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(page_path),
        "translated_text": text,
        "selected_text_box_xyxy": bbox,
    }


def _cleanup_payload(record_id: str, cleaned_path: Path, bbox: list[int]) -> dict:
    return {
        "record_id": record_id,
        "status": "cleaned",
        "cleanup": {"method": "bubble_mask_fill", "cleaned_crop_path": str(cleaned_path), "bbox": bbox},
    }


def _layout_payload(record_id: str, layout_path: Path, orientation: str) -> dict:
    return {
        "record_id": record_id,
        "status": "layout_generated",
        "layout": {
            "preview_path": str(layout_path),
            "font_size": 24,
            "orientation": orientation,
            "angle_degrees": 0.0,
            "line_spacing": 2,
            "letter_spacing": 0,
            "target_width": 40,
            "target_height": 50,
            "overflow_ratio": 0.0,
        },
    }


def _font_payload(record_id: str) -> dict:
    return {
        "record_id": record_id,
        "status": "selected",
        "selected_font_id": "font-a",
        "selected_font": {
            "family_name": "Font A",
            "postscript_name": "FontA",
            "filename": "font-a.ttf",
            "path": "fonts/font-a.ttf",
        },
    }


def _write_jsonl(path: Path, payloads: list[dict]) -> None:
    path.write_text("".join(json.dumps(payload, ensure_ascii=False) + "\n" for payload in payloads), encoding="utf-8")
