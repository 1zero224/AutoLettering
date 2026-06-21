# Phase 6 GBC06 Non-Bubble Cleanup Smoke Report

## Commands

Dry-run package generation:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase6-gbc06-nonbubble-dry-run-smoke --sample-limit 1
```

Controlled real `gpt-image-2` masked edit call:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase6-gbc06-nonbubble-gpt-image-smoke --sample-limit 1 --call-gpt-image
```

## Output

Dry-run directory:

```text
outputs/runs/phase6-gbc06-nonbubble-dry-run-smoke
```

Real-call directory:

```text
outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke
```

Generated artifacts:

- `cleanup-results.jsonl`
- `crops/input/*.png`
- `crops/mask/*.png`
- `crops/gpt_mask/*.png`
- `crops/cleaned/*.png`
- `crops/before_after/*.png`
- `gpt_image2/*.png` for real gpt-image-2 output
- `reports/phase6-nonbubble-report.md`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Record: `GBC06_01.png#16`
- Group: `框外`
- Translated text: `来自桃香的唐突的提案`
- Detection bbox: `[1349, 121, 1407, 378]`
- Local method: `local_diffusion_inpaint`
- Text mask pixels: `7779`
- Local input crop: `58 x 257`, `RGB`, non-empty
- Text mask: `58 x 257`, `L`, non-empty
- GPT edit mask: `58 x 257`, `RGBA`, non-empty
- Local cleaned crop: `58 x 257`, `RGB`, non-empty
- GPT status: `ok`
- GPT model: `gpt-image-2`
- GPT prompt length: `213`
- GPT usage total tokens: `1690`
- GPT output: `outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke/gpt_image2/GBC06-01-png-16.png`
- GPT output image: `884 x 1779`, `RGB`, non-empty

The real-call JSONL row records a safe request summary without API keys:

```json
{
  "record_id": "GBC06_01.png#16",
  "status": "cleaned",
  "cleanup": {
    "method": "local_diffusion_inpaint",
    "bbox": [1349, 121, 1407, 378],
    "input_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\crops\\input\\GBC06-01-png-16.png",
    "text_mask_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\crops\\mask\\GBC06-01-png-16.png",
    "gpt_mask_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\crops\\gpt_mask\\GBC06-01-png-16.png",
    "cleaned_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\crops\\cleaned\\GBC06-01-png-16.png",
    "dark_pixel_count": 7779
  },
  "gpt_image2_edit": {
    "status": "ok",
    "request": {
      "kind": "gpt_image_2_masked_edit",
      "model": "gpt-image-2",
      "base_url_configured": true,
      "prompt_chars": 213,
      "size": "auto",
      "quality": "auto",
      "n": 1
    },
    "response": {
      "usage": {
        "total_tokens": 1690
      }
    }
  }
}
```

## Interpretation

Phase 6 now has a non-bubble cleanup path:

1. Select non-bubble detections where `group_name != "框内"`.
2. Build a local dark-pixel text mask from the detected crop.
3. Save a local repaired crop using a deterministic diffusion-style inpaint prototype.
4. Save a gpt-image-2 compatible RGBA mask where the text area has alpha `0` and preserved regions have alpha `255`.
5. Support dry-run request packaging by default.
6. Support a controlled real `gpt-image-2` edit call with `--call-gpt-image`.

The first real call initially exposed a base URL compatibility issue: the configured `GPT_IMAGE_BASE_URL` ended at `/images`, while the OpenAI SDK appends `/images/edits`. The client now normalizes `/images` or `/images/edits` suffixes before creating the SDK client.

## Limitations

- The local diffusion inpaint is only a baseline. It can reduce obvious dark text but is not equivalent to LaMa, PatchMatch, or Photoshop content-aware fill.
- The gpt-image-2 output size changed from the input crop size `58 x 257` to `884 x 1779`. This means direct crop replacement is not yet safe; a later step must resize/crop/register the generated output before page composition.
- The prompt asks the model to edit the masked text area and preserve surrounding art, but the result still requires manual visual review.
- The current runner uses Phase 2 detection boxes directly; poor text boxes will produce poor masks and poor edits.
- This path is not yet integrated into Phase 7 page preview or Phase 8 Photoshop export selection logic.

## Verification

```powershell
python -m pytest tests/test_phase6_nonbubble_cleanup.py -q
python -m pytest tests/test_phase6_cleanup.py -q
python -m pytest -q
```

Fresh results before this report was written:

```text
5 passed in 1.36s
3 passed in 0.30s
50 passed in 4.00s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records the reproducible commands and aggregate result.
- No API credential or raw `.env` value is stored in the JSONL rows or this report.
