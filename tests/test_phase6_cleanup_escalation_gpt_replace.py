import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.models.gpt_image import GptImageConfig
from autolettering.phase6_cleanup_escalation_gpt_replace import run_phase6_cleanup_escalation_gpt_replace


def test_run_phase6_cleanup_escalation_gpt_replace_consumes_gate_candidates(tmp_path: Path, monkeypatch):
    cleanup_run = tmp_path / "phase6-cleanup"
    gate_run = tmp_path / "phase6-gate"
    input_crop = _write_tall_crop(cleanup_run / "crops" / "input" / "page-1.png")
    text_mask = _write_text_mask(cleanup_run / "crops" / "mask" / "page-1.png")
    gpt_mask = _write_gpt_mask(cleanup_run / "crops" / "gpt_mask" / "page-1.png")
    _write_cleanup_row(cleanup_run / "cleanup-results.jsonl", input_crop, text_mask, gpt_mask)
    _write_gate_manifest(gate_run / "manifest.json", cleanup_run)
    _write_candidate(gate_run / "cleanup-escalation-candidates.jsonl")
    fake_client = FakeGptClient()
    monkeypatch.setattr("autolettering.phase6_cleanup_escalation_gpt_replace.GptImageEditClient", lambda config: fake_client)

    run_dir = run_phase6_cleanup_escalation_gpt_replace(
        gate_run_dir=gate_run,
        output_root=tmp_path / "outputs",
        run_id="escalation-gpt-test",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        context_padding=4,
        rect_mask_expand_px=1,
        max_segment_chars=8,
        max_segment_height=140,
    )

    rows = _read_jsonl(run_dir / "cleanup-escalation-gpt-results.jsonl")
    cleanup_rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "processed"
    assert rows[0]["segmented_gpt_replace"]["status"] == "ok"
    assert rows[0]["segmented_gpt_replace"]["segment_count"] == 3
    assert [segment["target_text"] for segment in rows[0]["segments"]] == [
        "漫画第一卷",
        "2026年6月",
        "29日发售！！",
    ]
    assert [call["target_text"] for call in fake_client.calls] == ["漫画第一卷", "2026年6月", "29日发售！！"]
    assert rows[0]["segments"][-1]["context_segment_bbox"][3] >= rows[0]["context"]["local_target_bbox"][3]
    with Image.open(rows[0]["segments"][0]["mask_path"]) as first_mask:
        alpha = first_mask.convert("RGBA").getchannel("A")
        transparent = sum(1 for value in alpha.getdata() if value == 0)
        transparent_ratio = transparent / (alpha.width * alpha.height)
        assert transparent_ratio > 0.18
    assert Path(rows[0]["segmented_gpt_replace"]["composed_context_path"]).exists()
    assert Path(rows[0]["segmented_gpt_replace"]["target_crop_path"]).exists()
    assert (run_dir / "visuals" / "cleanup-escalation-gpt-grid.png").exists()
    assert manifest["replacement_cleanup_count"] == 1
    assert manifest["gpt_ok_count"] == 1

    cleanup = cleanup_rows[0]["cleanup"]
    assert cleanup_rows[0]["status"] == "cleaned"
    assert cleanup_rows[0]["gpt_image2_edit"]["status"] == "ok"
    assert cleanup["method"] == "segmented_gpt_image2_masked_edit"
    assert cleanup["replacement_method"] == "gpt_image2_masked_edit"
    assert cleanup["replacement_crop_path"] == rows[0]["segmented_gpt_replace"]["target_crop_path"]
    assert cleanup["cleaned_crop_path"] == str(input_crop)
    assert cleanup["mask_bbox"] == [10, 20, 90, 380]
    assert cleanup["text_overlay_required"] is False


def test_run_phase6_cleanup_escalation_gpt_replace_writes_dry_run_request(tmp_path: Path):
    cleanup_run = tmp_path / "phase6-cleanup"
    gate_run = tmp_path / "phase6-gate"
    input_crop = _write_tall_crop(cleanup_run / "crops" / "input" / "page-1.png")
    text_mask = _write_text_mask(cleanup_run / "crops" / "mask" / "page-1.png")
    gpt_mask = _write_gpt_mask(cleanup_run / "crops" / "gpt_mask" / "page-1.png")
    _write_cleanup_row(cleanup_run / "cleanup-results.jsonl", input_crop, text_mask, gpt_mask)
    _write_gate_manifest(gate_run / "manifest.json", cleanup_run)
    _write_candidate(gate_run / "cleanup-escalation-candidates.jsonl")

    run_dir = run_phase6_cleanup_escalation_gpt_replace(
        gate_run_dir=gate_run,
        output_root=tmp_path / "outputs",
        run_id="escalation-gpt-dry-run-test",
        sample_limit=1,
        call_gpt_image=False,
        max_segment_height=140,
    )

    rows = _read_jsonl(run_dir / "cleanup-escalation-gpt-results.jsonl")
    cleanup_rows = _read_jsonl(run_dir / "cleanup-results.jsonl")

    assert rows[0]["segmented_gpt_replace"]["status"] == "dry_run"
    assert rows[0]["segments"][0]["gpt_image2"]["status"] == "dry_run"
    assert rows[0]["segments"][0]["gpt_image2"]["request"]["mode"] == "cleanup_escalation_segmented_masked_chinese_replacement"
    assert cleanup_rows[0]["status"] == "failed"
    assert cleanup_rows[0]["gpt_image2_edit"]["status"] == "dry_run"
    assert cleanup_rows[0]["cleanup"]["text_overlay_required"] is True


