# Phase 7/8 GBC06_29 Large Non-Bubble Title Report

## Purpose

This report records the first complete Phase 1-8 pass for `GBC06_29.png#2`, a
large non-bubble vertical title translated as `囚禁中挣脱而出！`. It is the
current reference sample for the CTA matched path:

1. detect text with BallonsTranslator CTA/CTD masks;
2. match the closed mask component to the LabelPlus point by mask-edge distance;
3. repair the matched mask region with `lama_large_512px`;
4. render editable vertical Chinese lettering programmatically;
5. export a Photoshop manifest/JSX with text layers above the repaired image and
   the original image.

The intermediate failed experiments are intentionally preserved because this
record exposed both cleanup-method and font-size limits.

## CTA Detection

Command:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-29-2-cta-mask-v1 --sample-limit 1 --record-id "GBC06_29.png#2"
```

Result:

- Run: `outputs/runs/phase2-gbc06-29-2-cta-mask-v1`
- Status: `ok`
- Detection method: `cta_mask`
- Matched component id:
  `component-0004+component-0005+component-0006+component-0007+component-0008+component-0009`
- Mask-edge distance: `7.211px`
- Selected bbox / full bbox / body bbox: `[86, 815, 354, 1985]`
- Debug image:
  `outputs/runs/phase2-gbc06-29-2-cta-mask-v1/debug/detection/GBC06_29-2.png`

This fixes the earlier diverse-detection failure where `GBC06_29.png#2` only
received a partial large-title crop.

## Font And Angle

Font comparison:

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-29-2-cta-mask-v1 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-29-2-font-grid-v1 --sample-limit 1 --font-limit 12 --record-id "GBC06_29.png#2"
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-29-2-font-grid-v1 --output-root outputs/runs --run-id phase3-gbc06-29-2-mimo-font-selection-v1 --sample-limit 1 --record-id "GBC06_29.png#2"
```

Result:

- MIMO selected
  `工具箱漫画字体V2.5/[toolbox]与墨体-简体-Bold(v2.4).ttf`
- `selected_font_id`: `font-73f8e41116cb`
- Confidence: `0.85`
- Comparison image:
  `outputs/runs/phase3-gbc06-29-2-font-grid-v1/debug/font_comparison/GBC06-29-png-2.png`

Angle:

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-29-2-cta-mask-v1 --output-root outputs/runs --run-id phase5-gbc06-29-2-angle-v1 --sample-limit 1 --record-id "GBC06_29.png#2"
```

Result:

- Orientation: `vertical`
- Estimated/selected angle: `1.5`
- Confidence: `0.959`
- Final layout applies `0.0` degrees because the project ignores micro-rotations
  below the `3.0` degree threshold for obvious vertical manga text.
- Candidate grid:
  `outputs/runs/phase5-gbc06-29-2-angle-v1/debug/angle_candidates/GBC06-29-png-2.png`

## Cleanup Method Comparison

Matched CTA records still default to `lama_large_512px`. The experimental
override exists only to compare other inpainting methods on the same matched
mask.

LaMa command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-29-2-cta-mask-v1 --output-root outputs/runs --run-id phase6-gbc06-29-2-cta-lama-v1 --sample-limit 1 --record-id "GBC06_29.png#2" --skip-mimo
```

PatchMatch command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-29-2-cta-mask-v1 --output-root outputs/runs --run-id phase6-gbc06-29-2-cta-patchmatch-v1 --sample-limit 1 --record-id "GBC06_29.png#2" --skip-mimo --inpaint-method bt_patchmatch --allow-cta-method-override
```

GPT direct replacement command:

```powershell
python experiments/phase6_nonbubble_gpt_replace.py --detection-run-dir outputs/runs/phase2-gbc06-29-2-cta-mask-v1 --output-root outputs/runs --run-id phase6-gbc06-29-2-gpt-replace-v1 --sample-limit 1 --record-id "GBC06_29.png#2" --bt-method lama_large_512px --bt-method patchmatch --context-padding 24 --rect-mask-expand-px 2 --call-gpt-image
```

Results:

