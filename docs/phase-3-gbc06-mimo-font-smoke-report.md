# Phase 3 GBC06 MIMO Font Selection Smoke Report

## Documentation Basis

MIMO image understanding was checked against the official documentation through Context7:

```powershell
npx ctx7@latest library "Xiaomi MiMo" "MIMO image understanding OpenAI compatible chat completions base64 image"
npx ctx7@latest docs /websites/mimo_mi_en-us "MIMO image understanding chat completions base64 image_url api-key header response choices"
```

Confirmed interface shape:

- endpoint: `/v1/chat/completions`
- auth header: `api-key`
- image input: `messages[].content[]` item with `type=image_url`
- local image format: `data:{MIME_TYPE};base64,...`
- model used in this run: `mimo-v2.5`

## Command

```powershell
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-font-smoke --run-id phase3-gbc06-mimo-font-smoke --sample-limit 1
```

## Output

Run directory:

```text
outputs/runs/phase3-gbc06-mimo-font-smoke
```

Generated artifacts:

- `font-selections.jsonl`
- `reports/api-calls.jsonl`
- `reports/phase3-vision-report.md`

## Result Summary

- Input comparison run: `outputs/runs/phase3-gbc06-font-smoke`
- Records submitted: 1
- Selected: 1
- Failed: 0
- Record: `GBC06_01.png#1`
- Selected font: `font-07af2e938e0c`
- Selected family: `[toolbox]WenHei-JF-Bold`
- Confidence: `0.95`
- Request prompt characters: 1703
- Request image count: 1
- Token usage: 3150 total tokens
- Source crop path preserved for downstream layout: `outputs/runs/phase3-gbc06-font-smoke/crops/source_text/GBC06-01-png-1.png`

## Model Reasoning Summary

The model selected `font-07af2e938e0c` because it judged the source manga text as bold, thick, clean dialogue lettering and matched it to the WenHei bold candidate.

This is a real model-backed result for one sample only. It is not yet enough to claim robust font selection across the sample set.

An earlier run on the same comparison grid selected `font-51a342d311b2` with confidence `0.92`, and one retry returned invalid JSON. This shows the Phase 3 model-backed selector still needs stability controls such as repeated sampling, stricter JSON mode if available, or deterministic fallback rules.

## Safety Notes

- `.env` values were loaded locally but not printed.
- Request logs store URL, model, prompt length, image path, token usage, and response metadata.
- Request logs do not store `api-key`, bearer headers, raw environment values, or API keys.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.

## Verification

```powershell
python -m pytest -q
```

Fresh result before this report was written:

```text
23 passed in 1.07s
```
