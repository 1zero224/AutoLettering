# GBC06 框内 Comic RT-DETRv2 全链路说明

## 结论

当前检测框可以接入原设想的“按点位匹配最近检测框 -> 绑定 -> 自动计算文字大小 -> 结合视觉模型决定字体 -> 框内嵌字”流程。

本次用 `GBC06 (已翻 斗笠)` 的 `框内` 分组完整跑通 Phase 1-8：

- `框内` 输入记录：153 条
- RT-DETRv2 成功绑定：149 条
- RT-DETRv2 fallback：4 条
- MIMO 字体选择：149/149 条真实 API 成功
- Phase 4 布局：149/149 条生成
- Phase 6 框内清字：149/149 条完成
- Phase 7 页面预览：17 页，149 条记录
- Phase 8 Photoshop 导出：17 页，149 个可编辑文字层
- gpt-image-2 对照样本：1 条真实 masked edit 成功，未并入最终可编辑嵌字链路

框外记录本次没有进入 Phase 2-8。框内嵌字采用“清字 crop + 可编辑文字层”路径，没有用 `gpt-image-2` 直接生成框内文字位图。原因是本次目标要求“嵌字只做框内”，而现有框内路径需要 Photoshop 可编辑文本层；`gpt-image-2` 更适合框外/检测失败/复杂非气泡直接替换路线，后续应单独做质量门禁。

## 运行命令

```powershell
python experiments/full_gbc06_frame_in_comic_pipeline.py `
  --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" `
  --font-dir "工具箱漫画字体V2.5" `
  --output-root outputs/runs `
  --run-id gbc06-frame-in-comic-full-20260628 `
  --sample-limit 1000 `
  --env-file .env `
  --comic-detector-model-path "comic-text-and-bubble-detector\detector_int8.onnx" `
  --comic-detector-conf-threshold 0.5 `
  --comic-detector-max-distance-px 120 `
  --font-limit 12 `
  --mimo-timeout-sec 90 `
  --mimo-max-consecutive-timeouts 2 `
  --cleanup-method text_mask_inpaint `
  --inpaint-method opencv_telea `
  --mask-dilate-px 3
```

第一次直接使用原 `run_phase3_vision_selection` 时，远端 MIMO 请求长时间没有返回且阶段不落盘。随后新增了可恢复的 MIMO 字体选择路径：每条记录独立子进程调用 MIMO，逐条追加 `font-selections.jsonl` / `api-calls.jsonl`，并设置单条超时。最终第二次运行中 149 条全部真实返回，没有触发 fallback。

## 顶层产物

顶层 run 目录：

```text
outputs/runs/gbc06-frame-in-comic-full-20260628
```

关键文件：

