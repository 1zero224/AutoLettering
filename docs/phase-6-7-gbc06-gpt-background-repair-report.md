# Phase 6/7 GPT Background Repair Report

## Scope

This slice tests a safer `gpt-image-2` path for the tall non-bubble red side
banner where direct GPT Chinese replacement failed.

The new path asks GPT to repair only the background and to write no text at all.
Phase 7 then composites the repaired crop and renders Chinese programmatically
using the Phase 4 layout.

- Record: `GBC06_33.png#1`
- Target text: `漫画第一卷\n2026年6月29日发售！！`
- CTA/CTD matched bbox: `[1156, 371, 1298, 1925]`
- Gate run: `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-gate-v1`
- Source LaMA cleanup run: `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1`
- Layout run: `outputs/runs/phase4-gbc06-33-1-cta-full-layout-v2-light-cap`

## Code Changes Under Test

- `autolettering/phase4.py`
  - Infers light text from CTA/CTD source crop pixels for non-bubble tall strips.
  - Caps the base vertical font limit for tall narrow CTA strips to avoid the
    previous oversized `72px` render.
  - Keeps vertical alignment at top for the tested manga-style vertical strip.
- `autolettering/phase6_cleanup_escalation_gpt_background_repair.py`
  - Consumes cleanup quality-gate candidates.
  - Builds a dilated transparent GPT mask from the local text mask.
  - Prompts GPT to remove original glyphs and reconstruct only the red banner
    background.
  - Writes a Phase 7 compatible `cleanup-results.jsonl` row with
    `method="gpt_image2_background_repair"` and `text_overlay_required=true`.
  - Does not write `replacement_crop_path` or `replacement_method`, so Phase 7
    still renders editable/programmatic text.
- `experiments/phase6_cleanup_escalation_gpt_background_repair.py`
  - CLI wrapper with dry-run default and explicit `--call-gpt-image`.
- `tests/test_phase6_cleanup_escalation_gpt_background_repair.py`
  - Covers dry-run contract and fake GPT success contract.

## Commands

Dry-run request/mask check:

```powershell
python experiments/phase6_cleanup_escalation_gpt_background_repair.py --gate-run-dir outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-gate-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-gpt-background-dry-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --mask-dilation-px 6
```

Real GPT background repair:

```powershell
python experiments/phase6_cleanup_escalation_gpt_background_repair.py --gate-run-dir outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-gate-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-gpt-background-real-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --mask-dilation-px 6 --call-gpt-image
```

