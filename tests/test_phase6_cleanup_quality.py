import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.phase6_cleanup_quality import (
    build_cleanup_quality_prompt,
    parse_cleanup_quality_response,
    run_phase6_cleanup_quality,
)


class FakeCleanupQualityClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        image_path = Path(image_path)
        assert image_path.exists()
        assert image_path.parent.name == "cleanup_quality_sheets"
        assert kind == "phase6_cleanup_quality"
        assert max_completion_tokens == 900
        assert "AFTER cleaned crop" in prompt
        assert "visible original Japanese text" in prompt
        self.prompts.append(prompt)
        return {
            "raw_text": json.dumps(
                {
                    "score": 4,
                    "usable": False,
                    "original_text_removed": False,
                    "art_preserved": True,
                    "issues": ["visible_original_text"],
                    "summary": "Dark Japanese-shaped residue is still visible.",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path), "prompt_chars": len(prompt)},
            "response": {"status": "ok"},
        }


def test_parse_cleanup_quality_response_extracts_structured_json():
    result = parse_cleanup_quality_response(
        '{"score":4,"usable":false,"original_text_removed":false,'
        '"art_preserved":true,"issues":["visible_original_text"],"summary":"residue"}'
    )

    assert result.status == "evaluated"
    assert result.score == 4
    assert result.usable is False
    assert result.original_text_removed is False
    assert result.art_preserved is True
    assert result.issues == ["visible_original_text"]
    assert result.summary == "residue"
    assert result.failure_reason is None


def test_build_cleanup_quality_prompt_focuses_on_cleanup_not_translation():
    prompt = build_cleanup_quality_prompt(
        {
            "record_id": "page.png#1",
            "translated_text": "漫画第一卷",
            "cleanup": {"method": "bt_lama_large_inpaint", "bbox": [1, 2, 3, 4]},
        }
    )

    assert "page.png#1" in prompt
    assert "bt_lama_large_inpaint" in prompt
    assert "Do not require Chinese translated text" in prompt
    assert "visible original Japanese text" in prompt
    assert "Return only JSON" in prompt


def test_run_phase6_cleanup_quality_writes_results_and_review_sheet(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    before_after = tmp_path / "before-after.png"
    _write_before_after(before_after)
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#1",
                "image_name": "page.png",
                "translated_text": "背景文字",
                "status": "cleaned",
                "cleanup": {
                    "method": "bt_lama_large_inpaint",
                    "bbox": [10, 20, 40, 80],
                    "before_after_path": str(before_after),
                },
            }
        ],
    )

    run_dir = run_phase6_cleanup_quality(
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-cleanup-quality-test",
        sample_limit=1,
        client=FakeCleanupQualityClient(),
    )

    rows = _read_jsonl(run_dir / "cleanup-quality.jsonl")
    api_calls = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")
    report = (run_dir / "reports" / "phase6-cleanup-quality-report.md").read_text(encoding="utf-8")

    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "evaluated"
    assert rows[0]["usable"] is False
    assert rows[0]["original_text_removed"] is False
    assert rows[0]["art_preserved"] is True
    assert rows[0]["issues"] == ["visible_original_text"]
    sheet_path = Path(rows[0]["evaluation_image_path"])
    assert sheet_path.exists()
    with Image.open(sheet_path).convert("RGB") as sheet:
        assert sheet.width > sheet.height
        assert _has_nonwhite_pixel(sheet, (10, 10, sheet.width - 10, 50))
    assert api_calls[0]["status"] == "ok"
    assert "api_key" not in json.dumps(api_calls[0]).lower()
    assert "Usable cleanups: 0" in report


def test_run_phase6_cleanup_quality_skips_gpt_masked_edit_records(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    single_crop = tmp_path / "gpt-context.png"
    Image.new("RGB", (120, 80), "white").save(single_crop)
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#fallback",
                "image_name": "page.png",
                "translated_text": "背景文字",
                "status": "cleaned",
                "cleanup": {
                    "method": "gpt_image2_masked_edit",
                    "bbox": [10, 20, 40, 80],
                    "before_after_path": str(single_crop),
                    "replacement_method": "gpt_image2_masked_edit",
                },
            }
        ],
    )
    client = FakeCleanupQualityClient()

    run_dir = run_phase6_cleanup_quality(
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-cleanup-quality-skip-gpt",
        sample_limit=5,
        client=client,
    )

    assert _read_jsonl(run_dir / "cleanup-quality.jsonl") == []
    assert _read_jsonl(run_dir / "reports" / "api-calls.jsonl") == []
    assert client.prompts == []


def test_run_phase6_cleanup_quality_skips_records_with_gpt_replacement_method(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    before_after = tmp_path / "local-before-after.png"
    _write_before_after(before_after)
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#gpt-final",
                "image_name": "page.png",
                "translated_text": "背景文字",
                "status": "cleaned",
                "cleanup": {
                    "method": "local_diffusion_inpaint",
                    "bbox": [10, 20, 40, 80],
                    "before_after_path": str(before_after),
                    "replacement_method": "gpt_image2_masked_edit",
                    "replacement_crop_path": str(before_after),
                },
            }
        ],
    )
    client = FakeCleanupQualityClient()

    run_dir = run_phase6_cleanup_quality(
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-cleanup-quality-skip-replacement-method",
        sample_limit=5,
        client=client,
    )

    assert _read_jsonl(run_dir / "cleanup-quality.jsonl") == []
    assert _read_jsonl(run_dir / "reports" / "api-calls.jsonl") == []
    assert client.prompts == []


def test_run_phase6_cleanup_quality_splits_tall_vertical_crops_for_review(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    before_after = tmp_path / "tall-before-after.png"
    _write_tall_before_after(before_after)
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#tall",
                "image_name": "page.png",
                "translated_text": "背景文字",
                "status": "cleaned",
                "cleanup": {
                    "method": "bt_lama_large_inpaint",
                    "bbox": [10, 20, 50, 920],
                    "before_after_path": str(before_after),
                },
            }
        ],
    )
    client = FakeCleanupQualityClient()

    run_dir = run_phase6_cleanup_quality(
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-cleanup-quality-tall",
        sample_limit=1,
        client=client,
    )

    rows = _read_jsonl(run_dir / "cleanup-quality.jsonl")
    with Image.open(rows[0]["evaluation_image_path"]).convert("RGB") as sheet:
        assert sheet.width >= 900
        assert sheet.height >= 650
        assert sheet.width / sheet.height < 2.0
    assert "Long vertical cleanup crops may be split into numbered segments" in client.prompts[0]
    assert "Judge segment 1 -> 2 -> 3" in client.prompts[0]


def _write_before_after(path: Path) -> None:
    image = Image.new("RGB", (120, 80), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 20, 48, 60), fill="black")
    draw.rectangle((72, 20, 108, 60), fill=(50, 50, 50))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_tall_before_after(path: Path) -> None:
    image = Image.new("RGB", (80, 900), "white")
    draw = ImageDraw.Draw(image)
    for offset in (40, 320, 620):
        draw.rectangle((14, offset, 28, offset + 160), fill="black")
        draw.rectangle((54, offset, 68, offset + 160), fill=(60, 60, 60))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _has_nonwhite_pixel(image: Image.Image, box: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = box
    for y in range(y1, y2):
        for x in range(x1, x2):
            if image.getpixel((x, y)) != (255, 255, 255):
                return True
    return False
