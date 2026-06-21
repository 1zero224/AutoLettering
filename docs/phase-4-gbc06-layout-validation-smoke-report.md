# Phase 4 GBC06 Layout Validation Smoke Report

## Command

```powershell
python experiments/phase4_layout_validate.py --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase4-gbc06-layout-validation-smoke --sample-limit 1
```

The command has been run with the original JSON-only validation prompt, a shorter JSON prompt, the current low-burden text verdict prompt, and MIMO deep-thinking disabled for this one-line visual verdict. The current run reached the MIMO API successfully and returned a structured text verdict.

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
- Needs revision: 1
- Failed: 0
- Record: `GBC06_01.png#1`
- Layout preview: `outputs/runs/phase4-gbc06-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`
- Validation status: `needs_revision`
- Selection source: `mimo_vision`
- Accepted: `false`
- Needs revision: `true`
- Failure reason: `null`
- Model failure reason: `null`
- Raw model text: `REVISE, text is vertically centered but lacks horizontal centering within the target width.`
- Recommended change: `text is vertically centered but lacks horizontal centering within the target width.`
- Request prompt characters: 205
- Request thinking type: `disabled`
- Request image count: 1
- Max completion tokens: 96
- Last observed token usage: 242 total tokens
- Last observed completion tokens: 18
- Last observed reasoning tokens: 0

## Interpretation

This phase now has a real model-backed validation path plus a deterministic fallback for model formatting failures. The response parser accepts both structured JSON and short text verdicts such as `ACCEPT: ...`, `ACCEPT, ...`, and `REVISE: ...`.

The latest API request completed, returned usage metadata, and produced non-empty model text. Disabling thinking changed the observed response from an empty body with `95` reasoning tokens to a usable `REVISE` verdict with `0` reasoning tokens.

The current result is a model-backed revision request, not a deterministic fallback. The model says the rendered text is vertically centered but lacks horizontal centering within the target width. This gives the next layout iteration a concrete visual issue to optimize instead of only relying on measured overflow.

## Adjustment Already Tried

The validation prompt and per-call completion budget have been reduced across iterations:

- prompt length reduced from 419 characters to 241 characters
- prompt length reduced again from 241 characters to 205 characters
- `max_completion_tokens` reduced from 512 to 96
- observed token usage reduced from 778 to 324 total tokens
- latest observed token usage is 242 total tokens

The parser now supports direct text verdicts, so responses like `ACCEPT, text fits target` and `REVISE, ...` can be mapped into `mimo_vision` results without requiring JSON. Adding `thinking: {"type": "disabled"}` to the request made the latest persisted smoke return actual verdict text instead of spending almost all completion tokens on reasoning.

## Next Adjustment

The next iteration should feed the MIMO revision reason back into layout search:

- add candidate scoring or placement refinement for horizontal centering within the detected bbox
- optionally run validation on multiple layout candidates and select the first model-accepted candidate
- keep recording every failed model response as an experiment artifact
- use fallback verdicts only as deterministic acceptance, not as visual/model approval

## Verification

```powershell
python -m pytest tests/test_phase4_layout_validation.py -q
python -m pytest -q
```

Fresh result before this report was written:

```text
9 passed in 0.25s
67 passed in 3.63s
```

## Notes

- `.env` values were loaded locally but not printed.
- Request logs store URL, model, prompt length, image path, token usage, and response metadata.
- Request logs do not store `api-key`, bearer headers, raw environment values, or API keys.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
