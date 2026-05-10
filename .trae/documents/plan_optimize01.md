# plan_optimize01

## Summary
本计划用于优化当前“本地 1v1 三国杀（Tkinter GUI + Python 规则引擎）”，按你确认的策略分两期推进：
- 一期（稳定性与关键体验）：优先修复你点名问题（响应窗口位置、主动/被动技能可视化与可用性、决斗结算 bug、【杀】次数规则核对与修复），并做核心战斗链路 bug 扫描。
- 二期（规则深度扩展）：在“OL 当前标准口径”的约束下，扩展标准包锦囊与标准包 6 件装备（武器/防具/+1 马/-1 马），补齐结算、AI 与测试。
- 新增补充项（已纳入一期）：明确“出牌阶段结束后进入弃牌阶段，若手牌数大于当前体力值则弃到等于体力值”。

你已确认的关键决策：
- 交付节奏：分两期。
- 规则基线：OL 当前标准。
- 界面交互：响应与技能采用底部操作栏为主。
- bug 排查边界：限定核心战斗链（出牌/响应/结算/回合推进）。
- 一期验收取舍：先保证可玩性与规则正确，视觉美化后置。
- 二期范围：锦囊仅标准包；装备先做标准包 6 件。

## Current State Analysis
基于现有代码只读排查，当前状态如下：

### 已有基础
- 规则引擎核心在 `sanguosha/game.py`，已支持：
  - 基础牌：`杀/闪/桃`
  - 部分锦囊：`决斗/过河拆桥`
  - 装备：仅统一“武器”抽象（当前等价“可额外出杀”）
  - 主动技能注册与触发（CLI 路径可用）
- GUI 在 `sanguosha/gui.py` + `sanguosha/visual_engine.py`，已支持：
  - 手牌点击、确认/取消、响应窗口（目前是 `Toplevel` 弹窗）
  - AI 行为日志可见与短延时

### 与需求直接相关的现状问题
- 响应窗口位置问题：
  - 当前 `_ensure_response_window()` 使用 `Toplevel`，未显式定位，导致窗口可能在不理想位置（左上角）。
- 主动技能 GUI 不可用：
  - `game.py` 中存在主动技能调用路径（`_use_active_skill`），
  - 但 `gui.py` 当前无“技能按钮/技能区”与技能输入映射，导致 GUI 无法触发如关羽【武圣】。
- 决斗伤害疑似 bug（你反馈“敌方未掉血”）：
  - `game.py::_resolve_duel()` 逻辑表面正确，但需要复现链路（GUI/引擎输入桥接 + AI/玩家响应组合）确认是否存在特定分支遗漏。
- 【杀】次数规则：
  - 目前由 `sha_limit` + `actor.attack_limit()` 控制；
  - 需基于 OL 标准口径核对“默认 1 次、技能/武器改写次数”的完整约束。
- 弃牌阶段规则：
  - 当前 `game.py::_discard_to_limit()` 使用 `p.hand_limit()`，其默认可能按“体力上限/当前体力”的实现不够明确；
  - 需要按你要求收敛为“弃牌阶段手牌上限 = 当前体力值”并补测试覆盖。
- 装备/锦囊体系未精细化：
  - `cards.py` 仍是最小卡池配置，未包含标准包全锦囊与细化装备槽位、距离、时机。

### 现有测试覆盖
- `tests/test_core.py` 已覆盖基础牌与部分武将技能。
- `tests/test_visual_engine.py` 覆盖 visual_engine 输入桥接与回归。
- 缺口：尚无“主动技能 GUI 操作链”“决斗边界场景矩阵”“标准包锦囊/装备距离规则”系统化覆盖。

## Proposed Changes

## Phase 1：关键修复与可用性（先正确，再丰富）

### Phase 1 Work Breakdown（任务级）
1. P1-UI-01：底部响应栏替换主弹窗交互（保留弹窗兜底开关）。
2. P1-UI-02：技能面板分区（主动/被动）与主动技能按钮触发链路。
3. P1-RULE-01：决斗链路复现矩阵与修复（尤其“对方不出杀应掉血”）。
4. P1-RULE-02：【杀】次数口径收敛（默认/技能/装备/响应区分）。
5. P1-RULE-03：弃牌阶段规则收敛（按当前体力值弃牌）。
6. P1-QA-01：核心战斗链 bug 扫描（只限出牌/响应/结算/回合推进）。
7. P1-QA-02：新增自动化用例与回归脚本，形成一期验收基线。

