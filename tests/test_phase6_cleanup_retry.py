import json
from pathlib import Path

from PIL import Image

from autolettering.phase6_cleanup_retry import run_phase6_cleanup_retry


class FakeQualityClient:
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        text = "ok"
        if "bt_patchmatch_inpaint" in prompt:
            payload = {
                "score": 8,
                "usable": True,
                "original_text_removed": True,
                "art_preserved": True,
                "issues": [],
                "summary": "Patchmatch cleanup is usable.",
            }
        else:
            payload = {
                "score": 2,
                "usable": False,
                "original_text_removed": False,
                "art_preserved": True,
                "issues": ["visible_original_text"],
                "summary": "Residual text remains.",
            }
        return {
            "raw_text": json.dumps(payload),
            "request": {"kind": kind, "image_path": str(image_path), "prompt_chars": len(prompt), "text": text},
            "response": {"status": "ok"},
        }


class ScoreByMethodQualityClient:
    def __init__(self, scores: dict[str, int | None]) -> None:
        self.scores = scores

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        method = next((name for name in self.scores if name in prompt), "unknown")
        score = self.scores.get(method)
        payload = {
            "usable": False,
            "original_text_removed": False,
            "art_preserved": True,
            "issues": ["visible_original_text"],
            "summary": f"{method} score {score}",
        }
        if score is not None:
            payload["score"] = score
        return {
            "raw_text": json.dumps(payload),
            "request": {"kind": kind, "image_path": str(image_path), "prompt_chars": len(prompt)},
            "response": {"status": "ok"},
        }


def test_run_phase6_cleanup_retry_runs_candidate_methods_and_selects_best(tmp_path: Path, monkeypatch):
    detection_run = tmp_path / "phase2"
    quality_run = tmp_path / "quality"
    _write_detection(detection_run / "detections.jsonl", tmp_path / "page.png")
    _write_cleanup_quality_failure(quality_run / "cleanup-quality.jsonl")
    calls: list[dict] = []

    def fake_cleanup(**kwargs):
        calls.append(kwargs)
        method = kwargs["inpaint_method"]
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        cleanup_dir = run_dir / "crops"
        cleanup_dir.mkdir(parents=True, exist_ok=True)
        before_after = cleanup_dir / "before_after" / "page-png-1.png"
        before_after.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (120, 80), "white").save(before_after)
        row = {
            "record_id": "page.png#1",
            "image_name": "page.png",
            "translated_text": "背景文字",
            "status": "cleaned",
            "cleanup": {
                "method": f"{method}_inpaint",
                "bbox": [10, 20, 40, 80],
                "before_after_path": str(before_after),
            },
        }
        _write_jsonl(run_dir / "cleanup-results.jsonl", [row])
        return run_dir

    monkeypatch.setattr("autolettering.phase6_cleanup_retry.run_phase6_nonbubble_cleanup", fake_cleanup)

    run_dir = run_phase6_cleanup_retry(
        detection_run_dir=detection_run,
        cleanup_quality_run_dir=quality_run,
        output_root=tmp_path / "outputs",
        run_id="retry-test",
        methods=["bt_lama_large", "bt_patchmatch"],
        sample_limit=1,
        quality_client=FakeQualityClient(),
    )

    summary = json.loads((run_dir / "cleanup-retry-summary.json").read_text(encoding="utf-8"))
    assert [call["inpaint_method"] for call in calls] == ["bt_lama_large", "bt_patchmatch"]
    assert all(call["allow_cta_method_override"] is True for call in calls)
    assert summary["record_count"] == 1
    assert summary["records"][0]["record_id"] == "page.png#1"
    assert summary["records"][0]["best_method"] == "bt_patchmatch"
    assert summary["records"][0]["best_score"] == 8
    assert summary["records"][0]["usable"] is True
    assert (run_dir / "candidates" / "page-png-1__bt_lama_large" / "cleanup-results.jsonl").exists()
    assert (run_dir / "quality" / "page-png-1__bt_patchmatch" / "cleanup-quality.jsonl").exists()
    assert "bt_patchmatch" in (run_dir / "reports" / "phase6-cleanup-retry-report.md").read_text(encoding="utf-8")


def test_run_phase6_cleanup_retry_uses_per_record_candidate_directories(tmp_path: Path, monkeypatch):
    detection_run = tmp_path / "phase2"
    quality_run = tmp_path / "quality"
    _write_detection(detection_run / "detections.jsonl", tmp_path / "page.png")
    _append_detection(detection_run / "detections.jsonl", "page.png#2", tmp_path / "page2.png")
    _write_cleanup_quality_failure(quality_run / "cleanup-quality.jsonl")
    _append_cleanup_quality_failure(quality_run / "cleanup-quality.jsonl", "page.png#2")
    run_ids: list[str] = []

    def fake_cleanup(**kwargs):
        run_ids.append(kwargs["run_id"])
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        before_after = run_dir / "crops" / "before_after" / f"{kwargs['record_ids'][0].replace('#', '-')}.png"
        before_after.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (120, 80), "white").save(before_after)
        row = {
            "record_id": kwargs["record_ids"][0],
            "image_name": "page.png",
            "status": "cleaned",
            "cleanup": {
                "method": f"{kwargs['inpaint_method']}_inpaint",
                "bbox": [10, 20, 40, 80],
                "before_after_path": str(before_after),
            },
        }
        _write_jsonl(run_dir / "cleanup-results.jsonl", [row])
        return run_dir

    monkeypatch.setattr("autolettering.phase6_cleanup_retry.run_phase6_nonbubble_cleanup", fake_cleanup)

    run_dir = run_phase6_cleanup_retry(
        detection_run_dir=detection_run,
        cleanup_quality_run_dir=quality_run,
        output_root=tmp_path / "outputs",
        run_id="retry-two-records",
        methods=["bt_patchmatch"],
        sample_limit=2,
        quality_client=FakeQualityClient(),
    )

    assert run_ids == ["page-png-1__bt_patchmatch", "page-png-2__bt_patchmatch"]
    summary = json.loads((run_dir / "cleanup-retry-summary.json").read_text(encoding="utf-8"))
    dirs = [record["candidates"][0]["cleanup_run_dir"] for record in summary["records"]]
    assert len(set(dirs)) == 2
    assert all(Path(path).exists() for path in dirs)


