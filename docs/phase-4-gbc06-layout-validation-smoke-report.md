# Phase 4 GBC06 Layout Validation Smoke Report

## Command

```powershell
python experiments/phase4_layout_validate.py --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase4-gbc06-layout-validation-smoke --sample-limit 1
```

The command has been run with the original JSON-only validation prompt, a shorter JSON prompt, and the current low-burden text verdict prompt. The current run reached the MIMO API successfully but returned an empty model text field. Because the deterministic layout measurement has `overflow_ratio = 0.0`, the validator records an accepted deterministic fallback while preserving the model failure reason as `invalid_json`.

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
- Accepted: 1
- Needs revision: 0
- Failed: 0
- Record: `GBC06_01.png#1`
- Layout preview: `outputs/runs/phase4-gbc06-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`
- Validation status: `accepted`
- Selection source: `deterministic_fallback`
- Failure reason: `null`
- Model failure reason: `invalid_json`
- Raw model text: empty string
- Request prompt characters: 205
- Request image count: 1
- Max completion tokens: 96
- Last observed token usage: 318 total tokens
- Last observed completion tokens: 96
- Last observed reasoning tokens: 95

## Interpretation

This phase now has a real model-backed validation path plus a deterministic fallback for model formatting failures. The response parser accepts both structured JSON and short text verdicts such as `ACCEPT: ...`, `ACCEPT, ...`, and `REVISE: ...`.

The API request completed and returned usage metadata, so this was not a connectivity or authentication failure. The latest persisted smoke response content is empty, which caused the parser to classify the validation as `invalid_json`.

The accepted result in this smoke is not a model approval. It means deterministic measurement accepted the layout because `overflow_ratio = 0.0`; `layout-validation.jsonl` still records `model_failure_reason = "invalid_json"` and `raw_model_text = ""`.

## Adjustment Already Tried

The validation prompt and per-call completion budget have been reduced across iterations:

- prompt length reduced from 419 characters to 241 characters
- prompt length reduced again from 241 characters to 205 characters
- `max_completion_tokens` reduced from 512 to 96
- observed token usage reduced from 778 to 324 total tokens
- latest observed token usage is 318 total tokens

The parser now supports direct text verdicts, so a response like `ACCEPT, text fits target` can be mapped into a `mimo_vision` accepted result without requiring JSON. The latest persisted smoke still used almost all completion tokens as reasoning tokens and returned an empty response body.

## Next Adjustment

The next iteration should focus on MIMO response controls rather than parser shape:

- test whether the MIMO API supports disabling or limiting reasoning tokens
- if response controls are unavailable, test an even smaller image or metadata-only validation path
- try `MIMO_TEXT_MODEL` for validation of rendered-preview metadata if visual inspection keeps returning empty text
- keep recording every failed model response as an experiment artifact
- use fallback verdicts only as deterministic acceptance, not as visual/model approval

## Verification

```powershell
python -m pytest tests/test_phase4_layout_validation.py -q
python -m pytest -q
```

Fresh result before this report was written:

```text
8 passed in 0.19s
65 passed in 3.48s
```

## Notes

- `.env` values were loaded locally but not printed.
- Request logs store URL, model, prompt length, image path, token usage, and response metadata.
- Request logs do not store `api-key`, bearer headers, raw environment values, or API keys.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