### 1) 底部响应与技能操作栏（替代主弹窗依赖）
- 文件：`sanguosha/gui.py`, `sanguosha/ui_protocol.py`, `sanguosha/visual_engine.py`
- What
  - 在对局底部增加“响应操作区”（是/否按钮、当前提示文本）。
  - 增加“技能区”并区分：
    - 被动技能：只展示，不可点击（例如咆哮）。
    - 主动技能：独立按钮，可点击触发（例如武圣）。
  - 保留弹窗为兼容兜底（可选开关），默认走底部栏。
- Why
  - 修复响应窗口位置与操作成本问题。
  - 打通 GUI 主动技能使用能力。
- How
  - 在 `ui_protocol.py` 快照中补充可渲染技能模型（技能名、类型、可用性、按钮命令标识）。
  - 在 `visual_engine.py` 提供“技能触发输入映射”（例如将按钮行为转为 `s0` 风格输入或新的 `UIAction`）。
  - 在 `gui.py` 渲染技能面板与底部响应区，禁用/启用规则依据 `pending_request` 和当前回合身份。
  - 响应区交互优先级：若 `pending_request.kind == "yesno"`，底部响应区始终可见且优先抢占焦点。

### 2) 决斗结算问题复现与修复
- 文件：`sanguosha/game.py`, `tests/test_core.py`, `tests/test_visual_engine.py`
- What
  - 新增“敌方出决斗 -> 我方出杀 -> 敌方不出杀 -> 敌方掉血”的强约束测试。
  - 若复现失败，修复 `_resolve_duel()` 或输入桥接时序导致的问题。
- Why
  - 修复你明确发现的规则错误，避免实战误判。
- How
  - 先在引擎层（非 GUI）构建最小复现测试；
  - 再补 visual_engine 脚本化 E2E 测试确认 GUI 链路一致性。
  - 增加日志断言：明确记录“谁未出杀、谁受伤、剩余体力”三要素，便于回归定位。

### 3) 【杀】次数规则按 OL 口径核对并收敛
- 文件：`sanguosha/game.py`, `sanguosha/player.py`, `tests/test_core.py`
- What
  - 明确默认每回合出杀上限 = 1；
  - 仅通过技能/装备效果改写上限；
  - 将边界场景（武圣当杀、决斗中的杀响应不计入主动出杀上限）写入测试。
- Why
  - 防止“看起来能出无限杀”或“该能出却被禁止”。
- How
  - 收敛 `attack_limit()` 与 `sha_used_this_turn` 的定义；
  - 增加规则注释与测试矩阵。

### 4) 弃牌阶段规则收敛（新增）
- 文件：`sanguosha/game.py`, `sanguosha/player.py`, `tests/test_core.py`, `tests/test_visual_engine.py`
- What
  - 明确“结束出牌阶段后进入弃牌阶段”；
  - 手牌数若大于当前体力值，需弃到等于当前体力值。
- Why
  - 这是你新增明确要求，且影响回合平衡与 AI 手牌收益。
- How
  - 在 `run_turn()` 阶段输出中显式记录“弃牌阶段”；
  - 调整 `_discard_to_limit()` 使用当前体力作为上限（或统一 `hand_limit` 语义为当前体力）；
  - 新增测试：受伤状态下超手牌必须弃置；满血状态下上限恢复。

### 5) 核心战斗链 bug 扫描（限定范围）
- 文件：`sanguosha/game.py`, `sanguosha/visual_engine.py`, `tests/test_core.py`, `tests/test_visual_engine.py`
- What
  - 仅扫描：出牌合法性、响应时机、伤害/濒死/死亡、回合推进。
  - 对发现问题分类：P0 阻断、P1 规则错、P2 可优化。
- Why
  - 满足“再找 bug”但不扩到无关模块。
- How
  - 以测试先行方式记录每个问题（先 failing test，再修复）。

## Phase 2：标准包锦囊 + 标准包 6 件装备

### Phase 2 Work Breakdown（任务级）
1. P2-EQUIP-01：装备槽模型重构（武器/防具/+1马/-1马）。
2. P2-EQUIP-02：距离系统接入（基础距离、马修正、武器距离）。
3. P2-EQUIP-03：标准包 6 件装备逐件落地与测试。
4. P2-TRICK-01：标准包普通锦囊接入（目标、时机、响应）。
5. P2-TRICK-02：标准包延时锦囊接入（判定区与判定流程）。
6. P2-AI-01：AI 对新增牌的决策权重与最小可用策略。
7. P2-UI-01：GUI 对新增牌型/目标约束的提示与禁用逻辑。
8. P2-QA-01：规则矩阵测试与多局回归。

