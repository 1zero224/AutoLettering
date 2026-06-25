import json
from pathlib import Path

from PIL import Image, ImageDraw

import autolettering.phase6_replacement_sheet as replacement_sheet
from autolettering.phase6_replacement_quality import (
    build_replacement_quality_prompt,
    parse_replacement_quality_response,
    run_phase6_replacement_quality,
)


class FakeReplacementQualityClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.image_paths: list[Path] = []

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        image_path = Path(image_path)
        assert image_path.exists()
        assert image_path.parent.name == "replacement_quality_sheets"
        assert kind == "phase6_replacement_quality"
        assert max_completion_tokens == 1200
        assert "exact Simplified Chinese text" in prompt
        assert "新川崎（暂）" in prompt
        assert "暫 is incorrect" in prompt
        assert "Do not select a different text region" in prompt
        assert "新川崎（仮）" in prompt
        self.prompts.append(prompt)
        self.image_paths.append(image_path)
        return {
            "raw_text": json.dumps(
                {
                    "score": 6,
                    "usable": False,
                    "exact_text_correct": True,
                    "simplified_chinese_correct": True,
                    "no_japanese_remaining": True,
                    "region_correct": True,
                    "style_consistent": False,
                    "outside_mask_preserved": True,
                    "issues": ["style_mismatch"],
                    "summary": "The text is readable but the style is too bold.",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path), "prompt_chars": len(prompt)},
            "response": {"status": "ok"},
        }


def test_parse_replacement_quality_response_accepts_json_fences():
    result = parse_replacement_quality_response(
        """```json
{"score":8,"usable":true,"exact_text_correct":true,"no_japanese_remaining":true,
"simplified_chinese_correct":false,"region_correct":true,"style_consistent":false,"outside_mask_preserved":true,
"issues":["style_mismatch"],"summary":"text ok, style off"}
```"""
    )

    assert result.status == "evaluated"
    assert result.score == 8
    assert result.usable is True
    assert result.exact_text_correct is True
    assert result.simplified_chinese_correct is False
    assert result.no_japanese_remaining is True
    assert result.region_correct is True
    assert result.style_consistent is False
    assert result.outside_mask_preserved is True
    assert result.issues == ["style_mismatch"]
    assert result.summary == "text ok, style off"
    assert result.failure_reason is None


def test_parse_replacement_quality_response_normalizes_contradictory_region_issue():
    result = parse_replacement_quality_response(
        json.dumps(
            {
                "score": 1,
                "usable": False,
                "exact_text_correct": False,
                "simplified_chinese_correct": False,
                "no_japanese_remaining": False,
                "region_correct": True,
                "style_consistent": False,
                "outside_mask_preserved": True,
                "issues": ["The text was placed in the wrong speech bubble."],
                "summary": "The replacement targeted the wrong region.",
            },
            ensure_ascii=False,
        )
    )

    assert result.region_correct is False
    assert "region_correct_overridden_from_issue_text" in result.issues


def test_parse_replacement_quality_response_does_not_override_negated_region_issue():
    result = parse_replacement_quality_response(
        json.dumps(
            {
                "score": 8,
                "usable": True,
                "exact_text_correct": True,
                "simplified_chinese_correct": True,
                "no_japanese_remaining": True,
                "region_correct": True,
                "style_consistent": True,
                "outside_mask_preserved": True,
                "issues": ["Not wrong region; placement matches target."],
                "summary": "No wrong region issue detected.",
            },
            ensure_ascii=False,
        )
    )

    assert result.region_correct is True
    assert "region_correct_overridden_from_issue_text" not in result.issues


def test_build_replacement_quality_prompt_is_strict_about_gpt_text():
    prompt = build_replacement_quality_prompt(
        {
            "record_id": "GBC06_17.png#3",
            "translated_text": "新川崎（暂）",
            "fallback_locator_validation": {"visible_original_text": "新川崎（仮）"},
            "cleanup": {"replacement_method": "gpt_image2_masked_edit", "mask_bbox": [1, 2, 30, 40]},
        }
    )

    assert "GBC06_17.png#3" in prompt
    assert "新川崎（暂）" in prompt
    assert "gpt_image2_masked_edit" in prompt
    assert "exact Simplified Chinese text" in prompt
    assert "暫 is incorrect" in prompt
    assert "Japanese text remains" in prompt
    assert "outside the mask" in prompt
    assert "Do not select a different text region" in prompt
    assert "新川崎（仮）" in prompt
    assert "If the replacement appears in a different bubble" in prompt


