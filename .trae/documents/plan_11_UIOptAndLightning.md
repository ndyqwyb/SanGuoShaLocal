# plan_11_UIOptAndLightning

## Summary
本计划解决 4 个问题：
1) UI 在手牌数量变化时，双方武将框与底部播报栏宽度会“跟着变宽/变窄”，希望恒定为“8 张手牌的宽度”；  
2) 在恒定宽度前提下，右侧不要再出现明显大留白（与左侧留白一样窄）；  
3) 武将信息区需要显示判定区（延时锦囊）内容；  
4) 规则：对【闪电】使用【无懈可击】时，【闪电】应跳过本次判定并移动到下一个人的判定区，而不是直接进入弃牌堆。

## Current State Analysis
### UI 宽度动态变化根因
- [gui.py](file:///workspace/sanguosha/gui.py) `_sync_hand()` 仅为“当前手牌数量”创建按钮并 grid 到 `hand_frame`：
  - 列数随手牌数变化（例如 6 张只占 6 列，8 张占 8 列），导致 `hand_frame` 的“请求宽度”动态变化。
  - `page` 的整体宽度在 Tk 的布局传播下会跟随内容变化，从而导致上方武将框、下方日志区一起“萎缩/扩张”。
- `HAND_MAX_COLS = 8` 已用于换行，但当手牌不足 8 张时，第一行仍只占用较少列，因此宽度仍会缩。

### 右侧留白原因
- 当前窗口允许缩放且默认 `geometry("860x620")`；当内容宽度 < 窗口宽度时右侧会显著留白。
- 用户要求的“右侧留白和左侧一样窄”本质上是：默认窗口宽度应贴合内容宽度（8 张手牌宽度），并且内容容器应能横向填满，而不是只占左侧。

### 判定区不显示
- `PlayerSnapshot` 已包含 `judgment_area`（见 [ui_protocol.py](file:///workspace/sanguosha/ui_protocol.py#L15-L29)），`gui.py` 当前在 `_format_player_*` 里没有把它显示在武将框布局中。

### 闪电无懈后处理不符
- [game.py](file:///workspace/sanguosha/game.py#L292-L321) `_resolve_judgment_area()`：
  - 若延时牌被无懈（`_is_delayed_trick_countered(...)` 返回真），直接 `discard(delayed)`。
  - 这会让【闪电】被无懈后直接进弃牌堆，而不是转移到下一个角色判定区。

## Proposed Changes
### A. 手牌区固定为 8 列宽（手牌不足也不缩）
- 文件：`sanguosha/gui.py`
- 核心做法：引入“8 个固定槽位”，永远占位，从而让 `hand_frame` 的请求宽度恒定。
- 实现方案（推荐）
  1. 在 `App.__init__` 增加 `self._hand_slot_buttons: list[Any]`（固定长度 8）。
  2. `_build_battle_page()` 中创建 8 个“槽位按钮”（disabled，占位用），先 grid 到 `hand_frame` 的 `row=0, col=0..7`，并设置固定按钮宽度（例如 `width=<常量>`）。
  3. `_sync_hand()` 只更新这些槽位：
     - `idx < len(cards)`：把槽位按钮改为可用、设置文本为牌面、绑定 command 选择对应 idx
     - `idx >= len(cards)`：槽位按钮置为 disabled、文本置空（或 “ ”），但仍占宽
  4. 第二行及以上（当手牌 > 8）继续按既定换行策略扩展（row=1...），这部分不要求恒宽（因为首行已锁定 8 列宽，整体不会随首行少牌而缩）。
- 关键点
  - 占位槽位要一直存在且宽度固定，否则布局仍会随内容收缩。

### B. 默认窗口宽度贴合“8 张手牌宽度”，并减少右侧多余留白
- 文件：`sanguosha/gui.py`
- 做法
  - 在 UI 初始化后（或切换到 battle 页后）做一次 `update_idletasks()`，读取 battle 页容器的 `winfo_reqwidth()`，将 `root.geometry` 设置为“所需宽度 + 少量边距”，作为默认窗口宽度。
  - 同时保留 `resizable(True, True)`，用户仍可手动放大/缩小；默认启动时右侧留白会显著减少且左右边距一致（由 `_frame padding=16` 决定）。
- 注意
  - 只在初次进入 battle 页时设置一次，避免运行时闪动或强行抢用户调整。

### C. 武将框补充判定区显示（并保持两边等高）
- 文件：`sanguosha/gui.py`
- 做法
  - 为双方各新增一个 `StringVar`：`_self_judge_var`、`_enemy_judge_var`。
  - 在 `_tick()` 中从 snapshot 生成：
    - `判定区：-`（无牌）
    - `判定区：乐不思蜀、闪电`（有牌）
  - 在 self/enemy box 内增加一行固定显示“判定区”：
    - 行结构固定（base/equip/horse/judge 共 4 行），保证双方等高。

### D. 闪电被无懈后转移到下一个人的判定区
- 文件：`sanguosha/game.py`
- 修改点
  - 在 `_resolve_judgment_area()` 的“被无懈抵消”分支：
    - 若 `delayed.name != LIGHTNING`：维持现状（进弃牌堆）
    - 若 `delayed.name == LIGHTNING`：
      - 跳过本次判定
      - 将【闪电】转移到下一个角色判定区（沿用当前代码非触发时的 `next_player = other_player(actor)` 逻辑；多人扩展时可替换为“座次下家”）
      - 若下家已存在闪电，则按现有 `_has_delayed` 规则不叠加，改为进入弃牌堆
- 需要同步日志：输出 `【闪电】被无懈可击抵消，转移给 X` 或复用现有 `【闪电】转移给 X` 文案。

## Assumptions & Decisions
- “恒定宽度”以“第一行 8 张手牌槽位”的宽度为基准；当手牌超过 8 张时允许向下扩展，不再横向扩展。
- 默认窗口宽度通过 battle 页 `reqwidth` 自适配一次，满足不同平台字体差异；不会在运行中反复调整。
- 判定区显示为“判定区：xxx”文本，不做图标化。
- 闪电转移的“下一个人”在 1v1 仍为对手；多人模式后再替换为座次下家。

## Verification Steps
### GUI 手动验收
- 手牌数量从 8 降到 6 时：上方两侧武将框与下方日志区宽度不再萎缩（保持 8 槽位宽度）。
- 手牌占满 8 张时：窗口默认宽度下右侧留白与左侧留白接近一致（不再出现明显右侧大空白）。
- 双方武将框均显示“武器/防具/+1/-1/判定区”固定区域，判定区有牌时可见。

### 自动化回归
- 更新/新增 `tests/test_core.py`：
  - 闪电在判定阶段被无懈：不进入弃牌堆，而是转移到下一名角色判定区（若下家已有闪电则弃置）。
- 运行 `pytest -q`。

