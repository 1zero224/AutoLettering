# Phase 6 Cleanup Escalation GPT Replacement Report

## Scope

This slice consumes failed Phase 6 cleanup quality-gate candidates and tests whether `gpt-image-2` masked editing can directly replace a non-bubble CTA/CTD matched text region with Chinese text.

The tested record is the red vertical side banner:

- Record: `GBC06_33.png#1`
- Target text: `漫画第一卷\n2026年6月29日发售！！`
- CTA/CTD matched bbox: `[1156, 371, 1298, 1925]`
- Gate run: `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-gate-v1`
- Source cleanup run: `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1`
- Source cleanup issue: MIMO cleanup score `6`, `usable=true`, but `original_text_removed=false`; dark Japanese glyph residue remains.

## Code Changes Under Test

- `autolettering/phase6_cleanup_escalation_gpt_replace.py`
  - Reads `cleanup-escalation-candidates.jsonl`.
  - Resolves the source cleanup run from the gate manifest.
  - Builds context crops, transparent GPT masks, segment crops, mask overlays, composed outputs, and a near-square visual grid.
  - Writes both `cleanup-escalation-gpt-results.jsonl` and a compatible `cleanup-results.jsonl` so `phase6_replacement_quality.py` can evaluate the GPT output.
  - Supports segmented replacement and `--single-segment`.
- `experiments/phase6_cleanup_escalation_gpt_replace.py`
  - CLI wrapper with safe dry-run default and explicit `--call-gpt-image`.
  - Defaults to tight context: `--context-padding 16`, `--rect-mask-expand-px 2`.
- `autolettering/phase6_replacement_quality_io.py`
  - Hardens the MIMO prompt to transcribe `observed_text` before scoring.
  - Requires `exact_text_correct=false` when the observed text omits, adds, or changes any character or digit.
- `autolettering/phase6_replacement_quality.py`
  - Persists parsed `observed_text` in `replacement-quality.jsonl`.
- Segment bbox construction now prioritizes covering the full target height for the available text segments. This avoids the earlier high-bbox case where extra `max_segment_height` slices could be created and then truncated, leaving the tail of a tall banner unedited.

## Commands

Dry-run fixed single-segment prompt check:

```powershell
python experiments/phase6_cleanup_escalation_gpt_replace.py --gate-run-dir outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-gate-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-cleanup-escalation-gpt-dry-v7-single-fixed --sample-limit 1 --record-id "GBC06_33.png#1" --context-padding 16 --rect-mask-expand-px 2 --max-segment-chars 64 --max-segment-height 2400 --single-segment
```

Real fixed single-segment GPT call:

```powershell
python experiments/phase6_cleanup_escalation_gpt_replace.py --gate-run-dir outputs/runs/phase6-gbc06-33-1-cta-contract-lama-quality-gate-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-cleanup-escalation-gpt-real-v5-single-fixed --sample-limit 1 --record-id "GBC06_33.png#1" --context-padding 16 --rect-mask-expand-px 2 --max-segment-chars 64 --max-segment-height 2400 --single-segment --call-gpt-image
```

MIMO replacement quality for fixed single-segment GPT:

```powershell
python experiments/phase6_replacement_quality.py --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-real-v5-single-fixed --output-root outputs/runs --run-id phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v5-single-fixed --sample-limit 1 --record-id "GBC06_33.png#1"
```

MIMO re-evaluation of earlier runs with the stricter `observed_text` prompt:

```powershell
python experiments/phase6_replacement_quality.py --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-real-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v1-observedtext --sample-limit 1 --record-id "GBC06_33.png#1"

python experiments/phase6_replacement_quality.py --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-real-v2-seg5 --output-root outputs/runs --run-id phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v2-seg5-observedtext --sample-limit 1 --record-id "GBC06_33.png#1"
```

## Experiment Results

