# plan_optimize05

## Summary
本次优化聚焦 4 个问题：统一“确认出牌”按钮文案、修复“返回开始”未真正重置对局、修复结束页“返回开始页”无效、以及调整延时锦囊【乐不思蜀】【兵粮寸断】【闪电】的【无懈可击】询问时机。  
核心目标是让 GUI 交互语义更清晰、回局流程真正可重开、并使延时锦囊的响应时机符合“判定阶段触发时再响应”的规则期望。

## Current State Analysis
- `sanguosha/gui.py`
  - 出牌区按钮文案为“确认出牌”，但该按钮同时用于 `play` / `discard_select` / `skill_card_select` 三类提交，存在语义歧义。
  - 战斗页“返回开始”按钮仅执行 `self.show("start")`，不会通知引擎取消当前会话和重置状态。
  - 结束页“返回开始页”调用 `_restart_game()`，但当前 `_restart_game()` 只做 UI 清理 + `show("start")`，也不会触发引擎重置，因此可能出现“看似返回但旧会话仍在”的问题。
- `sanguosha/visual_engine.py`
  - 引擎已支持 `ActionType.RESTART`，其逻辑会取消当前会话、等待线程结束、重置快照与队列，并重新启动线程（可视为全量重开能力已具备）。
  - 现有 GUI 未使用 `RESTART`，导致重开逻辑没有被正确触发。
- `sanguosha/game.py`
  - 延时锦囊效果函数 `_effect_delayed_indulgence/_effect_delayed_supply_shortage/_effect_delayed_lightning` 在“打出时”调用 `_is_trick_countered(...)` 询问【无懈可击】。
  - `_resolve_judgment_area()` 当前直接判定并结算，不会在判定前再次走【无懈可击】流程。
  - 这与期望“延时锦囊在判定阶段触发时再询问无懈”不一致。

## Proposed Changes

### A. 统一确认按钮文案（GUI）
- 文件：`sanguosha/gui.py`
- What
  - 将战斗页主操作按钮文本从“确认出牌”改为“确认”。
- Why
  - 该按钮已承担出牌、弃牌提交、技能选牌提交三种确认动作，使用“确认”可避免误导。
- How
  - 在 `_build_battle_page()` 中仅改按钮 `text` 字段，不改 `command=self._confirm_play` 逻辑。
  - 不调整现有交互分支（`_confirm_play`）的行为，以降低回归风险。

### B. 修复“返回开始/返回开始页”重置行为
- 文件：`sanguosha/gui.py`
- What
  - 战斗页“返回开始”和结束页“返回开始页”都改为触发“真正重开会话”的统一入口，而非仅切换页面。
  - 回到开始页时清空界面选择残留（日志、选牌状态、弹窗、阶段提示），并确保下一次“开始对局”使用当前开始页选将重新建局。
- Why
  - 解决“返回开始后仍沿用上一把对局状态/武将分配”的问题。
  - 结束页按钮与战斗页按钮行为一致，避免用户路径差异导致体验不一致。
- How
  - 在 `_restart_game()` 中 dispatch `UIAction(type=ActionType.RESTART, text=self._general_var.get().strip() or None)`，然后执行现有 UI 清理并 `show("start")`。
  - 战斗页 footer 的“返回开始”按钮改为调用 `_restart_game`（或同等统一方法）而不是 `show("start")`。
  - 保留 `_start_game()` 使用 `ActionType.START`；若引擎存在活动线程，`START` 会被忽略，避免误触重复启动。
  - 可在 `_restart_game()` 末尾补充 `_last_request_kind = None` 以避免旧请求种类影响新局首次交互状态。

### C. 延时锦囊无懈时机改为判定阶段（乐/兵/闪）
- 文件：`sanguosha/game.py`
- What
  - 将【乐不思蜀】【兵粮寸断】【闪电】的【无懈可击】询问从“打出时”改为“进入目标角色判定阶段、逐张结算前”。
  - 三张牌全部按该规则调整（已确认包含【闪电】）。
- Why
  - 与用户指定规则一致：延时锦囊在判定阶段触发时才进行无懈响应判定。
- How
  - 在 `_effect_delayed_indulgence/_effect_delayed_supply_shortage/_effect_delayed_lightning` 中移除 `_is_trick_countered(...)` 判定，改为直接 `_place_delayed(...)`。
  - 在 `_resolve_judgment_area()` 的每张 `delayed` 结算开始前加入“判定阶段无懈检查”：
    - 若被无懈抵消：输出结算日志并将该延时牌置入弃牌堆，不执行判定牌翻开与后续效果。
    - 若未被抵消：按原逻辑翻判定牌并执行对应效果。
  - 为避免破坏非延时锦囊现有流程，不改 `_is_trick_countered(...)` 对即时锦囊的调用点。
  - 在判定阶段调用时的对抗双方可定义为“当前判定角色 vs 其对手”（1v1 下等价于双方轮流可无懈），保持与现有链式无懈逻辑一致。

### D. 测试补充与调整
- 文件：`tests/test_visual_engine.py`, `tests/test_core.py`
- What
  - 新增/调整测试覆盖 4 类改动：按钮文案、重开行为、结束页返回行为（通过 GUI 逻辑或引擎行为间接验证）、延时锦囊无懈时机迁移。
- Why
  - 本次变更涉及 GUI 事件绑定与核心规则结算，需通过回归测试锁定行为。
- How
  - `tests/test_visual_engine.py`
    - 增加“`RESTART` 后下一局人类武将按当前传入 text 生效、日志序号重置、旧 pending 输入不串局”的断言（现有相关测试可增强）。
  - `tests/test_core.py`
    - 新增延时锦囊时机用例：
      - 打出【乐不思蜀】/【兵粮寸断】/【闪电】时不立即消耗【无懈可击】输入。
      - 到目标判定阶段时出现【无懈可击】响应询问，且选择 `y` 后对应延时效果被抵消。
    - 保留并复用现有 `test_delayed_tricks_indulgence_supply_and_lightning`，按新时机更新断言。

## Assumptions & Decisions
- 已确认“延时无懈时机调整”范围包含三张：`乐不思蜀`、`兵粮寸断`、`闪电`。
- 已确认“返回开始”应立即重置对局（等价使用引擎 `RESTART` 能力），而非仅切页。
- 本计划不引入新的 `PendingRequest.kind`；仍沿用 `yesno` 文本协议承载无懈询问。
- 本计划不改 AI 无懈策略本身，仅改变延时锦囊触发时机。
- 本计划不涉及卡牌配置结构改造（`cards.py` 配置字段保持不变）。

## Verification Steps

### 自动化验证
- 执行：`pytest -q`
- 重点关注：
  - `tests/test_core.py` 中延时锦囊与无懈相关用例通过。
  - `tests/test_visual_engine.py` 中重开会话与 pending request 相关用例通过。

### 规则验证（核心）
- 场景 1：A 对 B 使用【乐不思蜀】后，立即不应询问无懈；到 B 判定阶段才询问是否打出【无懈可击】。
- 场景 2：A 对 B 使用【兵粮寸断】后同上，且无懈成功时 B 不应获得“跳过摸牌”标记。
- 场景 3：任意角色挂【闪电】后，进入其判定阶段才询问无懈；无懈成功时不触发闪电伤害/转移流程。

### GUI 手动验收
- 出牌区按钮显示为“确认”，在出牌/弃牌/技能选牌提交时均语义正确。
- 战斗页点击“返回开始”后，回到开始页并重置当前局；重新选择武将开始时，应按新选择重新开局且对手重新随机。
- 结束页点击“返回开始页”可正常返回并重置，而非无响应或只能退出。