| Method | Evidence | MIMO result |
| --- | --- | --- |
| `lama_large_512px` | `outputs/runs/phase6-gbc06-29-2-cta-lama-v1/crops/before_after/GBC06-29-png-2.png` | Best local repair for this sample. |
| `bt_patchmatch` | `outputs/runs/phase7-8-gbc06-29-2-cta-patchmatch-v1/runs/phase7-evaluation/preview-evaluation.jsonl` | Score `4`, usable but misplaced/dirty; worse than LaMa on this page. |
| `gpt-image-2` direct replacement | `outputs/runs/phase6-gbc06-29-2-gpt-replace-v1/visuals/gpt-replace-bt-grid.png` | API call succeeded, but quality failed: exact Chinese text `0`, no-Japanese `0`, typography/layout `0`, preservation outside mask `10`. |

Important reporting distinction: `gpt_ok_count=1` in
`outputs/runs/phase6-gbc06-29-2-gpt-replace-v1/manifest.json` means the image
API call succeeded. It does not mean the replacement quality succeeded. The
MIMO quality file
`outputs/runs/phase6-gbc06-29-2-gpt-replace-v1/reports/mimo-gpt-replace-evaluation.json`
marks `gpt-image-2 cn` and `patchmatch` unacceptable for this sample, and ranks
`lama_large_512px` above `patchmatch`.

## Font-Size Iteration

The first layout kept the old vertical upper bound and under-sized the large
title:

```text
phase4-gbc06-29-2-layout-v1: font_size=72, MIMO Phase 7 score=8
```

The first large-title fix used `0.48 * bbox_width`, which produced a better
title scale but overshot:

```text
phase4-gbc06-29-2-layout-v2-large-title: font_size=129, MIMO Phase 7 score=8
issue: excessive lettering size and background-art coverage
```

The retained fix uses a conservative large non-bubble CTA title cap
`0.38 * bbox_width`, bounded to `72..132`:

```text
phase4-gbc06-29-2-layout-v3-large-title-conservative:
font_size=102
orientation=vertical
vertical_align=top
angle_degrees=0.0
target_bbox=[86, 815, 354, 1985]
measured_size=102x773
overflow_ratio=0.0
```

Final Phase 7/8 command:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-29-2-cta-mask-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-29-2-cta-lama-v1 --layout-run-dir outputs/runs/phase4-gbc06-29-2-layout-v3-large-title-conservative --font-selection-run-dir outputs/runs/phase3-gbc06-29-2-mimo-font-selection-v1 --output-root outputs/runs --run-id phase7-8-gbc06-29-2-cta-lama-large-title-v3 --sample-limit 1
```

MIMO result:

- Run: `outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase7-evaluation`
- Score: `9`
- Usable: `true`
- Original text removed: `true`
- Art preserved: `true`
- Lettering readable: `true`
- Issues: `[]`
- Contact sheet:
  `outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-29-png.png`

## Photoshop Export

Audit command:

```powershell
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase8-export --output-root outputs/runs --run-id phase8-gbc06-29-2-cta-lama-large-title-audit-v3
```

Result:

- Audit passed: `true`
- Record count: `1`
- Vertical top layer count: `1`
- Missing vertical top anchors: `0`
- JSX anchor logic present: `true`
- Manifest:
  `outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase8-export/photoshop-manifest.json`
- JSX:
  `outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase8-export/photoshop-import.jsx`

The manifest keeps the required layer order contract:

```json
["text_layers", "repaired_image", "original_image"]
```

The repaired page bitmap is the full cleaned image:

```text
outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase7-preview/pages/cleaned/GBC06-29-png.png
```

## Coverage Promotion

The v19 coverage run adds this record to the Phase 1-8 complete set:

```text
outputs/runs/phase0-8-gbc06-pipeline-coverage-v19-gbc06-29-complete
base_record_count=35
complete_record_count=34
incomplete_record_count=1
```

The only remaining diverse base record missing Phase 3+ coverage is now:

```text
GBC06_33.png#1  框外  漫画第一卷 / 2026年6月29日发售！！
```

## Decision

Use the CTA matched `lama_large_512px` path plus conservative large-title layout
for `GBC06_29.png#2`. Keep `gpt-image-2` direct replacement as experimental
evidence only for this sample, because the real call did not preserve the exact
Chinese target text.

## Verification

Fresh targeted verification:

```powershell
python -m pytest tests/test_phase4_layout.py tests/test_phase6_nonbubble_cleanup.py tests/test_experiment_clis.py tests/test_phase7_preview.py tests/test_phase8_export_quality_audit.py -q
```

Observed result:

```text
100 passed in 6.33s
```

Full regression:

```powershell
python -m pytest -q
```

Observed result:

```text
254 passed in 21.07s
```