def test_run_phase6_replacement_quality_writes_results_and_review_sheet(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    original = _write_image(tmp_path / "original.png", "black", text="jp")
    validation = _write_image(tmp_path / "validation.png", "gray", text="box")
    edit_input = _write_image(tmp_path / "edit-input.png", "black", text="jp")
    mask = _write_mask(tmp_path / "mask.png")
    replacement = _write_image(tmp_path / "replacement.png", "black", text="cn")
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            _replacement_row(
                original=original,
                validation=validation,
                edit_input=edit_input,
                mask=mask,
                replacement=replacement,
            )
        ],
    )

    run_dir = run_phase6_replacement_quality(
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-replacement-quality-test",
        sample_limit=1,
        client=FakeReplacementQualityClient(),
    )

    rows = _read_jsonl(run_dir / "replacement-quality.jsonl")
    api_calls = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")
    report = (run_dir / "reports" / "phase6-replacement-quality-report.md").read_text(encoding="utf-8")

    assert rows[0]["record_id"] == "GBC06_17.png#3"
    assert rows[0]["status"] == "evaluated"
    assert rows[0]["usable"] is False
    assert rows[0]["exact_text_correct"] is True
    assert rows[0]["simplified_chinese_correct"] is True
    assert rows[0]["style_consistent"] is False
    assert rows[0]["replacement_method"] == "gpt_image2_masked_edit"
    assert rows[0]["source_request_image_path"] == str(edit_input)
    assert rows[0]["source_request_mask_path"] == str(mask)
    assert rows[0]["source_replacement_crop_path"] == str(replacement)
    assert rows[0]["source_cleaned_crop_path"] == str(original)
    assert rows[0]["source_local_context_bbox"] == [5, 6, 205, 126]
    assert rows[0]["source_mask_bbox"] == [30, 40, 180, 90]
    assert rows[0]["raw_model_text"]
    sheet_path = Path(rows[0]["evaluation_image_path"])
    assert sheet_path.exists()
    with Image.open(sheet_path).convert("RGB") as sheet:
        assert 0.55 <= sheet.width / sheet.height <= 1.9
        assert _has_nonwhite_pixel(sheet, (10, 10, sheet.width - 10, min(70, sheet.height)))
    assert (run_dir / "debug" / "replacement_target_crops" / "GBC06-17-png-3.png").exists()
    assert api_calls[0]["status"] == "ok"
    assert "api_key" not in json.dumps(api_calls[0]).lower()
    assert "Usable replacements: 0" in report
    assert "debug/replacement_quality_sheets/*.png" in report


def test_run_phase6_replacement_quality_skips_pending_or_non_gpt_rows(tmp_path: Path):
    cleanup_run = tmp_path / "phase6"
    crop = _write_image(tmp_path / "crop.png", "black", text="x")
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            {
                "record_id": "page.png#dry",
                "status": "cleaned",
                "translated_text": "译文",
                "cleanup": {
                    "method": "gpt_image2_masked_edit",
                    "replacement_method": "gpt_image2_masked_edit",
                    "cleaned_crop_path": str(crop),
                },
                "gpt_image2_edit": {"status": "dry_run"},
            },
            {
                "record_id": "page.png#lama",
                "status": "cleaned",
                "translated_text": "译文",
                "cleanup": {
                    "method": "bt_lama_large",
                    "cleaned_crop_path": str(crop),
                    "replacement_crop_path": str(crop),
                },
                "gpt_image2_edit": {"status": "not_applicable"},
            },
        ],
    )
    client = FakeReplacementQualityClient()

    run_dir = run_phase6_replacement_quality(
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-replacement-quality-skip-test",
        sample_limit=5,
        client=client,
    )

    assert _read_jsonl(run_dir / "replacement-quality.jsonl") == []
    assert _read_jsonl(run_dir / "reports" / "api-calls.jsonl") == []
    assert client.prompts == []


