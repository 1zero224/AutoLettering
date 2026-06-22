# Phase 4 竖排多列顺序实验：GBC06_01.png#14

## 1) 实验目标

对 `record_id=GBC06_01.png#14` 做真实图片对照实验，比较
`vertical_column_order="rtl"` 与 `vertical_column_order="ltr"` 的效果差异，验证中文竖排漫画文本在默认 RTL 顺序是否比 LTR 更符合版面自然度与阅读顺序。

## 2) 命令与输入

### 运行命令

```bash
python experiments/phase4_vertical_column_order_compare.py --run-id phase4-gbc06-01-14-vertical-column-order-v1
```

### 固定输入

- Layout 输入：`outputs/runs/phase4-gbc06-batch-14-15-layout-v2/layout-results.jsonl`
- Font 选择输入：`outputs/runs/phase3-gbc06-batch-14-15-17-mimo-font-selection/font-selections.jsonl`
- Cleaned 底图：`outputs/runs/phase6-gbc06-batch-14-15-region-fill-v2/crops/cleaned/GBC06-01-png-14.png`
- Before/after 参考图：`outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase7-preview/crops/before_after/GBC06-01-png-14.png`
- `record_id`：`GBC06_01.png#14`
- 预期文本：`昴也好\n仁菜也好`

## 3) 运行结果（本轮 run）

- 状态：`DONE`
- Run 目录：`outputs/runs/phase4-gbc06-01-14-vertical-column-order-v1`
- 对照图：`outputs/runs/phase4-gbc06-01-14-vertical-column-order-v1/debug/comparison/GBC06-01-png-14-vertical-column-order-comparison.png`
- 结构化结果：`outputs/runs/phase4-gbc06-01-14-vertical-column-order-v1/reports/vertical-column-order-comparison-result.json`
- MIMO 评估结果：`outputs/runs/phase4-gbc06-01-14-vertical-column-order-v1/reports/vertical-column-order-mimo-eval.json`

## 4) 产物清单

- `.../debug/render/GBC06-01-png-14-rtl.png`
  RTL 渲染底图（透明文字图）
- `.../debug/render/GBC06-01-png-14-ltr.png`
  LTR 渲染底图（透明文字图）
- `.../debug/overlay/GBC06-01-png-14-rtl-on-cleaned.png`
  RTL 叠加到 cleaned 的对照图
- `.../debug/overlay/GBC06-01-png-14-ltr-on-cleaned.png`
  LTR 叠加到 cleaned 的对照图
- `.../debug/comparison/GBC06-01-png-14-vertical-column-order-comparison.png`
  包含 before/after、cleaned、RTL/LTR 渲染及 overlay 的统一对照图，包含中文标注

## 5) MIMO 评估

本次实验已执行 MIMO 调用（`mimo-v2.5`），请求摘要已保存至结构化结果与独立 JSON。

### Prompt 方向
- 聚焦中文竖排漫画嵌字可读性、左右列顺序（中文竖排常见从右到左）、版面自然度、留白与错位风险
- 未要求其按 OCR 校验文本，不作为硬规则

### MIMO 输出摘要（关键点）
- 推荐顺序：`best_order = "rtl"`
- 可读性与版面自然度评分：较高（`readability_score=8, naturalness_score=8`）
- 关键说明：LTR 认为存在列顺序颠倒导致阅读跳动，RTL 更符合中文漫画竖排阅读习惯
- 局限：MIMO 在说明中把 `昴也好` 误读成了 `昂也好`；本轮只采用它对列顺序与版面自然度的判断，不把它当作 OCR/文本正确性校验依据。

> 说明：`outputs/.../reports/vertical-column-order-mimo-eval.json` 中也保存了完整 `raw_text` 与 `response`，便于人工复核。

## 6) 人工评估建议关注点

请在对照图中逐项核对以下项后给出最终使用判断：

- 列顺序：是否真正符合从右到左阅读轨迹
- 字符连贯性：是否出现字符顺序错乱、重叠、断笔
- 边界对齐：文字框与清理底图边界是否稳妥
- 版面比例：与参考 before/after 的自然度对比
- 文字粗细/留白：RTL 与 LTR 在视觉体感上的差异

## 7) 结论

本轮实验实证结果倾向 `RTL` 优于 `LTR`（MIMO 与视觉对比一致）。
**当前证据不足以支持将默认行为改为 LTR**；建议将默认保持 `RTL`，将 `LTR` 仅保留为可选实验参数，或用于特定异常样本的人工覆写场景。
