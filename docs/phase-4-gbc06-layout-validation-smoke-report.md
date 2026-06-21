# Phase 4 GBC06 Layout Validation Smoke Report

## Command

```powershell
python experiments/phase4_layout_validate.py --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase4-gbc06-layout-validation-smoke --sample-limit 1
```

The command was run twice. Both runs reached the MIMO API successfully but returned an empty model text field, so the structured validator recorded `invalid_json`.

## Output

Run directory:

```text
outputs/runs/phase4-gbc06-layout-validation-smoke
```

Generated artifacts:

- `layout-validation.jsonl`
- `reports/api-calls.jsonl`
- `reports/phase4-validation-report.md`

## Result Summary

- Layout source: `outputs/runs/phase4-gbc06-layout-smoke/layout-results.jsonl`
- Records submitted: 1
- Accepted: 0
- Needs revision: 0
- Failed: 1
- Record: `GBC06_01.png#1`
- Layout preview: `outputs/runs/phase4-gbc06-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`
- Failure reason: `invalid_json`
- Raw model text: empty string
- Request prompt characters: 419
- Request image count: 1
- Last observed token usage: 778 total tokens

## Interpretation

This phase now has a real model-backed validation path, but the first smoke result did not produce a usable validation decision.

The API request completed and returned usage metadata, so this was not a connectivity or authentication failure. The model response content was empty in both observed runs, which caused the JSON parser to classify the validation as `invalid_json`.

This is a valid experiment result, not a pass. The current validator correctly preserves the failed result in `layout-validation.jsonl` instead of inventing a mock validation.

## Next Adjustment

The next iteration should make the MIMO validation call easier to satisfy:

- use a lower `max_completion_tokens` to reduce reasoning-token exhaustion risk
- shorten the prompt
- ask for a minimal JSON object only
- consider adding a deterministic fallback verdict when deterministic overflow checks pass but model output is empty
- keep recording every failed model response as an experiment artifact

## Verification

```powershell
python -m pytest -q
```

Fresh result before this report was written:

```text
30 passed in 1.15s
```

## Notes

- `.env` values were loaded locally but not printed.
- Request logs store URL, model, prompt length, image path, token usage, and response metadata.
- Request logs do not store `api-key`, bearer headers, raw environment values, or API keys.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
