# plan_optimize03

## Summary
本计划聚焦你提出的 3 个高优先问题，目标是在不扩展新玩法的前提下恢复 GUI 可用性与对局随机性：
- 修复华佗【青囊】后 GUI 卡死（按钮全不可点击、重开后仍不可交互）。
- 修复选将不随机与“重开无法重新选将”的问题。
- 修复牌堆每局固定的问题，确保每局开始与洗牌时都随机化。

成功标准：
- 使用【青囊】后可继续完成当前回合交互，且重开后交互状态正常。
- 玩家选非关羽时，AI 不再固定关羽；点击重开后可按新选择生效。
- 连续开局同配置下牌堆顺序不同；耗尽后洗牌顺序也不同。

## Current State Analysis
基于当前代码只读核查，问题来源明确如下：

### 1) 【青囊】后 GUI 卡死
- `skills.py` 中 `qingnang_active()` 会触发两类额外输入：
  - `技能选牌-青囊...`
  - `技能目标-青囊...`
- `visual_engine.py` 已把这两类 prompt 分类为：
  - `skill_card_select`
  - `skill_target_select`
- 但 `gui.py` 的 `_sync_interactions()` 只对 `play/yesno/discard_select/area_select/harvest_select` 开放交互，未对 `skill_card_select/skill_target_select` 提供任何可点击提交路径，导致界面进入“等待输入但无可用按钮”的死锁状态。

### 2) 选将不随机与重开武将失效
- `visual_engine.py` 初始化时将 `_selected_human_general` 固定为 `"关羽"`，且 `_run_game()` 中人类直接使用该字段、AI 设为 `None` 交给引擎随机。
- 现有表现“我方非关羽时敌方必关羽”，高概率来自“玩家配置没有稳定更新到新会话”与“重开流程复用旧状态”的组合（`START/RESTART` 都可能沿用旧字段）。
- `gui.py` 重开按钮只调用 `RESTART`，但没有重置/确认“当前下拉值 -> 引擎会话参数”这一时序。

### 3) 牌堆固定
- `VisualEngineConfig.seed` 当前固定为 `1`，并在 `_run_game()` 中每局传给 `Game(seed=...)`。
- `Game.__init__()` 用该 seed 构建 `Random(seed)`，并将相同 seed 传给 `build_deck(seed=seed, ...)`，导致每局初始牌堆顺序一致。
- `draw_cards()/draw_judge_card()` 的洗牌逻辑使用同一个 `self.rng`，若每局 seed 固定，洗回牌堆顺序也可重复。

## Proposed Changes

### A. 修复【青囊】输入链与 GUI 交互死锁
- 文件：`sanguosha/gui.py`, `sanguosha/visual_engine.py`
- What
  - 给 `skill_card_select`、`skill_target_select` 增加明确的 GUI 交互入口与提交逻辑。
  - 在这些请求期间启用“手牌点击+确认”或“目标按钮（自己/对方）”。
- How
  - 在 `_sync_interactions()` 中新增 `can_skill_card_select/can_skill_target_select` 状态。
  - `skill_card_select`：
    - 复用手牌按钮选择索引；
    - “确认”按钮提交所选编号到 `SUBMIT_TEXT`。
  - `skill_target_select`：
    - 新增两个按钮：`目标[0]自己`、`目标[1]对方`（或复用区域条），点击即提交 `0/1`。
  - 若 `pending_request.kind` 不匹配，统一禁用上述按钮，避免误提交。
  - 明确“请求切换时清空旧选择态”，防止上个阶段残留。
- Why
  - 根治“技能触发后等待输入但 GUI 无输入通道”的阻塞。

### B. 修复选将随机与重开选将不生效
- 文件：`sanguosha/visual_engine.py`, `sanguosha/gui.py`
- What
  - 去掉 `_selected_human_general` 的硬编码默认值，改为“由开始页选择值驱动”。
  - 每次 `START/RESTART` 均以当前 GUI 下拉值覆盖本局参数。
  - 会话重置时清理旧输入队列与 pending request，避免上一局 prompt 污染新局。
- How
  - `LocalVisualEngine`：
    - `_selected_human_general` 默认 `None`；
    - `START/RESTART` 统一先标准化 `action.text`（空值时回退为开始页默认项而非上局缓存）。
  - `gui.py`：
    - `开始对局`、`再来一局` 都传当前下拉武将值；
    - 重开后返回开始页或保留开始页可见选将状态（两者择一，建议返回开始页以强调“重新选将”）。
  - 保持 AI 为“从剩余武将池随机”。
- Why
  - 彻底解决“敌方似乎总固定/重开无法重新选将”的状态串局。

### C. 牌堆与洗牌随机化
- 文件：`sanguosha/visual_engine.py`, `sanguosha/game.py`, `sanguosha/cards.py`（最小改动）
- What
  - 默认每局使用随机 seed（不固定 1）。
  - 仅在测试模式下保留可控 seed（用于稳定测试）。
  - 保证抽空后洗入弃牌堆时随机化。
- How
  - `VisualEngineConfig.seed` 默认改为 `None`。
  - `_run_game()` 传递该 seed 到 `Game`；`None` 时使用系统随机。
  - `Game` 内继续使用 `self.rng.shuffle` 进行洗牌；当 seed 为 `None` 时每局都不固定。
  - 如需保留可复现实验，测试中显式传 seed。
- Why
  - 满足“每局开始与每次洗牌随机化”的对局预期。

## Assumptions & Decisions
- 本计划只修复你明确列出的 3 项问题，不额外改动规则或新增玩法。
- 仍以 GUI 为主路径，CLI 行为不作为本轮重点。
- “敌方随机”定义为：在剩余可选武将中等概率随机，不强制均匀长期分布统计。
- 随机化改动允许测试中通过显式 seed 保持可重复性。

## Verification Steps

### 自动化验证
- 新增/更新 `tests/test_visual_engine.py`：
  - `青囊`触发后出现 `skill_card_select -> skill_target_select`，并能通过 GUI action 完成提交，不进入卡死。
  - `RESTART` 后 pending_request 清空、按钮状态恢复、可进入新对局交互。
  - 玩家切换武将后，新局快照中的 `human.general` 与选择一致。
  - 连续两局在 `seed=None` 下初始手牌/抽牌序列非恒定一致（统计式断言，避免偶然冲突可多轮比对）。
- 更新 `tests/test_core.py`（如需要）：
  - AI 选将来自剩余池而非固定值。

### 手动验收（GUI）
- 用华佗发动【青囊】：
  - 能选择弃置牌；
  - 能选择治疗目标；
  - 结算后本回合继续可点击交互。
- 点击“再来一局”后：
  - 可以重新选将并生效；
  - 不再出现“按钮都不可点”。
- 连续开 3~5 局观察：
  - 开局手牌与前几轮摸牌顺序有明显变化；
  - 牌堆耗尽重洗后顺序不固定。