| Run | Segments | MIMO run | MIMO score / usable | Manual result | Evidence |
| --- | ---: | --- | --- | --- | --- |
| `phase6-gbc06-33-1-cleanup-escalation-gpt-real-v1` | 3 | `phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v1` | `9`, `true` | Fail. Date line is malformed; `2026年` is not rendered correctly. | `outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v1/debug/replacement_quality_sheets/GBC06-33-png-1.png` |
| `phase6-gbc06-33-1-cleanup-escalation-gpt-real-v1` | 3 | `phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v1-observedtext` | `3`, `false` | Fail, now caught by stricter MIMO. | `outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v1-observedtext/debug/replacement_quality_sheets/GBC06-33-png-1.png` |
| `phase6-gbc06-33-1-cleanup-escalation-gpt-real-v2-seg5` | 4 | `phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v2-seg5` | `10`, `true` | Fail. Middle date region is overlapped and dark-blocked. | `outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v2-seg5/debug/replacement_quality_sheets/GBC06-33-png-1.png` |
| `phase6-gbc06-33-1-cleanup-escalation-gpt-real-v2-seg5` | 4 | `phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v2-seg5-observedtext` | `10`, `true` | Fail. This is a MIMO false positive even after the stricter prompt. | `outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v2-seg5-observedtext/debug/replacement_quality_sheets/GBC06-33-png-1.png` |
| `phase6-gbc06-33-1-cleanup-escalation-gpt-real-v3-line` | 2 | `phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v3-line` | `3`, `false` | Fail. Text is warped, style mismatched, and original/incorrect text remains. | `outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v3-line/debug/replacement_quality_sheets/GBC06-33-png-1.png` |
| `phase6-gbc06-33-1-cleanup-escalation-gpt-real-v4-single` | 1 | `phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v4-single` | `0`, `false` | Fail. This run exposed a prompt construction bug for multi-line target text. | `outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v4-single/debug/replacement_quality_sheets/GBC06-33-png-1.png` |
| `phase6-gbc06-33-1-cleanup-escalation-gpt-real-v5-single-fixed` | 1 | `phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v5-single-fixed` | `0`, `false` | Fail. Prompt is fixed, but GPT still produces oversized, garbled partial glyphs. | `outputs/runs/phase6-gbc06-33-1-cleanup-escalation-gpt-quality-v5-single-fixed/debug/replacement_quality_sheets/GBC06-33-png-1.png` |

## Key Findings

1. The consumer contract works: the gate candidate can be converted into GPT masked-edit requests and into a `cleanup-results.jsonl` row that the existing MIMO replacement quality step can read.
2. The original `--single-segment` path had a real bug: multi-line target text caused escalation instructions to be inserted between the first and second target lines. The fixed dry-run `phase6-gbc06-33-1-cleanup-escalation-gpt-dry-v7-single-fixed` writes request `target_text='漫画第一卷\n2026年6月29日发售！！'` with `contains_escalation=false`.
3. The fixed single-segment real run still fails, so the bad result was not only caused by the prompt bug. On this tall red banner, `gpt-image-2` scales and warps glyphs instead of reproducing the original compact vertical lettering.
4. MIMO is useful but insufficient as the only quality gate for this class of text. The stricter prompt corrected v1 from `9 usable=true` to `3 usable=false`, but v2 still received `10 usable=true` despite visible overlap/dark-block artifacts.
5. A high-bbox segmentation bug was fixed during this slice: `_bbox_segments()` now covers the full target bbox with the actual text segment count instead of creating more slices than text segments and truncating the tail.
6. For this sample, the current best decision is not to accept GPT direct replacement output. The safer route remains: use CTA/CTD to locate the whole source region, use a local/generative method only to repair the background, then render Chinese programmatically or export editable Photoshop text layers.

## Current Decision

Keep the cleanup-escalation GPT consumer in the codebase because it is useful for controlled experiments and for future samples where direct GPT replacement might work. Do not promote `gpt-image-2` direct replacement as an accepted result for `GBC06_33.png#1`.

For this red vertical banner, the next experiment should shift away from direct text generation and test one of these options:

1. full-strip background regeneration without Chinese text, followed by programmatic vertical rendering;
2. a narrower per-character or per-cluster cleanup-only mask, followed by programmatic rendering;
3. a Photoshop export path using the repaired page as the image layer and editable text layers for manual correction.

## Verification

Targeted verification after the prompt fix and `observed_text` output change:

```powershell
python -m pytest tests/test_phase6_cleanup_escalation_gpt_replace.py tests/test_phase6_replacement_quality.py tests/test_experiment_clis.py::test_phase6_cleanup_escalation_gpt_cli_defaults_to_tight_segment_contract -q
```

Result: `13 passed in 3.73s`.
