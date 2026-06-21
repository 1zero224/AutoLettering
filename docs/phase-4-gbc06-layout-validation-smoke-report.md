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
- Accepted: 1
- Needs revision: 0
- Failed: 0
- Record: `GBC06_01.png#1`
- Layout preview: `outputs/runs/phase4-gbc06-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`
- Layout alpha ink center offset after correction: `-0.5px` horizontal, `-0.5px` vertical
- Validation status: `accepted`
- Selection source: `mimo_vision`
- Accepted: `true`
- Needs revision: `false`
- Failure reason: `null`
- Model failure reason: `null`
- Raw model text: `ACCEPT: Text is centered and fits the target bounding box without overflow.`
- Reasoning summary: `Text is centered and fits the target bounding box without overflow.`
- Recommended changes: none
- Request prompt characters: 205
- Request thinking type: `disabled`
- Request image count: 1
- Max completion tokens: 96
- Last observed token usage: 239 total tokens
- Last observed completion tokens: 15
- Last observed reasoning tokens: 0

## Interpretation

This phase now has a real model-backed validation path plus a deterministic fallback for model formatting failures. The response parser accepts both structured JSON and short text verdicts such as `ACCEPT: ...`, `ACCEPT, ...`, and `REVISE: ...`.

The latest API request completed, returned usage metadata, and produced non-empty model text. Disabling thinking changed the observed response from an empty body with `95` reasoning tokens to usable verdict text with `0` reasoning tokens.

The previous persisted model-backed verdict was `REVISE, text is vertically centered but lacks horizontal centering within the target width.` The current layout run now records alpha-channel ink alignment and recenters the visible ink after rendering. On the same smoke record, `horizontal_center_offset_px` moved from `-16.5` before correction to `-0.5` after correction, and MIMO now returns `ACCEPT: Text is centered and fits the target bounding box without overflow.`

This is the first closed layout feedback loop in Phase 4: MIMO reported a concrete visual issue, deterministic alpha metrics made the issue measurable, the renderer corrected the visible-ink placement, and MIMO accepted the corrected preview.

## Adjustment Already Tried

The validation prompt and per-call completion budget have been reduced across iterations:

- prompt length reduced from 419 characters to 241 characters
- prompt length reduced again from 241 characters to 205 characters
- `max_completion_tokens` reduced from 512 to 96
- observed token usage reduced from 778 to 324 total tokens
- latest observed token usage is 242 total tokens

The parser now supports direct text verdicts, so responses like `ACCEPT, text fits target` and `REVISE, ...` can be mapped into `mimo_vision` results without requiring JSON. Adding `thinking: {"type": "disabled"}` to the request made the latest persisted smoke return actual verdict text instead of spending almost all completion tokens on reasoning.

## Next Adjustment

The next iteration should broaden the closed feedback loop beyond one smoke record:

- run the same alpha alignment metric on a 10-30 record representative sample
- add candidate scoring for natural line breaks and visual balance, not only center placement
- optionally run validation on multiple layout candidates and select the first model-accepted candidate when deterministic scores are close
- keep recording every failed model response as an experiment artifact
- use fallback verdicts only as deterministic acceptance, not as visual/model approval

## Verification

Fresh verification before this report was written:

```text
python -m pytest tests/test_phase4_layout.py -q
10 passed in 0.93s

python -m pytest tests/test_phase4_layout_validation.py -q
9 passed in 0.20s

python -m pytest -q
69 passed in 3.96s

git diff --check
passed

AST length gate
passed

diff secret scan
passed
```

## Notes

- `.env` values were loaded locally but not printed.
- Request logs store URL, model, prompt length, image path, token usage, and response metadata.
- Request logs do not store `api-key`, bearer headers, raw environment values, or API keys.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
