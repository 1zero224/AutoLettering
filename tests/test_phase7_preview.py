import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from autolettering.phase7 import run_phase7_preview
from autolettering.rendering.compose import compose_page_preview


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


def test_run_phase7_preview_writes_page_preview_and_records(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    cleaned_path = _write_cleaned_crop(tmp_path / "cleaned.png")
    layout_path = _write_layout_preview(tmp_path / "layout.png")
    detection_run = tmp_path / "phase2"
    cleanup_run = tmp_path / "phase6"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    cleanup_run.mkdir()
    layout_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", page_path)
    _write_cleanup(cleanup_run / "cleanup-results.jsonl", cleaned_path)
    _write_layout(layout_run / "layout-results.jsonl", layout_path)

    run_dir = run_phase7_preview(
        detection_run_dir=detection_run,
        cleanup_run_dir=cleanup_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "preview-results.jsonl")
    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "preview_generated"
    assert Path(rows[0]["preview"]["page_preview_path"]).exists()
    assert (run_dir / "reports" / "phase7-report.md").exists()


def _write_page(path: Path) -> Path:
    image = Image.new("RGB", (120, 100), "white")
    ImageDraw.Draw(image).rectangle((40, 20, 80, 70), fill="black")
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


def _write_detection(path: Path, page_path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(page_path),
        "selected_text_box_xyxy": [40, 20, 80, 70],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_cleanup(path: Path, cleaned_path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "cleaned",
        "cleanup": {"cleaned_crop_path": str(cleaned_path), "bbox": [40, 20, 80, 70]},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_layout(path: Path, layout_path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "layout_generated",
        "layout": {"preview_path": str(layout_path)},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