- `outputs/runs/gbc06-frame-in-comic-full-20260628/manifest.json`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/reports/pipeline-report.md`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/frame-in-records.jsonl`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/final-page-contact-sheet.png`

最终预览页：

- `outputs/runs/gbc06-frame-in-comic-full-20260628/runs/phase7-page-preview/pages/*.png`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/runs/phase7-page-preview/debug/page_overlays/*.png`

Photoshop 导出：

- `outputs/runs/gbc06-frame-in-comic-full-20260628/runs/phase8-photoshop-export/photoshop-manifest.json`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/runs/phase8-photoshop-export/photoshop-import.jsx`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/runs/phase8-photoshop-export/reports/photoshop-validation-checklist.md`

gpt-image-2 对照样本：

- `outputs/runs/gbc06-frame-in-comic-full-20260628/gpt-image-2-frame-in-sample/manifest.json`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/gpt-image-2-frame-in-sample/GBC06-04-png-9-gpt-mask.png`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/gpt-image-2-frame-in-sample/GBC06-04-png-9-gpt-image-2-output.png`
- `outputs/runs/gbc06-frame-in-comic-full-20260628/gpt-image-2-frame-in-sample/GBC06-04-png-9-gpt-image-2-normalized.png`

## 阶段说明

### Phase 1 Parse

输入：

- `GBC06 (已翻 斗笠)\翻译_0.txt`

输出：

- `runs/phase1-parse/manifest.json`
- `runs/phase1-parse/debug/label_points/*.png`
- `runs/phase1-parse/samples/phase1-sample.jsonl`
- `runs/phase1-parse/reports/phase1-report.md`

作用：

- 解析 LabelPlus。
- 只从可用图片里收集 `group_name == "框内"` 的记录。
- 本次可用图片中的 `框内` 记录为 153 条。

### Phase 2 Comic RT-DETRv2 检测和点位绑定

输入：

- Phase 1 解析出的 `框内` record id 列表。
- 本地模型：`comic-text-and-bubble-detector\detector_int8.onnx`

输出：

- `runs/phase2-comic-rtdetrv2/detections.jsonl`
- `runs/phase2-comic-rtdetrv2/debug/detection/*.png`
- `runs/phase2-comic-rtdetrv2/reports/manual-review.csv`
- `runs/phase2-comic-rtdetrv2/reports/phase2-report.md`

绑定逻辑：

- 对每页运行 comic RT-DETRv2。
- Detector 输出 `bubble`、`text_bubble`、`text_free`。
- Phase 2 只把 `text_bubble` / `text_free` 当作可嵌字文字框。
- 对每条 LabelPlus 点位，选择阈值 `120px` 内最近的文字框。
- 成功绑定后写入 `selected_text_box_xyxy`、`selected_text_full_xyxy`、`selected_text_body_xyxy`，供 Phase 3-8 复用。

结果：

- 检测行数：153
- 成功绑定：149
- fallback：4
- 成功绑定类别：`text_bubble=149`
- 失败原因：`no_comic_text_box_within_threshold=4`
- matched 距离范围：最小 `0.0px`，最大 `82.037px`，p95 `15.0px`
- 最低 selected score：`0.6732`

未进入后续链路的 4 条：

- `GBC06_04.png#13`
- `GBC06_06.png#5`
- `GBC06_07.png#1`
- `GBC06_07.png#7`

这 4 条在 120px 阈值内没有 `text_bubble` / `text_free`，最近候选均为 `bubble` 类。当前策略没有强行把 bubble 当文字框，这是正确的保守行为。

### Phase 3 Font Comparison

输入：

- `runs/phase2-comic-rtdetrv2/detections.jsonl`
- 字体目录：`工具箱漫画字体V2.5`

输出：

- `runs/phase3-font-comparison/font-index.jsonl`
- `runs/phase3-font-comparison/font-comparisons.jsonl`
- `runs/phase3-font-comparison/crops/source_text/*.png`
- `runs/phase3-font-comparison/crops/rendered_text/*/*.png`
- `runs/phase3-font-comparison/debug/font_comparison/*.png`

结果：

- 进入比较图的记录：149
- 每条候选字体数：12
- 状态：`candidates_generated=149`

说明：

- 这一步只处理 Phase 2 `status == ok` 且有 `selected_text_box_xyxy` 的记录。
- 4 条 fallback 不进入标准框内嵌字链路。

### Phase 3 MIMO Font Selection

输入：

- `runs/phase3-font-comparison/font-comparisons.jsonl`
- MIMO 模型：`mimo-v2.5`

输出：

- `runs/phase3-mimo-font-selection/font-selections.jsonl`
- `runs/phase3-mimo-font-selection/reports/api-calls.jsonl`
- `runs/phase3-mimo-font-selection/reports/resume-metadata.json`
- `runs/phase3-mimo-font-selection/reports/phase3-vision-report.md`

结果：

- 字体选择记录：149
- `selected=149`
- `selection_source=mimo_vision=149`
- MIMO API：`ok=149`
- deterministic fallback：0

实现细节：

- 新 orchestration 脚本中使用可恢复 MIMO 选择：每条记录独立子进程调用一次 MIMO，写一条结果。
- resume metadata 会记录 `font-comparisons.jsonl` 内容 hash、过滤后的候选行 hash、record id 列表、MIMO base URL/model、timeout 和 fallback 策略；这些条件变化时会清理旧 selection/API rows 后重算。
- 单条记录只有 `font-selections.jsonl` 和 `reports/api-calls.jsonl` 都存在时才视为完成；如果进程在两次写入之间中断，下次运行会丢弃半写入记录并重试。
- 单条超时默认 90 秒。
- 连续 2 条超时后，后续会走 deterministic fallback，避免整条链路卡住。
- 本次实际没有触发超时，149 条均为真实 MIMO 选择。

### Phase 4 Layout

输入：

- `runs/phase3-mimo-font-selection/font-selections.jsonl`
- `runs/phase2-comic-rtdetrv2/detections.jsonl`

输出：

- `runs/phase4-layout-search/layout-results.jsonl`
- `runs/phase4-layout-search/debug/layout_candidates/*.png`
- `runs/phase4-layout-search/reports/phase4-report.md`

结果：

- `layout_generated=149`
- 方向：`vertical=110`，`horizontal=39`

说明：

- Phase 4 使用 Phase 2 的绑定 bbox 作为布局目标。
- 自动搜索字号、方向、换行、行距、字距、颜色和目标 bbox。
- 目前是 deterministic layout，没有额外 MIMO 版面自然度评分；长句会出现占满气泡、换行生硬的问题。

### Phase 6 Bubble Cleanup

输入：

- `runs/phase2-comic-rtdetrv2/detections.jsonl`
- `runs/phase4-layout-search/layout-results.jsonl`

输出：

- `runs/phase6-bubble-cleanup/cleanup-results.jsonl`
- `runs/phase6-bubble-cleanup/crops/before/*.png`
- `runs/phase6-bubble-cleanup/crops/cleaned/*.png`
- `runs/phase6-bubble-cleanup/crops/before_after/*.png`
- `runs/phase6-bubble-cleanup/reports/phase6-report.md`

配置：

- `cleanup_method=text_mask_inpaint`
- `inpaint_method=opencv_telea`
- `mask_dilate_px=3`

结果：

- `cleaned=149`
- 方法：`bubble_text_mask_opencv_telea_inpaint=149`

说明：

- 这一步只对 `框内` 执行。
- 产物是清掉原文后的 crop，最终文字仍由 Phase 7/8 可编辑文本层叠加。

### Phase 7 Preview

输入：

- Phase 2 detection
- Phase 4 layout
- Phase 6 cleanup

输出：

- `runs/phase7-page-preview/preview-results.jsonl`
- `runs/phase7-page-preview/manifest.json`
- `runs/phase7-page-preview/pages/original/*.png`
- `runs/phase7-page-preview/pages/cleaned/*.png`
- `runs/phase7-page-preview/pages/*.png`
- `runs/phase7-page-preview/debug/page_overlays/*.png`
- `runs/phase7-page-preview/crops/before_after/*.png`
- `runs/phase7-page-preview/crops/context_before_after/*.png`

结果：

- 页面预览：17 页
- 预览记录：149 条

代表性产物：

- 全页 contact sheet：`outputs/runs/gbc06-frame-in-comic-full-20260628/final-page-contact-sheet.png`
- 示例页面：`outputs/runs/gbc06-frame-in-comic-full-20260628/runs/phase7-page-preview/pages/GBC06-04-png.png`
- 示例 before/after：`outputs/runs/gbc06-frame-in-comic-full-20260628/runs/phase7-page-preview/crops/context_before_after/GBC06-04-png-9.png`

视觉观察：

- 文字均被限制在框内。
- 大部分竖排气泡能够放入目标框。
- 部分长句的字号和断行还不够自然，后续需要引入版面自然度评分或规则补强。
- 部分短句可读但风格较统一，MIMO 选字体解决了候选选择，但还没有解决描边、粗细、压缩比例等字效问题。

### Phase 8 Photoshop Export

输入：

- Phase 2 detection
- Phase 3 MIMO font selection
- Phase 4 layout
- Phase 6 cleanup
- Phase 7 preview

输出：

- `runs/phase8-photoshop-export/photoshop-manifest.json`
- `runs/phase8-photoshop-export/photoshop-import.jsx`
- `runs/phase8-photoshop-export/reports/phase8-report.md`
- `runs/phase8-photoshop-export/reports/photoshop-validation-checklist.md`

结果：

- Photoshop pages：17
- editable text layers：149
- repaired pages：17

每页图层数：

- `GBC06_01.png`: 15
- `GBC06_02.png`: 13
- `GBC06_03.png`: 10
- `GBC06_04.png`: 15
- `GBC06_05.png`: 9
- `GBC06_06.png`: 8
- `GBC06_07.png`: 5
- `GBC06_14.png`: 11
- `GBC06_15.png`: 11
- `GBC06_16.png`: 10
- `GBC06_17.png`: 9
- `GBC06_18.png`: 5
- `GBC06_19.png`: 7
- `GBC06_20.png`: 9
- `GBC06_21.png`: 9
- `GBC06_22.png`: 1
- `GBC06_30.png`: 2

说明：

- `photoshop-import.jsx` 读取 `photoshop-manifest.json`。
- 每条记录导出一个可编辑 Photoshop 文字层。
- Phase 7 提供整页 repaired image 时，PSD 中会有 `修复图像` 层和可编辑文本层。
- 字体名称使用 `font.photoshop_font_name`，失败时回退候选字体名。

## 质量判断

可用部分：

- 点位到检测框绑定已经能替换或补强原 Phase 2 CTD/CTA/CV 检测。
- 对框内气泡，RT-DETRv2 的 `text_bubble` 输出比之前纯 CV/CTD mask 更直接，能给 Phase 4/6/8 共享同一个 bbox。
- MIMO 字体选择在本次 149 条上全部真实返回，输出稳定。
- Photoshop export 可以导出 149 个可编辑文本层，具备后续人工修正基础。
- gpt-image-2 在 `GBC06_04.png#9` 的真实 masked edit 对照样本中能生成目标中文内容。

主要限制：

- 4 条框内记录没有进入后续链路，因为 120px 内无文字框；后续可以考虑用 `bubble` 类做二次 bbox 推断，但不能直接把 bubble 当文字框。
- 当前 Phase 4 没有视觉模型评估排版自然度；长句、短句和特殊语气词仍需更细规则。
- 当前清字是 `opencv_telea`，对白气泡可用，但复杂网点/渐变背景上可能残留。
- `gpt-image-2` 对照样本输出是位图 crop，且原始返回尺寸为 1233x1275，需要额外 normalize 才能贴回原 crop；它不保留 Photoshop 可编辑文字层。因此本次最终 Phase7/8 没有使用该位图结果。

## 后续建议

1. 给 Phase 2 增加 fallback 子策略：当无 `text_bubble/text_free` 时，用 `bubble` bbox + 点位局部 OCR/文字像素定位推导内部文字框。
2. 给 Phase 4 增加 MIMO 版面自然度评分，至少检查字号过大、断行不自然、文字太靠边、竖排列宽不合理。
3. 在 Phase 6 对复杂气泡尝试 `bt_lama_large` 或 mask refinement 网格，并用 Phase7 before/after crop 做自动质量筛选。
4. 把 Phase 8 的 font mapping 做成可配置表，减少 Photoshop 字体名不匹配。
5. 单独为 `框外` 设计 `MIMO locator + gpt-image-2 masked edit + quality gate` 路线，不混入本次框内可编辑文字层路径。
