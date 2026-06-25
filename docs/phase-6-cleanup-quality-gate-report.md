# Phase 6 Cleanup Quality Gate Report

## Scope

This slice adds a small quality gate after Phase 6 cleanup evaluation. It does not replace the requested CTA matched path:

- CTA/CTD matched records still default to `lama_large_512px` cleanup plus editable lettering.
- MIMO cleanup quality remains the source of the quality verdict.
- Only failed CTA/LaMA cleanup rows become escalation candidates.
- The gate writes a structured candidate for a future `gpt-image-2` transparent-mask replacement experiment, instead of silently accepting a poor local repair.

## Added Artifacts

- `autolettering/phase6_cleanup_gate.py`
  - Reads `cleanup-results.jsonl` and `cleanup-quality.jsonl`.
  - Writes `cleanup-escalation-candidates.jsonl`, `manifest.json`, and `reports/phase6-cleanup-gate-report.md`.
- `experiments/phase6_cleanup_gate.py`
  - CLI wrapper for the gate.
- `tests/test_phase6_cleanup_gate.py`
  - Covers failed CTA/LaMA escalation, usable LaMA skip, non-CTA skip, and the guard that a generic `source_mask_path` alone is not CTA/CTD provenance.

## Real Experiment: Existing GBC06_33 Quality Row

Command:

```powershell
python experiments/phase6_cleanup_gate.py --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-cta-lama-large-v1 --cleanup-quality-run-dir outputs/runs/phase6-gbc06-33-1-cta-lama-cleanup-quality-v2 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-lama-quality-gate-v1 --record-id "GBC06_33.png#1"
```

Result:

- Run: `outputs/runs/phase6-gbc06-33-1-cta-lama-quality-gate-v1`
- Candidate count: `1`
- Record: `GBC06_33.png#1`
- Recommended route: `quality_gate_gpt_image2_masked_edit`
- Reasons:
  - `phase6_cleanup_unusable`
  - `phase6_cleanup_original_text_visible`
  - `phase6_cleanup_low_score`
- MIMO cleanup quality:
  - score: `2`
  - usable: `false`
  - original_text_removed: `false`
  - art_preserved: `true`
- Target text: `漫画第一卷\n2026年6月29日发售！！`

The candidate keeps the source CTD component mask and the MIMO evaluation sheet path, so a later GPT replacement experiment has enough traceable input context.

## Real Experiment: Current CTA Contract Run

Commands:

```powershell
python experiments/phase6_cleanup_quality.py --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-contract-lama-quality-v1 --sample-limit 1 --record-id "GBC06_33.png#1"

python experiments/phase6_cleanup_gate.py --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1 --cleanup-quality-run-dir outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-contract-lama-quality-gate-v1 --record-id "GBC06_33.png#1"
```

Result:

- Cleanup run: `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1`
- MIMO quality run: `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-v1`
- Gate run: `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-gate-v1`
- Candidate count: `1`
- Record: `GBC06_33.png#1`
- Recommended route: `quality_gate_gpt_image2_masked_edit`
- Reasons:
  - `phase6_cleanup_original_text_visible`
  - `phase6_cleanup_low_score`
- MIMO cleanup quality:
  - score: `6`
  - usable: `true`
  - original_text_removed: `false`
  - art_preserved: `true`
  - issue: dark glyph-shaped ghosting remains in all cleaned segments.
- Candidate target text: `漫画第一卷\n2026年6月29日发售！！`
- Source mask: `outputs/runs/phase2-gbc06-33-1-cta-contract-v1/debug/ctd_masks/GBC06_33/components/component-0001+component-0002+component-0003+component-0004+component-0005+component-0006+component-0007+component-0008+component-0009+component-0011+component-0014+component-0015+component-0021+component-0025+component-0031+component-0032.png`
- Evaluation sheet: `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-v1/debug/cleanup_quality_sheets/GBC06-33-png-1.png`

This experiment is intentionally stricter than a plain usable/not-usable flag. A cleanup can preserve art and still be unacceptable for lettering if the original Japanese glyphs remain visible. The gate therefore escalates this sample because `original_text_removed=false` and the score is below the default threshold `7`.

## Current Decision

Use this gate as the bridge between local BallonsTranslator-style repair and GPT replacement:

1. Run CTA/CTD detection.
2. Run `lama_large_512px` cleanup for matched records.
3. Run MIMO cleanup quality.
4. If CTA/LaMA cleanup is not usable, original text remains visible, art is damaged, or the quality score is below threshold, write a GPT escalation candidate.
5. A later controlled GPT experiment should consume `cleanup-escalation-candidates.jsonl` and still run MIMO replacement quality before Phase 7/8 accepts the output.
