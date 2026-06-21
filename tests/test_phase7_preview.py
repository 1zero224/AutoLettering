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


def _detection_payload(record_id: str, page_path: Path, bbox: list[int]) -> dict:
    return {
        "record_id": record_id,
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(page_path),
        "selected_text_box_xyxy": bbox,
    }


def _cleanup_payload(record_id: str, cleaned_path: Path, bbox: list[int], replacement_path: Path | None = None) -> dict:
    payload = {
        "record_id": record_id,
        "status": "cleaned",
        "cleanup": {"cleaned_crop_path": str(cleaned_path), "bbox": bbox},
    }
    if replacement_path is not None:
        payload["cleanup"]["replacement_method"] = "gpt_image2_masked_edit"
        payload["cleanup"]["replacement_crop_path"] = str(replacement_path)
    return payload


def _transparent_layout(tmp_path: Path) -> Path:
    path = tmp_path / "transparent-layout.png"
    Image.new("RGBA", (40, 50), (255, 255, 255, 0)).save(path)
    return path


def _layout_payload(record_id: str, layout_path: Path) -> dict:
    return {
        "record_id": record_id,
        "status": "layout_generated",
        "layout": {"preview_path": str(layout_path)},
    }


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