Phase 7 preview with GPT background repair and programmatic text:

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-cta-full-layout-v2-light-cap --output-root outputs/runs --run-id phase7-gbc06-33-1-gpt-background-full-layout-v1 --sample-limit 1
```

MIMO evaluation for GPT background repair preview:

```powershell
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-33-1-gpt-background-full-layout-v1 --output-root outputs/runs --run-id phase7-gbc06-33-1-gpt-background-full-layout-mimo-v1 --sample-limit 1
```

MIMO baseline evaluation for LaMA preview:

```powershell
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-33-1-lama-full-layout-v1 --output-root outputs/runs --run-id phase7-gbc06-33-1-lama-full-layout-mimo-v1 --sample-limit 1
```

## Artifacts

Main comparison image:

- `outputs/runs/phase7-gbc06-33-1-gpt-background-full-layout-v1/debug/method_comparison_gbc06-33-1.png`

GPT background repair artifacts:

- Grid: `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1/visuals/cleanup-escalation-gpt-background-grid.png`
- Input crop: `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1/background_repair_input/GBC06-33-png-1.png`
- GPT mask: `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1/background_repair_gpt_mask/GBC06-33-png-1.png`
- Normalized repaired crop: `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1/background_repair_gpt_normalized/GBC06-33-png-1.png`
- Before/after crop: `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1/background_repair_before_after/GBC06-33-png-1.png`

Phase 7 preview artifacts:

- GPT preview crop: `outputs/runs/phase7-gbc06-33-1-gpt-background-full-layout-v1/crops/before_after/GBC06-33-png-1.png`
- GPT MIMO sheet: `outputs/runs/phase7-gbc06-33-1-gpt-background-full-layout-v1/debug/evaluation_contact_sheets/GBC06-33-png.png`
- LaMA baseline preview crop: `outputs/runs/phase7-gbc06-33-1-lama-full-layout-v1/crops/before_after/GBC06-33-png-1.png`
- LaMA baseline MIMO sheet: `outputs/runs/phase7-gbc06-33-1-lama-full-layout-v1/debug/evaluation_contact_sheets/GBC06-33-png.png`

## Results

| Method | MIMO run | Score | Usable | Model issues | Manual read |
| --- | --- | ---: | --- | --- | --- |
| `bt_lama_large_inpaint` + programmatic text | `outputs/runs/phase7-gbc06-33-1-lama-full-layout-mimo-v1` | 8 | true | Visible dark blurry artifacts in segments 5 and 6. | Rejected for this sample: dark residual blocks and glyph-shaped shadows remain obvious. |
| `gpt_image2_background_repair` + programmatic text | `outputs/runs/phase7-gbc06-33-1-gpt-background-full-layout-mimo-v1` | 10 | true | None. | Best cleanup result so far for this strip: original text residue is removed and red banner texture/border are preserved. Text rendering is usable for preview but still needs later font/digit refinement. |

The real GPT repair response wrote:

- `status=ok`
- normalized target size: `[142, 1554]`
- source GPT output size: `[741, 2123]`
- total image call usage recorded in
  `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1/cleanup-escalation-gpt-background-results.jsonl`

## Findings

1. Direct GPT Chinese replacement remains rejected for `GBC06_33.png#1`, but
   GPT background-only repair is useful on this exact red strip.
2. The Phase 7 cleanup contract works as intended: because the background repair
   row does not set `replacement_crop_path`, Phase 7 pastes the cleaned
   background and then renders the Chinese overlay.
3. The Phase 4 fix materially improves this sample: the layout now uses white
   text, top alignment, and `font_size=54` instead of the previous black,
   oversized `72px` render.
4. MIMO correctly prefers the GPT background repair path over the LaMA baseline
   for this sample, but the manual gate is still required. It does not flag the
   remaining font/style issues, especially the stiff font and vertical digit
   rendering.

## Decision

Promote `gpt_image2_background_repair` as the current best experimental path
for this tall non-bubble CTA/CTD red banner:

1. CTA/CTD finds the full text component.
2. `lama_large_512px` can remain as a local baseline and gate trigger.
3. When LaMA leaves strong glyph residue, run GPT background-only repair.
4. Always render Chinese programmatically or via editable Photoshop text layers;
   do not accept GPT direct text replacement for this sample.

## Remaining Work

- Improve font selection for the red banner; the current Chinese font is
  readable but too rigid compared with the original.
- Add vertical number handling options for dates (`2026`, `6`, `29`) so the
  result can better match manga banner typography.
- Feed this background-only cleanup route into the future Photoshop export so
  the PSD can contain:
  - editable text layers,
  - repaired image layer,
  - original image layer.

## Verification

Targeted tests:

```powershell
python -m pytest tests/test_phase4_layout.py::test_run_phase4_infers_light_text_for_tall_cta_mask_source tests/test_phase6_cleanup_escalation_gpt_background_repair.py tests/test_experiment_clis.py -q
```

Result: `19 passed in 3.38s`.

Broader targeted suite:

```powershell
python -m pytest tests/test_phase4_layout.py tests/test_phase6_cleanup_escalation_gpt_background_repair.py tests/test_experiment_clis.py -q
```

Result: `57 passed in 7.88s`.

Full suite:

```powershell
python -m pytest -q
```

Result: `317 passed in 39.93s`.

Whitespace check:

```powershell
git diff --check
```

Result: no output.
