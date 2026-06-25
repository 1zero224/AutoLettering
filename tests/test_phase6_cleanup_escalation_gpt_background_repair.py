import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.models.gpt_image import GptImageConfig
from autolettering.phase6_cleanup_escalation_gpt_background_repair import (
    run_phase6_cleanup_escalation_gpt_background_repair,
)


def test_run_phase6_cleanup_escalation_gpt_background_repair_outputs_overlay_cleanup(tmp_path: Path, monkeypatch):
    cleanup_run = tmp_path / "phase6-cleanup"
    gate_run = tmp_path / "phase6-gate"
    input_crop = _write_tall_crop(cleanup_run / "crops" / "input" / "page-1.png")
    text_mask = _write_text_mask(cleanup_run / "crops" / "mask" / "page-1.png")
    _write_cleanup_row(cleanup_run / "cleanup-results.jsonl", input_crop, text_mask)
    _write_gate_manifest(gate_run / "manifest.json", cleanup_run)
    _write_candidate(gate_run / "cleanup-escalation-candidates.jsonl")
    fake_client = FakeGptBackgroundClient()
    monkeypatch.setattr(
        "autolettering.phase6_cleanup_escalation_gpt_background_repair.GptImageEditClient",
        lambda config: fake_client,
    )

    run_dir = run_phase6_cleanup_escalation_gpt_background_repair(
        gate_run_dir=gate_run,
        output_root=tmp_path / "outputs",
        run_id="escalation-gpt-background-test",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mask_dilation_px=4,
    )

    rows = _read_jsonl(run_dir / "cleanup-escalation-gpt-background-results.jsonl")
    cleanup_rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "processed"
    assert rows[0]["gpt_image2_background_repair"]["status"] == "ok"
    assert rows[0]["gpt_image2_background_repair"]["request"]["mode"] == "cleanup_escalation_background_repair_only"
    assert rows[0]["repair_input"]["mask_dilation_px"] == 4
    assert Path(rows[0]["gpt_image2_background_repair"]["normalized_output_path"]).exists()
    assert Path(rows[0]["before_after_path"]).exists()
    assert (run_dir / "visuals" / "cleanup-escalation-gpt-background-grid.png").exists()
    assert manifest["gpt_ok_count"] == 1

    cleanup_row = cleanup_rows[0]
    cleanup = cleanup_row["cleanup"]
    assert cleanup_row["status"] == "cleaned"
    assert cleanup_row["gpt_image2_edit"]["status"] == "ok"
    assert cleanup_row["gpt_image2_edit"]["mode"] == "background_repair_only"
    assert cleanup["method"] == "gpt_image2_background_repair"
    assert cleanup["text_overlay_required"] is True
    assert "replacement_crop_path" not in cleanup
    assert "replacement_method" not in cleanup
    assert cleanup["cleaned_crop_path"] == rows[0]["gpt_image2_background_repair"]["normalized_output_path"]
    assert fake_client.calls[0]["image_size"] == (80, 360)
    assert "Do not write" in fake_client.calls[0]["prompt"]


def test_run_phase6_cleanup_escalation_gpt_background_repair_writes_dry_run_contract(tmp_path: Path):
    cleanup_run = tmp_path / "phase6-cleanup"
    gate_run = tmp_path / "phase6-gate"
    input_crop = _write_tall_crop(cleanup_run / "crops" / "input" / "page-1.png")
    text_mask = _write_text_mask(cleanup_run / "crops" / "mask" / "page-1.png")
    _write_cleanup_row(cleanup_run / "cleanup-results.jsonl", input_crop, text_mask)
    _write_gate_manifest(gate_run / "manifest.json", cleanup_run)
    _write_candidate(gate_run / "cleanup-escalation-candidates.jsonl")

    run_dir = run_phase6_cleanup_escalation_gpt_background_repair(
        gate_run_dir=gate_run,
        output_root=tmp_path / "outputs",
        run_id="escalation-gpt-background-dry-test",
        sample_limit=1,
        call_gpt_image=False,
        mask_dilation_px=6,
    )

    rows = _read_jsonl(run_dir / "cleanup-escalation-gpt-background-results.jsonl")
    cleanup_rows = _read_jsonl(run_dir / "cleanup-results.jsonl")

    assert rows[0]["status"] == "failed"
    assert rows[0]["gpt_image2_background_repair"]["status"] == "dry_run"
    assert rows[0]["gpt_image2_background_repair"]["request"]["mode"] == "cleanup_escalation_background_repair_only"
    assert cleanup_rows[0]["status"] == "failed"
    assert cleanup_rows[0]["gpt_image2_edit"]["status"] == "dry_run"
    assert cleanup_rows[0]["gpt_image2_edit"]["mode"] == "background_repair_only"
    assert cleanup_rows[0]["cleanup"]["text_overlay_required"] is True
    assert cleanup_rows[0]["cleanup"]["cleaned_crop_path"] == str(input_crop)


class FakeGptBackgroundClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
        del mask_path
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as image:
            self.calls.append({"prompt": prompt, "image_size": image.size})
            repaired = Image.new("RGB", image.size, (205, 58, 72))
        repaired.save(output)
        return {"status": "ok", "output_path": str(output), "response": {"usage": {"total_tokens": 1}}}


def _write_tall_crop(path: Path) -> Path:
    image = Image.new("RGB", (80, 360), (205, 58, 72))
    draw = ImageDraw.Draw(image)
    for y in range(28, 330, 42):
        draw.rectangle((30, y, 50, y + 24), fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _write_text_mask(path: Path) -> Path:
    image = Image.new("L", (80, 360), 0)
    draw = ImageDraw.Draw(image)
    for y in range(28, 330, 42):
        draw.rectangle((28, y, 52, y + 24), fill=255)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _write_cleanup_row(path: Path, input_crop: Path, text_mask: Path) -> None:
    row = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "漫画第一卷\n2026年6月29日发售！！",
        "status": "cleaned",
        "cleanup": {
            "method": "bt_lama_large_inpaint",
            "route": "cta_mask_lama_large_512px",
            "bbox": [10, 20, 90, 380],
            "input_crop_path": str(input_crop),
            "text_mask_path": str(text_mask),
            "cleaned_crop_path": str(input_crop),
            "before_after_path": str(input_crop),
            "source_mask_path": str(text_mask),
            "text_overlay_required": True,
        },
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
        "recommended_route": "quality_gate_gpt_image2_background_repair",
        "recommended_action": "run_gpt_image2_background_repair_only",
        "reason_codes": ["phase6_cleanup_original_text_visible", "phase6_cleanup_low_score"],
        "quality": {"score": 6, "original_text_removed": False, "evaluation_image_path": "quality.png"},
        "cleanup": {
            "method": "bt_lama_large_inpaint",
            "route": "cta_mask_lama_large_512px",
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
