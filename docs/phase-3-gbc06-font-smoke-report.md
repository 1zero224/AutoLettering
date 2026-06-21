# Phase 3 GBC06 Font Smoke Report

## Command

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-dir "工具箱漫画字体V2.5" --run-id phase3-gbc06-font-smoke --sample-limit 5 --font-limit 12
```

## Output

Run directory:

```text
outputs/runs/phase3-gbc06-font-smoke
```

Generated artifacts:

- `font-index.jsonl`
- `font-comparisons.jsonl`
- `crops/source_text/*.png`
- `crops/rendered_text/*/*.png`
- `debug/font_comparison/*.png`
- `reports/phase3-report.md`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Records with comparison grids: 5
- Indexed font records: 68
- Candidate fonts per record: 12
- Font comparison records: 5
- Comparison images: 5

## Interpretation

This phase creates deterministic font-selection inputs, not final font-selection decisions.

The current method:

- scans `.ttf` and `.otf` files from the manga font toolbox
- reads font metadata and character coverage with `fontTools`
- writes the complete font index for the current sample text
- selects a 12-font comparison batch with distinct primary style hints before filling any remaining slots
- crops the detected original text region from Phase 2 output
- renders the translated text with each candidate font
- writes one comparison grid per sampled record
- keeps `selected_font`, `model_reasoning_summary`, and `confidence` as `null`

The next iteration should connect a controlled MIMO vision call that chooses from the visible candidate IDs in each comparison grid. That model-backed phase must save request summaries, response summaries, selected font IDs, confidence, and failure reasons.

## Verification

```powershell
python -m pytest -q
```

Fresh result before this report was finalized:

```text
14 passed in 0.66s
```

## Notes

- This phase does not call MIMO or GPT image APIs.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
