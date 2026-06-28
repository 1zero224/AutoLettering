import json
from pathlib import Path

from PIL import Image

from experiments import full_gbc06_frame_in_comic_pipeline as pipeline


def test_pipeline_filters_frame_in_records_and_uses_comic_detector(tmp_path: Path, monkeypatch):
    labelplus_file = _write_labelplus_project(tmp_path)
    font_dir = tmp_path / "fonts"
    font_dir.mkdir()
    calls = {}

    _patch_phase_runners(monkeypatch, calls)

    run_dir = pipeline.run_full_gbc06_frame_in_comic_pipeline(
        labelplus_file=labelplus_file,
        font_dir=font_dir,
        output_root=tmp_path / "outputs",
        run_id="gbc06-frame-in",
        sample_limit=10,
        target_group_name="框内",
        comic_detector_model_path=tmp_path / "detector.onnx",
        comic_detector_conf_threshold=0.51,
        comic_detector_max_distance_px=123,
        font_limit=7,
        mimo_client=object(),
        mimo_model="mimo-v2.5",
    )

    expected_record_ids = ["page1.png#1", "page2.png#1"]
    assert calls["phase2"]["record_ids"] == expected_record_ids
    assert calls["phase2"]["detection_strategy"] == "comic_rtdetrv2"
    assert calls["phase2"]["comic_detector_conf_threshold"] == 0.51
    assert calls["phase2"]["comic_detector_max_distance_px"] == 123
    assert calls["phase3"]["record_ids"] == expected_record_ids
    assert calls["phase3"]["font_limit"] == 7
    assert calls["phase3_vision"]["record_ids"] == expected_record_ids
    assert calls["phase3_vision"]["client"] is not None
    assert calls["phase4"]["record_ids"] == expected_record_ids
    assert calls["phase4"]["detection_run_dir"] == run_dir / "runs" / "phase2-comic-rtdetrv2"
    assert calls["phase6"]["record_ids"] == expected_record_ids
    assert calls["phase6"]["cleanup_method"] == "text_mask_inpaint"
    assert calls["phase7"]["cleanup_run_dir"] == [run_dir / "runs" / "phase6-bubble-cleanup"]
    assert calls["phase8"]["preview_run_dir"] == run_dir / "runs" / "phase7-page-preview"

    frame_rows = _read_jsonl(run_dir / "frame-in-records.jsonl")
    assert [row["record_id"] for row in frame_rows] == expected_record_ids
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == pipeline.SCHEMA_VERSION
    assert manifest["frame_in_record_count"] == 2
    assert manifest["configuration"]["phase2_detection_strategy"] == "comic_rtdetrv2"
    assert manifest["configuration"]["lettering_scope"] == "inside_bubble_only"
    assert manifest["stage_summary"]["phase2"]["status_counts"] == {"ok": 2}
    assert manifest["stage_summary"]["phase8_photoshop_export"]["text_layer_count"] == 2
    assert (run_dir / "reports" / "pipeline-report.md").exists()


