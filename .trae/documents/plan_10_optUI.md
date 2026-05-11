# plan_10_optUI

## Summary
本计划优化可视化 UI 的布局与交互体验，解决 4 个问题：
1) 初始状态右侧存在明显留白；2) 我方/敌方武将框尺寸不一致且内容行会动态挤压；3) 手牌过多时横向扩展导致整体越拉越宽；4) “跳过 AI 等待”按钮含义不清，评估是否隐藏/移除。

目标是：窗口在默认尺寸下尽量“刚好填满”、信息区对齐、手牌自动换行向下扩展，并减少不必要的控件。

## Current State Analysis
- 布局实现集中在 [gui.py](file:///workspace/sanguosha/gui.py) 的 `_build_battle_page()` 与 `_sync_hand()`。
  - 双方武将框使用 `Frame(... relief="groove")` + 1 行 `Label(textvariable=...)` 展示，敌方额外多 1 个“查看技能”按钮导致高度不同。
  - 武器/防具/+1/-1 目前是拼进同一行字符串（`_format_player`），导致长度变化时框体观感不稳定。
  - 手牌按钮在 `_sync_hand()` 中固定 `row=0, column=idx` 横向铺开，手牌多时会把界面越撑越宽。
- 窗口尺寸目前是 `root.minsize(860, 620)` 且允许缩放；右侧留白主要来自“内容区域本身不横向填满/手牌不换行导致用户倾向放大窗口”的叠加观感。
- “跳过 AI 等待”按钮触发 [visual_engine.py](file:///workspace/sanguosha/visual_engine.py) 的 `ActionType.SKIP_AI_WAIT`，作用是跳过 AI 动作节奏延时（`SkippableDelay.wait()`），默认延时为 `0.35s`。

## Proposed Changes
### A. 消除右侧留白（默认尺寸更贴合 + 横向自适应）
- 文件：`sanguosha/gui.py`
- What
  - 设定 battle 页的“推荐宽度”更贴近实际组件宽度（不强制固定，但默认 geometry 更小），并确保关键容器 `sticky="nsew"` 且 column/row `weight` 合理，避免内容只挤在左侧。
  - 对日志区与手牌区增加横向填充策略：日志控件本身可拉伸；手牌区改为多行换行（见 C），从源头避免横向无限扩展。
- How
  - `_build_battle_page`：确保 `page.grid_columnconfigure(0, weight=1)` 保持，日志控件维持 `sticky="nsew"`。
  - `hand_frame` 改为按列数换行布局（见 C），使内容宽度自然收敛，默认窗口无需很宽。

### B. 我方/敌方武将框尺寸一致 + 固定的装备占位行
- 文件：`sanguosha/gui.py`
- What
  - 将我方/敌方信息框改为“固定三段布局”，两边使用相同的 grid 行结构，从而 x/y 尺寸一致：
    1) 第一行：角色基础信息（姓名/武将/HP/手牌数）
    2) 第二行：武器 + 防具（即使为空也显示占位，如 “武器 - / 防具 -”）
    3) 第三行：+1马 / -1马（同样占位）
  - 敌方“查看技能”按钮放在框内，但占据固定位置（例如放到标题行右侧或底部固定列），不再改变框体高度。
- How
  - 为 self/enemy 分别新增 3 个 `StringVar`（base/equip/horse），并在 `_tick()` 中从 snapshot 填充：
    - base：`{name}({general}) HP x/y 手牌 n`
    - equip：`武器 {weapon or "-"}  防具 {armor or "-"}`（需要 snapshot 暴露 armor；目前 PlayerSnapshot 已有 armor 字段）
    - horse：`+1 {plus_horse or "-"}  -1 {minus_horse or "-"}`
  - 重排 enemy_box：标题 + “查看技能”按钮在同一行（左右对齐），下面三行信息与我方一致。

### C. 手牌多行换行（向下扩展而不是向右扩展）
- 文件：`sanguosha/gui.py`
- What
  - `_sync_hand()` 将手牌按钮网格从“单行横排”改为“固定列数自动换行”。
  - 例如默认每行最多 8 张，超出后换到下一行：`row = idx // max_cols, col = idx % max_cols`。
- How
  - 新增一个 `HAND_MAX_COLS` 常量（例如 8，可按窗口宽度后续自适应），并改动 `btn.grid(...)`。
  - `hand_frame` 的 `grid_columnconfigure` 可不必逐列 weight（按钮自适应即可），但需要保证 `hand_area` 的 `sticky="nsew"` 不变。

### D. “跳过 AI 等待”按钮评估与优化
- 文件：`sanguosha/gui.py`, `sanguosha/visual_engine.py`（仅当需要进一步改动）
- 当前作用结论
  - 该按钮用于跳过 AI 动作的节奏延时（默认 0.35s），属于“加速/调试”用途。
- 建议方案（默认采用第 1 项）
  1) 隐藏化：仅在“电脑行动期间”或“AI 延时>0 且正在输出电脑日志时”显示该按钮；平时不显示，减少噪音。
  2) 明确化：将文案改为“跳过 AI 动作延时”，并在 hover/提示区显示解释（本项目目前无 hover，可在 `_hint_var` 或按钮旁加简短说明）。
  3) 移除：彻底删除该按钮（代价是 AI 回合节奏固定，无法临时加速）。

## Assumptions & Decisions
- 手牌换行的每行列数先采用固定值（默认 8），不做按窗口宽度动态计算；若后续需要更智能再迭代。
- 武将框占位行永远显示，内容缺失时以 “-” 占位，保证布局稳定。
- “查看技能”按钮保留，但不再影响敌方框高度（通过固定行/列布局解决）。
- “跳过 AI 等待”按钮默认不删除，而是改为“条件显示 + 文案更清晰”（若你坚持删除，可在实现阶段直接采用移除方案）。

## Verification Steps
### GUI 手动验收
- 初始打开 battle 页时右侧不出现明显大块留白（默认尺寸下内容更饱满，手牌不会把窗口撑到很宽）。
- 我方/敌方武将框完全等宽等高，且装备/坐骑占位行固定存在。
- 手牌数量增多时自动换行向下扩展，不再横向无限扩展导致 UI 被迫加宽。
- “跳过 AI 等待”按钮要么被隐藏（非 AI 行动时看不到），要么改名后含义清晰；不会造成布局拥挤。

### 自动化回归
- 运行 `pytest -q`（确保仅 UI 布局改动不影响规则测试）。

