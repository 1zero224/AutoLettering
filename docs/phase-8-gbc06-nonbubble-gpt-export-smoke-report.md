# Phase 8 GBC06 Non-Bubble GPT Photoshop Export Smoke Report

## Command

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke --run-id phase8-gbc06-nonbubble-gpt-export-smoke --sample-limit 2
```

## Output

Run directory:

```text
outputs/runs/phase8-gbc06-nonbubble-gpt-export-smoke
```

Generated artifacts:

- `photoshop-manifest.json`
- `photoshop-import.jsx`
- `reports/phase8-report.md`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Font selection source: `outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke/font-selections.jsonl`
- Layout source: `outputs/runs/phase4-gbc06-nonbubble-layout-smoke/layout-results.jsonl`
- Cleanup source: `outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke/cleanup-results.jsonl`
- Schema: `autolettering.photoshop.v1`
- Pages exported: 1
- Text layers exported: 2
- Manifest size: `5333` bytes
- JSX size: `3437` bytes
- Missing cleanup layers: 1
- Effective cleanup methods: `gpt_image2_masked_edit=1`

The run includes two layout/font records because the non-bubble font/layout smoke run contains both `GBC06_01.png#1` and `GBC06_01.png#16`.
Only `GBC06_01.png#16` has a matching non-bubble cleanup row in this cleanup run; `GBC06_01.png#1` is exported with `cleanup.status = "missing"`.

## Replacement Cleanup Metadata

Phase 8 now preserves both the local cleanup artifact and the GPT replacement artifact in the manifest.
For the non-bubble record, `effective_*` points at the GPT replacement crop because it is the user-visible replacement selected by Phase 6/7.

```json
{
  "record_id": "GBC06_01.png#16",
  "text": "来自桃香的唐突的提案",
  "bbox": [1349, 121, 1407, 378],
  "font": "[toolbox]YuMo-GB-Bold",
  "layout": {
    "font_size": 22,
    "orientation": "vertical",
    "angle_degrees": 0.2
  },
  "cleanup": {
    "status": "cleaned",
    "method": "local_diffusion_inpaint",
    "cleaned_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\crops\\cleaned\\GBC06-01-png-16.png",
    "replacement_method": "gpt_image2_masked_edit",
    "replacement_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\gpt_image2_normalized\\GBC06-01-png-16.png",
    "effective_method": "gpt_image2_masked_edit",
    "effective_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\gpt_image2_normalized\\GBC06-01-png-16.png"
  }
}
```

## Behavior Change

- `cleanup.method` and `cleanup.cleaned_crop_path` still describe the local cleanup baseline.
- `cleanup.replacement_method` and `cleanup.replacement_crop_path` describe the optional GPT replacement crop.
- `cleanup.effective_method` and `cleanup.effective_crop_path` select the artifact that downstream tools should prefer for preview/export metadata.
- Missing cleanup rows now still emit a stable cleanup object with all cleanup path/method fields set to `null`.
- `photoshop-import.jsx` attempts to place `cleanup.effective_crop_path` as a bitmap patch layer named `AL cleanup <record_id>` before adding editable text.

## Limitations

- The generated JSX now attempts to place cleanup bitmap patches from `cleanup.effective_crop_path` before creating editable text layers. Photoshop execution is still unverified in this environment.
- This run uses a non-bubble cleanup directory only, so the first bubble record has missing cleanup metadata. Mixed bubble/non-bubble export is now covered by `docs/phase-7-8-gbc06-mixed-cleanup-smoke-report.md`, using repeated `--cleanup-run-dir` inputs.
- Photoshop is not available in this environment, so the JSX was not executed inside Photoshop.

## Verification

```powershell
python -m pytest tests/test_phase8_photoshop_export.py -q
python -m pytest -q
```

Fresh result before this report was written:

```text
3 passed in 0.21s
54 passed in 3.79s
```