def test_pipeline_manifest_and_report_do_not_leak_mimo_env(tmp_path: Path, monkeypatch):
    labelplus_file = _write_labelplus_project(tmp_path)
    calls = {}
    _patch_phase_runners(monkeypatch, calls)
    monkeypatch.setenv("MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setenv("MIMO_API_KEY", "secret-value")
    monkeypatch.setenv("MIMO_VISION_MODEL", "mimo-v2.5")

    run_dir = pipeline.run_full_gbc06_frame_in_comic_pipeline(
        labelplus_file=labelplus_file,
        font_dir=tmp_path,
        output_root=tmp_path / "outputs",
        run_id="gbc06-frame-in",
        sample_limit=10,
        mimo_client=object(),
        mimo_model="mimo-v2.5",
    )

    combined = (
        (run_dir / "manifest.json").read_text(encoding="utf-8")
        + (run_dir / "reports" / "pipeline-report.md").read_text(encoding="utf-8")
    )
    assert "secret-value" not in combined
    assert "MIMO_API_KEY" not in combined
    assert "api_key" not in combined.lower()
    assert "mimo-v2.5" in combined


def test_pipeline_main_forwards_cli_args(monkeypatch, tmp_path: Path, capsys):
    calls = {}

    def fake_run(**kwargs):
        calls.update(kwargs)
        return tmp_path / "outputs" / "gbc06-cli"

    monkeypatch.setattr(pipeline, "run_full_gbc06_frame_in_comic_pipeline", fake_run)
    monkeypatch.setattr(pipeline, "MimoVisionClient", lambda config: {"config": config})
    monkeypatch.setenv("MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setenv("MIMO_API_KEY", "secret-value")
    monkeypatch.setenv("MIMO_VISION_MODEL", "mimo-v2.5")
    monkeypatch.setattr(
        "sys.argv",
        [
            "full_gbc06_frame_in_comic_pipeline.py",
            "--labelplus-file",
            "GBC06 (已翻 斗笠)/翻译_0.txt",
            "--font-dir",
            "工具箱漫画字体V2.5",
            "--output-root",
            str(tmp_path / "outputs"),
            "--run-id",
            "gbc06-cli",
            "--sample-limit",
            "12",
            "--target-group-name",
            "框内",
            "--comic-detector-model-path",
            "comic-text-and-bubble-detector/detector_int8.onnx",
            "--comic-detector-conf-threshold",
            "0.42",
            "--comic-detector-max-distance-px",
            "98",
            "--font-limit",
            "9",
            "--cleanup-method",
            "text_mask_inpaint",
            "--inpaint-method",
            "opencv_ns",
            "--mask-dilate-px",
            "4",
            "--env-file",
            str(tmp_path / "missing.env"),
        ],
    )

    pipeline.main()

    assert calls["labelplus_file"] == Path("GBC06 (已翻 斗笠)/翻译_0.txt")
    assert calls["font_dir"] == Path("工具箱漫画字体V2.5")
    assert calls["output_root"] == tmp_path / "outputs"
    assert calls["run_id"] == "gbc06-cli"
    assert calls["sample_limit"] == 12
    assert calls["target_group_name"] == "框内"
    assert calls["comic_detector_model_path"] == Path("comic-text-and-bubble-detector/detector_int8.onnx")
    assert calls["comic_detector_conf_threshold"] == 0.42
    assert calls["comic_detector_max_distance_px"] == 98
    assert calls["font_limit"] == 9
    assert calls["cleanup_method"] == "text_mask_inpaint"
    assert calls["inpaint_method"] == "opencv_ns"
    assert calls["mask_dilate_px"] == 4
    assert calls["mimo_model"] == "mimo-v2.5"
    assert calls["mimo_client"]["config"].api_key == "secret-value"
    assert str(tmp_path / "outputs" / "gbc06-cli") in capsys.readouterr().out


def test_resumable_mimo_selection_clears_stale_rows_when_inputs_change(tmp_path: Path):
    input_run = tmp_path / "phase3"
    output_root = tmp_path / "outputs"
    _write_jsonl(
        input_run / "font-comparisons.jsonl",
        [
            _font_comparison_row("page1.png#1"),
        ],
    )
    selection_dir = output_root / "phase3-mimo-font-selection"
    _write_jsonl(selection_dir / "font-selections.jsonl", [_font_selection_row("stale.png#1")])
    _write_jsonl(selection_dir / "reports" / "api-calls.jsonl", [{"record_id": "stale.png#1", "status": "ok"}])
    (selection_dir / "reports" / "resume-metadata.json").write_text(
        json.dumps({"input_run_dir": "old", "record_ids": ["stale.png#1"], "mimo_model": "mimo-v2.5"}),
        encoding="utf-8",
    )

    run_dir = pipeline._run_phase3_vision_selection_resumable(
        input_run_dir=input_run,
        output_root=output_root,
        run_id="phase3-mimo-font-selection",
        sample_limit=1,
        record_ids=["page1.png#1"],
        config=pipeline.MimoVisionConfig("https://mimo.example/v1", "secret-value", "mimo-v2.5"),
        timeout_sec=1,
        max_consecutive_timeouts=1,
    )

    rows = _read_jsonl(run_dir / "font-selections.jsonl")
    api_rows = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")
    metadata = json.loads((run_dir / "reports" / "resume-metadata.json").read_text(encoding="utf-8"))
    assert [row["record_id"] for row in rows] == ["page1.png#1"]
    assert [row["record_id"] for row in api_rows] == ["page1.png#1"]
    assert rows[0]["selection_source"] == "deterministic_fallback"
    assert metadata["record_ids"] == ["page1.png#1"]


def test_resumable_mimo_selection_clears_rows_when_comparisons_change(tmp_path: Path, monkeypatch):
    input_run = tmp_path / "phase3"
    output_root = tmp_path / "outputs"
    old_rows = [_font_comparison_row("page1.png#1")]
    new_rows = [_font_comparison_row("page1.png#1")]
    new_rows[0]["candidate_fonts"] = [{"font_id": "font-b", "path": "font-b.ttf"}]
    comparison_path = input_run / "font-comparisons.jsonl"
    _write_jsonl(comparison_path, new_rows)
    config = pipeline.MimoVisionConfig("https://mimo.example/v1", "secret-value", "mimo-v2.5")
    selection_dir = output_root / "phase3-mimo-font-selection"
    old_metadata = pipeline._mimo_resume_metadata(input_run, comparison_path, old_rows, config, 1, 1)
    _write_jsonl(selection_dir / "font-selections.jsonl", [_font_selection_row("page1.png#1")])
    _write_jsonl(selection_dir / "reports" / "api-calls.jsonl", [{"record_id": "page1.png#1", "status": "ok"}])
    (selection_dir / "reports" / "resume-metadata.json").write_text(
        json.dumps(old_metadata, ensure_ascii=False),
        encoding="utf-8",
    )
    calls = []

    def fake_select(row, config, timeout_sec):
        calls.append(row["record_id"])
        return _mimo_success(row["record_id"], "font-b"), {"record_id": row["record_id"], "status": "ok"}, False

    monkeypatch.setattr(pipeline, "_select_font_with_process_timeout", fake_select)
    run_dir = pipeline._run_phase3_vision_selection_resumable(
        input_run_dir=input_run,
        output_root=output_root,
        run_id="phase3-mimo-font-selection",
        sample_limit=1,
        record_ids=["page1.png#1"],
        config=config,
        timeout_sec=1,
        max_consecutive_timeouts=1,
    )

    rows = _read_jsonl(run_dir / "font-selections.jsonl")
    metadata = json.loads((run_dir / "reports" / "resume-metadata.json").read_text(encoding="utf-8"))
    assert calls == ["page1.png#1"]
    assert rows[0]["selected_font_id"] == "font-b"
    assert metadata["filtered_rows_sha256"] == pipeline._stable_json_sha256(new_rows)


def test_resumable_mimo_selection_retries_half_written_rows(tmp_path: Path, monkeypatch):
    input_run = tmp_path / "phase3"
    output_root = tmp_path / "outputs"
    comparison_rows = [_font_comparison_row("page1.png#1")]
    comparison_path = input_run / "font-comparisons.jsonl"
    _write_jsonl(comparison_path, comparison_rows)
    config = pipeline.MimoVisionConfig("https://mimo.example/v1", "secret-value", "mimo-v2.5")
    selection_dir = output_root / "phase3-mimo-font-selection"
    metadata = pipeline._mimo_resume_metadata(input_run, comparison_path, comparison_rows, config, 1, 1)
    _write_jsonl(selection_dir / "font-selections.jsonl", [_font_selection_row("page1.png#1")])
    (selection_dir / "reports").mkdir(parents=True)
    (selection_dir / "reports" / "resume-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )
    calls = []

    def fake_select(row, config, timeout_sec):
        calls.append(row["record_id"])
        return _mimo_success(row["record_id"], "font-a"), {"record_id": row["record_id"], "status": "ok"}, False

    monkeypatch.setattr(pipeline, "_select_font_with_process_timeout", fake_select)
    run_dir = pipeline._run_phase3_vision_selection_resumable(
        input_run_dir=input_run,
        output_root=output_root,
        run_id="phase3-mimo-font-selection",
        sample_limit=1,
        record_ids=["page1.png#1"],
        config=config,
        timeout_sec=1,
        max_consecutive_timeouts=1,
    )

    rows = _read_jsonl(run_dir / "font-selections.jsonl")
    api_rows = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")
    assert calls == ["page1.png#1"]
    assert [row["record_id"] for row in rows] == ["page1.png#1"]
    assert [row["record_id"] for row in api_rows] == ["page1.png#1"]


def _patch_phase_runners(monkeypatch, calls: dict) -> None:
    def fake_phase1(**kwargs):
        calls["phase1"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
        return run_dir

    def fake_phase2(**kwargs):
        calls["phase2"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        _write_jsonl(
            run_dir / "detections.jsonl",
            [
                _detection_row("page1.png#1", "page1.png", [10, 10, 110, 90], "text_bubble", 0.0),
                _detection_row("page2.png#1", "page2.png", [20, 20, 120, 100], "text_bubble", 3.0),
            ],
        )
        return run_dir

    def fake_phase3(**kwargs):
        calls["phase3"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        _write_jsonl(
            run_dir / "font-comparisons.jsonl",
            [
                _font_comparison_row("page1.png#1"),
                _font_comparison_row("page2.png#1"),
            ],
        )
        _write_jsonl(run_dir / "font-index.jsonl", [{"font_id": "font-a"}])
        return run_dir

    def fake_phase3_vision(**kwargs):
        calls["phase3_vision"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        _write_jsonl(
            run_dir / "font-selections.jsonl",
            [
                _font_selection_row("page1.png#1"),
                _font_selection_row("page2.png#1"),
            ],
        )
        _write_jsonl(run_dir / "reports" / "api-calls.jsonl", [{"record_id": "page1.png#1", "status": "ok"}])
        return run_dir

    def fake_phase4(**kwargs):
        calls["phase4"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        _write_jsonl(
            run_dir / "layout-results.jsonl",
            [
                _layout_row("page1.png#1", "page1.png", [10, 10, 110, 90]),
                _layout_row("page2.png#1", "page2.png", [20, 20, 120, 100]),
            ],
        )
        return run_dir

    def fake_phase6(**kwargs):
        calls["phase6"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        _write_jsonl(
            run_dir / "cleanup-results.jsonl",
            [
                _cleanup_row("page1.png#1", "page1.png", [10, 10, 110, 90]),
                _cleanup_row("page2.png#1", "page2.png", [20, 20, 120, 100]),
            ],
        )
        return run_dir

    def fake_phase7(**kwargs):
        calls["phase7"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        _write_jsonl(
            run_dir / "preview-results.jsonl",
            [
                {
                    "image_name": "page1.png",
                    "status": "page_preview_generated",
                    "records": [{"record_id": "page1.png#1"}, {"record_id": "page2.png#1"}],
                    "preview": {"page_preview_path": "preview.png"},
                }
            ],
        )
        (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
        return run_dir

    def fake_phase8(**kwargs):
        calls["phase8"] = kwargs
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        run_dir.mkdir(parents=True)
        manifest = {
            "summary": {"page_count": 1, "record_count": 2},
            "pages": [{"image_name": "page1.png", "repaired_image_path": "cleaned.png", "layers": [{}, {}]}],
        }
        (run_dir / "photoshop-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run_dir / "photoshop-import.jsx").write_text("// fake", encoding="utf-8")
        return run_dir

    monkeypatch.setattr(pipeline, "run_phase1", fake_phase1)
    monkeypatch.setattr(pipeline, "run_phase2", fake_phase2)
    monkeypatch.setattr(pipeline, "run_phase3", fake_phase3)
    monkeypatch.setattr(pipeline, "run_phase3_vision_selection", fake_phase3_vision)
    monkeypatch.setattr(pipeline, "run_phase4", fake_phase4)
    monkeypatch.setattr(pipeline, "run_phase6_bubble_cleanup", fake_phase6)
    monkeypatch.setattr(pipeline, "run_phase7_preview", fake_phase7)
    monkeypatch.setattr(pipeline, "run_phase8_photoshop_export", fake_phase8)


def _write_labelplus_project(root: Path) -> Path:
    Image.new("RGB", (200, 200), "white").save(root / "page1.png")
    Image.new("RGB", (200, 200), "white").save(root / "page2.png")
    labelplus_file = root / "翻译_0.txt"
    labelplus_file.write_text(
        "\n".join(
            [
                "1,0",
                "-",
                "框内",
                "框外",
                "-",
                "comment",
                ">>>>>>>>[page1.png]<<<<<<<<",
                "----------------[1]----------------[0.25,0.25,1]",
                "框内一",
                "----------------[2]----------------[0.50,0.50,2]",
                "框外一",
                ">>>>>>>>[page2.png]<<<<<<<<",
                "----------------[1]----------------[0.40,0.40,1]",
                "框内二",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return labelplus_file


def _detection_row(record_id: str, image_name: str, bbox: list[int], label: str, distance: float) -> dict:
    return {
        "record_id": record_id,
        "image_name": image_name,
        "image_path": str(Path(image_name)),
        "group_name": "框内",
        "translated_text": "测试",
        "status": "ok",
        "selected_text_box_xyxy": bbox,
        "selected_text_full_xyxy": bbox,
        "selected_text_body_xyxy": bbox,
        "comic_text_bubble_match": {
            "status": "matched",
            "selected_label": label,
            "selected_score": 0.9,
            "distance_px": distance,
        },
    }


def _font_comparison_row(record_id: str) -> dict:
    return {
        "record_id": record_id,
        "status": "candidates_generated",
        "candidate_fonts": [{"font_id": "font-a", "path": "font.ttf"}],
    }


def _font_selection_row(record_id: str) -> dict:
    return {
        "record_id": record_id,
        "image_name": "page1.png",
        "translated_text": "测试",
        "status": "selected",
        "selected_font_id": "font-a",
        "selected_font": {"font_id": "font-a", "path": "font.ttf"},
        "selection_source": "mimo_vision",
    }


def _mimo_success(record_id: str, font_id: str) -> dict:
    row = _font_selection_row(record_id)
    row["selected_font_id"] = font_id
    row["selected_font"] = {"font_id": font_id, "path": f"{font_id}.ttf"}
    return row


def _layout_row(record_id: str, image_name: str, bbox: list[int]) -> dict:
    return {
        "record_id": record_id,
        "image_name": image_name,
        "translated_text": "测试",
        "status": "layout_generated",
        "layout": {
            "font_size": 24,
            "orientation": "horizontal",
            "line_breaks": "测试",
            "target_bbox": bbox,
        },
    }


def _cleanup_row(record_id: str, image_name: str, bbox: list[int]) -> dict:
    return {
        "record_id": record_id,
        "image_name": image_name,
        "translated_text": "测试",
        "status": "cleaned",
        "cleanup": {
            "method": "text_mask_inpaint",
            "bbox": bbox,
            "cleaned_crop_path": "cleaned.png",
            "layout_text_bbox": bbox,
        },
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
