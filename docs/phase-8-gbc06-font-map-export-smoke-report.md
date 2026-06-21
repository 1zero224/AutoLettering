# Phase 8 GBC06 Font Mapping Photoshop Export Smoke Report

Command:

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir "outputs/runs/phase2-gbc06-smoke" --font-selection-run-dir "outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke" --layout-run-dir "outputs/runs/phase4-gbc06-nonbubble-layout-smoke" --cleanup-run-dir "outputs/runs/phase6-gbc06-bubble-smoke" --cleanup-run-dir "outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke" --run-id phase8-gbc06-font-map-export-smoke --sample-limit 2 --font-mapping docs/photoshop-font-map.example.json
```

Generated artifacts:

```text
outputs/runs/phase8-gbc06-font-map-export-smoke
```

- `photoshop-manifest.json`
- `photoshop-import.jsx`
- `reports/phase8-report.md`
- `reports/photoshop-validation-checklist.md`

Manifest summary:

- Schema: `autolettering.photoshop.v1`
- Pages exported: 1
- Text layers exported: 2
- Manifest size: `6117` bytes
- JSX size: `4103` bytes
- Validation checklist size: `1180` bytes
- Missing cleanup layers: 0
- Expected cleanup patch layers in checklist: 2
- Effective cleanup methods: `bubble_fill=1`, `gpt_image2_masked_edit=1`

## Font Mapping

The export used `docs/photoshop-font-map.example.json`:

```json
{
  "toolboxPOP1GBJF-W5": "toolboxPOP1GBJF-W5"
}
```

Both exported records selected `[toolbox]POP1GB-JF-W5` with PostScript name `toolboxPOP1GBJF-W5`.
The manifest records `font.mapped_from = "toolboxPOP1GBJF-W5"` and `font.photoshop_font_name = "toolboxPOP1GBJF-W5"` for:

- `GBC06_01.png#1`
- `GBC06_01.png#16`

Users can copy the example mapping and change the value to the exact Photoshop-installed font name if Photoshop resolves the toolbox font differently from the extracted PostScript name.

## Limitations

- Photoshop is not available in this environment, so the generated JSX was not executed inside Photoshop.
- This smoke validates that the manifest and report consume a mapping file. It does not prove that a specific mapped font name exists in the user's Photoshop installation.
- The example mapping intentionally maps the extracted PostScript name to itself; it is a safe template rather than a claim about a separate local Photoshop font name.
- `reports/photoshop-validation-checklist.md` is now generated as the manual Photoshop execution gate; it lists the expected PSD folder, editable text layer count, cleanup patch layer count, font mapping file, and compatibility checks.

## Verification

```powershell
python -m pytest tests/test_phase8_photoshop_export.py -q
python -m pytest -q
```

Fresh result before this report was written:

```text
4 passed in 0.21s
56 passed in 2.79s
```
