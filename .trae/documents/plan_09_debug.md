# plan_09_debug

## Summary
本计划修复 5 个近期回归问题：决斗结算出现“双方都掉血”的异常、无中生有的无懈提示目标错误、鬼才替换判定牌后缺少“新判定牌播报”、GUI 出现右侧/下侧大块空白且窗口尺寸体验不佳、以及战斗结束自动跳转结束页导致无法复盘日志。  
整体目标是：规则层面修复结算与提示语准确性，UI 层面优化布局与结束态交互，并补齐回归测试以防再次复发。

## Current State Analysis
### 1) 决斗伤害异常
- 相关代码：
  - [game.py](file:///workspace/sanguosha/game.py) 的 `_effect_duel()` / `_resolve_duel()`。
- 现象描述为“敌方决斗→我方出杀→敌方没出杀→按理只敌方受伤，但我方也受了不明伤害”。
- 初步判断：需要通过可复现用例定位“额外伤害”的来源，可能来自：
  - `_deal_damage()` 触发的 `after_damage` 技能链（例如刚烈/反馈/遗计）对另一方造成了额外伤害；
  - 或决斗流程中的“当前出杀者/受伤者”引用混乱（例如 `current/other` 交换后伤害目标不一致）；
  - 或 UI/日志误读（实际是失去体力/濒死救援/其他结算导致 HP 变化但日志不清晰）。

### 2) 无中生有目标提示错误
- 相关代码：
  - [gui.py](file:///workspace/sanguosha/gui.py) `_target_for_card()` 认为“无中生有”目标是 self。
  - 但 [game.py](file:///workspace/sanguosha/game.py) 的 `_human_play_phase()` 始终把 `target` 传成 `other_player(actor)`，导致 `play_card(actor, target, idx)` 的 `target` 在规则层仍是“电脑”，从而无懈提示用错目标名字。
- 根因：规则层缺少“根据牌本身决定实际目标”的统一逻辑（当前依赖 UI/调用方传入 target）。

### 3) 鬼才替换判定牌后未播报新判定牌
- 相关代码：
  - [game.py](file:///workspace/sanguosha/game.py) `_run_judgment()` 目前会播报初始判定牌与“司马懿获得原判定牌”，但不会播报“替换后的最终判定牌是什么”。
  - 导致后续技能（如郭嘉【天妒】）触发时，玩家无法在日志中明确看到最终判定牌。

### 4) UI 右侧/下侧大块空白 + 窗口尺寸体验
- 相关代码：
  - [gui.py](file:///workspace/sanguosha/gui.py) 当前在 `__init__` 强制 `root.minsize(980,720)` 与 `root.geometry("980x720")`。
- 推断：
  - 若窗口被固定在较大尺寸，而内容区域没有随窗口自适应铺满，会出现显著空白。
  - 同时固定尺寸会让用户无法把窗口调小以消除空白（即使可以放大也会观感不佳）。

### 5) 战斗结束自动跳转结束页
- 相关代码：
  - [gui.py](file:///workspace/sanguosha/gui.py) `_tick()` 检测到 `snapshot.winner` 会自动 `show("end")`。
- 问题：用户无法停留在对战页观察播报栏最后几条结算日志。

## Proposed Changes
### A. 修复决斗额外伤害（以可复现用例驱动）
- 文件：`sanguosha/game.py`, `tests/test_core.py`
- 方案：
  1. 先新增测试用例复现“敌方决斗，玩家出杀，敌方不出杀，玩家不应掉血”的路径（严格断言双方 HP 变化与日志关键字）。
  2. 若复现后确认是技能链导致的额外伤害：
     - 补齐日志标记（例如在 `_deal_damage` 输出 reason/来源），或在触发处输出更明确的结算信息；
     - 或修正“决斗结算结束后不应额外触发的伤害逻辑”（例如错误复用 `resolve_sha` / 错误触发）。
  3. 若复现后发现是 `_resolve_duel` 逻辑本身错误：
     - 校验 `current/other` 交换、以及 `_deal_damage(other,current)` 的参数含义是否始终正确；
     - 保证只有“未能出杀的一方”受到 1 点伤害。

### B. 统一规则层“实际目标解析”，修复无中生有无懈提示目标错误
- 文件：`sanguosha/game.py`
- 方案：
  - 在 `play_card(actor, target, hand_index)` 内增加一个“实际目标决策”步骤，例如：
    - `_resolve_effective_target(actor, target, card_name) -> Player`
  - 对自目标牌（至少覆盖：无中生有、桃、装备牌、闪电、五谷丰登、桃园结义）统一返回 `actor` 作为 `effective_target`。
  - 之后所有使用 `target` 的校验/无懈提示/效果处理都使用 `effective_target`（保证 prompt 中目标名字正确）。
  - 该改造应保持 CLI 与 GUI 行为一致，不再依赖 UI 传入正确 target。

### C. 鬼才替换后追加“新判定牌播报”
- 文件：`sanguosha/game.py`
- 方案：
  - 在 `_run_judgment` 中，当 `before_judge` 返回替换牌并完成替换后：
    - 立即输出一条日志：`[判定] {judge_owner} 判定牌被替换为：{新牌}`（使用统一格式化函数）
  - 确保该日志发生在 `after_judge`（天妒等）触发前。

### D. UI 空白与窗口尺寸优化
- 文件：`sanguosha/gui.py`
- 方案（最小改动优先）：
  - 去掉强制 `root.geometry("980x720")`，仅保留合理的 `minsize` 或改为更小的默认尺寸（例如 900x650），并显式 `root.resizable(True, True)`。
  - 确认 battle 页 `grid_rowconfigure/grid_columnconfigure` 的 weight 设置能让日志区与手牌区随窗口变化自适应填充，减少空白。

### E. 战斗结束不跳转结束页：在对战页增加“返回主界面/退出游戏”
- 文件：`sanguosha/gui.py`
- 方案：
  - `_tick()` 不再在 `winner != None` 时自动 `show("end")`。
  - battle 页 footer 增加两按钮：
    - “返回主界面”：复用现有 `_restart_game`（回到 start）
    - “退出游戏”：`root.destroy`
  - 当 `winner != None` 时：
    - 禁用出牌相关按钮（确认/取消/结束阶段/技能按钮/手牌按钮），避免误操作；
    - 在 battle 页顶部或状态栏增加“对局结束，胜者：xx”的固定提示，方便用户停留复盘日志。
  - end 页可以保留但不自动跳转（后续可再决定是否删除）。

## Assumptions & Decisions
- 目标解析的最小覆盖集合为：无中生有/桃/装备/闪电/五谷丰登/桃园结义；后续可按牌表扩展。
- UI 优化优先保证“可手动缩放窗口 + 内容区域可自适应”，不追求重新设计视觉风格。
- 战斗结束后仍留在 battle 页，用户可自行点击“返回主界面/退出游戏”，不再强制跳转 end 页。

## Verification Steps
### 自动化测试
- 新增/更新 `tests/test_core.py`：
  - 决斗回归：敌方决斗、我方出杀、敌方不出杀 → 仅敌方掉血。
  - 目标解析回归：无中生有的无懈询问 prompt 中目标应为使用者本人而非电脑。
  - 判定播报回归：鬼才替换判定牌后日志出现“被替换为：xx”且在天妒询问/结算前出现。
- 运行：`pytest -q`

### 手动验证（GUI）
- 调整窗口大小时 UI 能自适应，不出现明显不可控的右侧/下侧大块空白。
- 对局结束后停留在 battle 页，可查看日志，并可点击“返回主界面/退出游戏”。