### 5) 装备系统精细化（标准包 6 件）
- 文件：`sanguosha/cards.py`, `sanguosha/player.py`, `sanguosha/game.py`, `tests/test_core.py`
- What
  - 从“单一 weapon 字段”升级为多装备槽：武器、防具、+1 马、-1 马。
  - 先实现标准包 6 件装备（按 OL 口径定义效果与触发）。
  - 引入距离计算：基础距离、+1/-1 马修正、武器攻击距离。
- Why
  - 支撑“装备不再只等于多一张杀”的需求。
- How
  - 在 `cards.py` 配置层增加装备子类型与效果类型；
  - 在 `player.py` 增加槽位与距离相关属性；
  - 在 `game.py` 新增距离校验、目标合法性校验、装备效果触发。
  - 每件装备单独建立 effect handler，避免“装备通用逻辑过度分支”。

### 6) 标准包锦囊完整接入（不含扩展包）
- 文件：`sanguosha/cards.py`, `sanguosha/game.py`, `tests/test_core.py`
- What
  - 扩展标准包普通锦囊 + 延时锦囊。
  - 建立统一结算钩子：指定目标、可响应窗口、判定与结算顺序。
- Why
  - 满足“锦囊精细化”并与 OL 标准口径对齐。
- How
  - 延续现有 `effect_registry + play_validator_registry` 机制；
  - 为每张锦囊补独立 effect handler 与测试用例；
  - 对延时锦囊引入判定区与回合开始判定流程。
  - 增加“不可目标化/距离不足/无合法目标”的统一失败提示。

### 7) AI 与 GUI 配套补全
- 文件：`sanguosha/game.py`, `sanguosha/gui.py`, `sanguosha/visual_engine.py`, `tests/test_visual_engine.py`
- What
  - AI 新卡识别与出牌权重策略更新（装备收益、锦囊威胁）。
  - GUI 操作区适配新增装备/锦囊目标选择与提示。
- Why
  - 规则扩展后保持可玩性，不出现“卡在不会用牌”的 AI。
- How
  - 分层实现：先“可用”策略，再细调权重。

## Assumptions & Decisions
- 以“OL 当前标准口径”为规则基线；若与当前代码冲突，以规则正确优先。
- 本计划不覆盖联网、多人、身份模式。
- 一期不做视觉皮肤级美化，仅做可用性优化。
- 二期仅覆盖标准包，不引入扩展包。
- 仅进行核心战斗链 bug 扫描，不做全项目性能重构。

## Verification Steps

### 一期验收
- 自动化测试：
  - `pytest -q` 全绿。
  - 新增测试必须覆盖：
    - GUI 主动技能触发链（至少武圣）。
    - 敌方决斗场景下敌方掉血复现与修复。
    - 【杀】次数边界（默认、咆哮、武圣、决斗响应）。
    - 弃牌阶段边界（受伤手牌超限弃置、回合后手牌不高于当前体力）。
- 手动验收：
  - GUI 中响应区固定在底部操作栏，单手可达，不再出现难点弹窗操作。
  - GUI 可区分主动/被动技能；主动技能可点击并成功结算。
  - 回合日志中可见“弃牌阶段”，且弃牌结果与体力值一致。

### 二期验收
- 自动化测试：
  - 为每个新增标准锦囊与 6 件装备提供至少 1 个正向结算测试 + 1 个边界测试。
  - 新增距离与目标合法性测试矩阵（至少：无马、有+1马、有-1马、武器距离变化）。
- 手动验收：
  - 实战可完成多局，未出现回合卡死、响应死锁、结算不推进。
  - AI 能在新增卡池下完成基本可用决策（不频繁无效操作）。

## Deliverables（执行产物清单）
- 代码变更：`sanguosha/game.py`, `sanguosha/player.py`, `sanguosha/cards.py`, `sanguosha/gui.py`, `sanguosha/ui_protocol.py`, `sanguosha/visual_engine.py`, `sanguosha/skills.py`（按实际需要）。
- 测试变更：`tests/test_core.py`, `tests/test_visual_engine.py`, `tests/test_main.py`（按实际需要）。
- 文档变更：`KNOWN_LIMITATIONS.md` 更新新增规则与已知限制。