def test_run_phase6_cleanup_escalation_gpt_replace_can_keep_full_text_in_one_segment(tmp_path: Path):
    cleanup_run = tmp_path / "phase6-cleanup"
    gate_run = tmp_path / "phase6-gate"
    input_crop = _write_tall_crop(cleanup_run / "crops" / "input" / "page-1.png")
    text_mask = _write_text_mask(cleanup_run / "crops" / "mask" / "page-1.png")
    gpt_mask = _write_gpt_mask(cleanup_run / "crops" / "gpt_mask" / "page-1.png")
    _write_cleanup_row(cleanup_run / "cleanup-results.jsonl", input_crop, text_mask, gpt_mask)
    _write_gate_manifest(gate_run / "manifest.json", cleanup_run)
    _write_candidate(gate_run / "cleanup-escalation-candidates.jsonl")

    run_dir = run_phase6_cleanup_escalation_gpt_replace(
        gate_run_dir=gate_run,
        output_root=tmp_path / "outputs",
        run_id="escalation-gpt-single-segment-test",
        sample_limit=1,
        call_gpt_image=False,
        max_segment_height=140,
        single_segment=True,
    )

    rows = _read_jsonl(run_dir / "cleanup-escalation-gpt-results.jsonl")

    assert rows[0]["segmented_gpt_replace"]["segment_count"] == 1
    assert rows[0]["segments"][0]["target_text"] == "漫画第一卷\n2026年6月29日发售！！"
    _assert_bbox_contains(rows[0]["segments"][0]["context_segment_bbox"], rows[0]["context"]["local_target_bbox"])
    request = rows[0]["segments"][0]["gpt_image2"]["request"]
    assert request["target_text"] == "漫画第一卷\n2026年6月29日发售！！"


class FakeGptClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as image:
            target_text = prompt.split("Target Chinese text: ", 1)[-1]
            self.calls.append({"target_text": target_text, "image_size": image.size})
            edited = image.convert("RGB").copy()
        draw = ImageDraw.Draw(edited)
        draw.rectangle((4, 4, edited.width - 4, edited.height - 4), fill="white")
        draw.text((8, 8), target_text, fill="black")
        edited.save(output)
        return {"status": "ok", "output_path": str(output), "response": {"usage": {"total_tokens": 1}}}


def _write_tall_crop(path: Path) -> Path:
    image = Image.new("RGB", (80, 360), (205, 58, 72))
    draw = ImageDraw.Draw(image)
    for y in range(28, 330, 42):
        draw.rectangle((30, y, 50, y + 24), fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _assert_bbox_contains(outer: list[int], inner: list[int]) -> None:
    assert outer[0] <= inner[0]
    assert outer[1] <= inner[1]
    assert outer[2] >= inner[2]
    assert outer[3] >= inner[3]


def _write_text_mask(path: Path) -> Path:
    image = Image.new("L", (80, 360), 0)
    draw = ImageDraw.Draw(image)
    for y in range(28, 330, 42):
        draw.rectangle((28, y, 52, y + 24), fill=255)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _write_gpt_mask(path: Path) -> Path:
    alpha = Image.new("L", (80, 360), 255)
    draw = ImageDraw.Draw(alpha)
    for y in range(28, 330, 42):
        draw.rectangle((28, y, 52, y + 24), fill=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.merge("RGBA", [Image.new("L", (80, 360), 0)] * 3 + [alpha]).save(path)
    return path


def _write_cleanup_row(path: Path, input_crop: Path, text_mask: Path, gpt_mask: Path) -> None:
    row = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "漫画第一卷\n2026年6月29日发售！！",
        "status": "cleaned",
        "cleanup": {
            "method": "bt_lama_large_inpaint",
            "route": "cta_mask_lama_large_512px",
            "text_region_source": "ctd_refined_mask_component",
            "bbox": [10, 20, 90, 380],
            "input_crop_path": str(input_crop),
            "text_mask_path": str(text_mask),
            "gpt_mask_path": str(gpt_mask),
            "cleaned_crop_path": str(input_crop),
            "before_after_path": str(input_crop),
            "source_mask_path": str(text_mask),
            "text_overlay_required": True,
        },
        "gpt_image2_edit": {"status": "not_applicable", "reason": "cta_mask_matched_inpaint_path"},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_gate_manifest(path: Path, cleanup_run: Path) -> None:
    payload = {
        "schema_version": "autolettering.phase6_cleanup_gate.v1",
        "cleanup_run_dir": str(cleanup_run),
        "cleanup_quality_run_dir": "quality",
        "candidate_count": 1,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_candidate(path: Path) -> None:
    row = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "status": "candidate",
        "recommended_route": "quality_gate_gpt_image2_masked_edit",
        "recommended_action": "run_gpt_image2_transparent_masked_replacement",
        "reason_codes": ["phase6_cleanup_original_text_visible", "phase6_cleanup_low_score"],
        "quality": {"score": 6, "original_text_removed": False, "evaluation_image_path": "quality.png"},
        "cleanup": {
            "method": "bt_lama_large_inpaint",
            "route": "cta_mask_lama_large_512px",
            "text_region_source": "ctd_refined_mask_component",
            "bbox": [10, 20, 90, 380],
            "source_mask_path": "mask.png",
        },
        "gpt_image2_contract": {
            "target_text": "漫画第一卷\n2026年6月29日发售！！",
            "mask_mode": "transparent_target_region_preserve_opaque_background",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