def test_run_phase6_cleanup_retry_prefers_score_zero_over_missing_score(tmp_path: Path, monkeypatch):
    detection_run = tmp_path / "phase2"
    quality_run = tmp_path / "quality"
    _write_detection(detection_run / "detections.jsonl", tmp_path / "page.png")
    _write_cleanup_quality_failure(quality_run / "cleanup-quality.jsonl")

    def fake_cleanup(**kwargs):
        run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
        before_after = run_dir / "crops" / "before_after" / "page-png-1.png"
        before_after.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (120, 80), "white").save(before_after)
        row = {
            "record_id": "page.png#1",
            "status": "cleaned",
            "cleanup": {
                "method": f"{kwargs['inpaint_method']}_inpaint",
                "bbox": [10, 20, 40, 80],
                "before_after_path": str(before_after),
            },
        }
        _write_jsonl(run_dir / "cleanup-results.jsonl", [row])
        return run_dir

    monkeypatch.setattr("autolettering.phase6_cleanup_retry.run_phase6_nonbubble_cleanup", fake_cleanup)

    run_dir = run_phase6_cleanup_retry(
        detection_run_dir=detection_run,
        cleanup_quality_run_dir=quality_run,
        output_root=tmp_path / "outputs",
        run_id="retry-zero-score",
        methods=["missing_score", "zero_score"],
        sample_limit=1,
        quality_client=ScoreByMethodQualityClient({"missing_score": None, "zero_score": 0}),
    )

    summary = json.loads((run_dir / "cleanup-retry-summary.json").read_text(encoding="utf-8"))
    assert summary["records"][0]["best_method"] == "zero_score"
    assert summary["records"][0]["best_score"] == 0


def test_run_phase6_cleanup_retry_uses_only_cleanup_quality_failures(tmp_path: Path, monkeypatch):
    detection_run = tmp_path / "phase2"
    quality_run = tmp_path / "quality"
    _write_detection(detection_run / "detections.jsonl", tmp_path / "page.png")
    _write_jsonl(
        quality_run / "cleanup-quality.jsonl",
        [
            {
                "record_id": "page.png#1",
                "status": "evaluated",
                "usable": True,
                "original_text_removed": True,
                "art_preserved": True,
            }
        ],
    )
    calls: list[dict] = []

    def fake_cleanup(**kwargs):
        calls.append(kwargs)
        return Path(kwargs["output_root"]) / kwargs["run_id"]

    monkeypatch.setattr("autolettering.phase6_cleanup_retry.run_phase6_nonbubble_cleanup", fake_cleanup)

    run_dir = run_phase6_cleanup_retry(
        detection_run_dir=detection_run,
        cleanup_quality_run_dir=quality_run,
        output_root=tmp_path / "outputs",
        run_id="retry-no-failures",
        methods=["bt_patchmatch"],
        sample_limit=5,
        quality_client=FakeQualityClient(),
    )

    summary = json.loads((run_dir / "cleanup-retry-summary.json").read_text(encoding="utf-8"))
    assert calls == []
    assert summary["record_count"] == 0


def _write_detection(path: Path, image_path: Path) -> None:
    Image.new("RGB", (100, 120), "white").save(image_path)
    _write_jsonl(
        path,
        [
            {
                "record_id": "page.png#1",
                "image_name": "page.png",
                "image_path": str(image_path),
                "group_name": "框外",
                "status": "ok",
                "detection_method": "cta_mask",
                "selected_text_box_xyxy": [10, 20, 40, 80],
                "candidate_boxes": [
                    {"xyxy": [10, 20, 40, 80], "score": 1.0, "polarity": "dark_on_light"},
                ],
            }
        ],
    )


def _append_detection(path: Path, record_id: str, image_path: Path) -> None:
    Image.new("RGB", (100, 120), "white").save(image_path)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                {
                    "record_id": record_id,
                    "image_name": "page.png",
                    "image_path": str(image_path),
                    "group_name": "框外",
                    "status": "ok",
                    "selected_text_box_xyxy": [10, 20, 40, 80],
                    "candidate_boxes": [
                        {"xyxy": [10, 20, 40, 80], "score": 1.0, "polarity": "dark_on_light"},
                    ],
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _write_cleanup_quality_failure(path: Path) -> None:
    _write_jsonl(
        path,
        [
            {
                "record_id": "page.png#1",
                "status": "evaluated",
                "score": 2,
                "usable": False,
                "original_text_removed": False,
                "art_preserved": True,
                "issues": ["visible_original_text"],
            }
        ],
    )


def _append_cleanup_quality_failure(path: Path, record_id: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                {
                    "record_id": record_id,
                    "status": "evaluated",
                    "score": 1,
                    "usable": False,
                    "original_text_removed": False,
                    "art_preserved": True,
                    "issues": ["visible_original_text"],
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
