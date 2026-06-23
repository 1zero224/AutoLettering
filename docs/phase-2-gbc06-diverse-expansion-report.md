# Phase 2 GBC06 Diverse Expansion Report

## Scope

This experiment expands Phase 2 detection beyond the first two completed pages and deliberately samples mixed text types:

```text
GBC06_06.png#3   框内  long regular vertical bubble
GBC06_17.png#3   框外  black-card/sign text
GBC06_18.png#3   框内  diamond/announcer-style block candidate
GBC06_29.png#2   框外  large non-bubble page text
GBC06_33.png#1   框外  color promotional side text with numbers
```

## Commands

Initial diverse Phase 2 run:

```powershell
python experiments/phase2_detect_text_regions.py --run-id phase2-gbc06-diverse-expansion-v1 --sample-limit 5 --record-id "GBC06_18.png#3" --record-id "GBC06_06.png#3" --record-id "GBC06_17.png#3" --record-id "GBC06_29.png#2" --record-id "GBC06_33.png#1" --radius-x 260 --radius-y 300
```

Color-light-text follow-up:

```powershell
python experiments/phase2_detect_text_regions.py --run-id phase2-gbc06-diverse-expansion-v2-color-light-text --sample-limit 5 --record-id "GBC06_18.png#3" --record-id "GBC06_06.png#3" --record-id "GBC06_17.png#3" --record-id "GBC06_29.png#2" --record-id "GBC06_33.png#1" --radius-x 260 --radius-y 300
```

## Detection Results

| Record | v1 full bbox | v2 full bbox | Decision |
| --- | --- | --- | --- |
| `GBC06_06.png#3` | `[557,490,750,649]` | `[557,490,750,649]` | Usable for next phase. |
| `GBC06_17.png#3` | `[1187,151,1234,312]` | `[1187,151,1234,312]` | Partial/narrow sign crop; keep for later sign-specific pass. |
| `GBC06_18.png#3` | `[1087,1335,1312,1621]` | `[1087,1335,1312,1621]` | Usable for next phase. |
| `GBC06_29.png#2` | `[8,634,182,909]` | `[8,634,182,909]` | Partial large-title crop; keep for large non-bubble title pass. |
| `GBC06_33.png#1` | `[1207,975,1249,1008]` | `[1180,463,1281,645]` | Improved from wrong tiny fragment to main white side text, but still partial. |

Key visual artifact:

```text
outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text/debug/diverse-v1-v2-contact-sheet.png
```

## Root Cause For Color Promotional Text

`GBC06_33.png#1` has white lettering on a mid-dark red promotional band. The old light-text branch only enabled white text detection when the local background was nearly black (`gray < 95`). On this page, the label neighborhood is mostly mid-dark red:

```text
local radius 36: gray<95=0.0542, gray<140=0.9214, gray<190=0.9595
```

The dark-text branch treated the red band itself as a dark region and rejected the large background component. The remaining selected box was only a small bottom shadow fragment.

## Code Change

- `autolettering/detection/cv_text.py`
  - Allows light-text detection on mid-dark colored backgrounds when the local area has bright pixels and enough `gray < 150` context.
  - Uses a `gray < 150` dilated context mask for white text on colored dark backgrounds.
- `autolettering/text_bbox.py`
  - Extends light-on-dark same-column vertical text downward when candidates have strong horizontal overlap and bounded vertical gaps.
  - Keeps the existing guard against bridging separate upper light-text art.

## Current Decision

Proceed with `GBC06_06.png#3` and `GBC06_18.png#3` as the next small Phase 3-7 expansion candidates.

Do not promote `GBC06_17.png#3`, `GBC06_29.png#2`, or `GBC06_33.png#1` into the full pipeline yet:

- `GBC06_17.png#3`: needs sign/card-specific region interpretation.
- `GBC06_29.png#2`: needs large non-bubble title grouping beyond the nearest segment.
- `GBC06_33.png#1`: improved but needs full promotional side-text grouping, including the date and `発売!!`.