def test_run_phase6_replacement_quality_resolves_repo_relative_paths_from_any_cwd(tmp_path: Path, monkeypatch):
    cleanup_run = tmp_path / "phase6"
    repo_root = tmp_path / "repo"
    original = _write_image(repo_root / "outputs" / "run" / "original.png", "black", text="jp")
    validation = _write_image(repo_root / "outputs" / "run" / "validation.png", "gray", text="box")
    edit_input = _write_image(repo_root / "outputs" / "run" / "edit-input.png", "black", text="jp")
    mask = _write_mask(repo_root / "outputs" / "run" / "mask.png")
    replacement = _write_image(repo_root / "outputs" / "run" / "replacement.png", "black", text="cn")
    monkeypatch.chdir(tmp_path)
    _write_jsonl(
        cleanup_run / "cleanup-results.jsonl",
        [
            _replacement_row(
                original=_repo_relative(repo_root, original),
                validation=_repo_relative(repo_root, validation),
                edit_input=_repo_relative(repo_root, edit_input),
                mask=_repo_relative(repo_root, mask),
                replacement=_repo_relative(repo_root, replacement),
            )
        ],
    )

    run_dir = run_phase6_replacement_quality(
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-replacement-quality-path-test",
        sample_limit=1,
        client=FakeReplacementQualityClient(),
        path_roots=[repo_root],
    )

    rows = _read_jsonl(run_dir / "replacement-quality.jsonl")
    assert len(rows) == 1
    assert Path(rows[0]["evaluation_image_path"]).exists()


def test_replacement_sheet_prefers_existing_cjk_font_for_readable_labels(tmp_path: Path, monkeypatch):
    chosen = []
    fake_font = tmp_path / "fake-cjk.ttf"
    fake_font.write_bytes(b"fake")

    def fake_truetype(path, size, *args, **kwargs):
        if Path(path) == fake_font:
            chosen.append(Path(path))
            return object()
        raise OSError("missing font")

    monkeypatch.setattr(replacement_sheet, "_cjk_font_candidates", lambda: [fake_font])
    monkeypatch.setattr(replacement_sheet.ImageFont, "truetype", fake_truetype)

    font = replacement_sheet._font(13)

    assert font is not None
    assert chosen == [fake_font]


def _replacement_row(original: Path | str, validation: Path | str, edit_input: Path | str, mask: Path | str, replacement: Path | str) -> dict:
    return {
        "record_id": "GBC06_17.png#3",
        "image_name": "GBC06_17.png",
        "translated_text": "新川崎（暂）",
        "status": "cleaned",
        "cleanup": {
            "method": "gpt_image2_masked_edit",
            "bbox": [10, 20, 210, 160],
            "mask_bbox": [30, 40, 180, 90],
            "cleaned_crop_path": str(original),
            "replacement_method": "gpt_image2_masked_edit",
            "replacement_crop_path": str(replacement),
        },
        "fallback_locator_validation": {
            "validation_image_path": str(validation),
            "visible_original_text": "新川崎（仮）",
        },
        "gpt_image2_edit": {
            "status": "ok",
            "request": {"image_path": str(edit_input), "mask_path": str(mask), "target_size": [220, 140]},
            "edit_context": {
                "input_path": str(edit_input),
                "mask_path": str(mask),
                "local_context_bbox": [5, 6, 205, 126],
            },
            "normalized_output_path": str(replacement),
        },
    }


def _write_image(path: Path, background: str, text: str) -> Path:
    image = Image.new("RGB", (220, 140), background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 35, 190, 85), outline="white", width=2)
    draw.text((35, 50), text, fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _write_mask(path: Path) -> Path:
    image = Image.new("RGBA", (220, 140), (0, 0, 0, 255))
    alpha = Image.new("L", (220, 140), 255)
    ImageDraw.Draw(alpha).rectangle((45, 40, 180, 90), fill=0)
    Image.merge("RGBA", [Image.new("L", (220, 140), 0)] * 3 + [alpha]).save(path)
    return path


def _repo_relative(repo_root: Path, path: Path) -> str:
    return str(path.relative_to(repo_root))


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
