# plan_06_addchar

## Summary
当前武将池只有 4 名，难以支撑玩法与后续多人模式扩展。本计划新增 5 名《三国杀标准版》武将，并按现有架构继续区分主动/被动技能：主动技能在 GUI 中以按钮呈现、可在出牌阶段点击触发；被动技能通过事件触发与响应窗口完成交互。  
为提前适配多人模式，本计划统一“目标选择/选牌/判定替换/分牌”等交互协议为“按索引列出全场可选角色/牌”的通用格式，避免 1v1 写死对手或自己。

## Current State Analysis
- 武将与技能定义
  - [generals.py](file:///workspace/sanguosha/generals.py)：`GeneralDefinition/SkillDefinition`，现有 4 名武将（关羽/张飞/黄月英/华佗），`kind` 为 `active|passive`。
  - [skills.py](file:///workspace/sanguosha/skills.py)：目前仅实现 `武圣/青囊/集智` 相关逻辑。
  - [game.py](file:///workspace/sanguosha/game.py)：技能注册在 `_register_generals_skills()` 内通过大量 `elif skill.name == ...` 硬编码映射到处理函数；被动事件目前只有少量 `_trigger_event` 调用（如 `turn_start`、`after_use_trick`）。
- 交互协议
  - `visual_engine.py` 会根据 prompt 文本分类 `PendingRequest.kind`（如包含“技能选牌/技能目标/(y/n)”等）。
  - `gui.py` 已支持：
    - 手牌索引选择（出牌 / 技能选牌）
    - 弃牌多选确认（`discard_select`）
    - 模态弹窗（`yesno/skill_target_select/area_select/harvest_select`）
  - 当前目标选择已从“自己/对方”改为“索引列表”模式（如青囊），具备多人扩展雏形。
- 限制点（必须在本轮计划中一并补齐）
  - 技能注册硬编码不可扩展：新增 10 个技能会导致 `game.py` 越来越难维护。
  - 事件钩子不足：标准版技能普遍依赖“受到伤害/判定/摸牌阶段”等触发点，目前引擎缺少统一 damage/judge 事件与可插拔的判定替换机制。
  - GUI 主动技能按钮数量固定：当前界面只预留了固定数量按钮（需要改为按技能数动态渲染，避免新武将技能上限问题）。

## Proposed Changes

### A. 新增 5 名标准版武将（不依赖性别/势力系统）
选择技能机制相对独立、且与现有牌堆/规则耦合度可控的标准版武将，保证“原版一致”同时降低引擎改造风险：
1) 司马懿（3血）：反馈（被动）、鬼才（被动）  
2) 郭嘉（3血）：天妒（被动）、遗计（被动）  
3) 夏侯惇（4血）：刚烈（被动）  
4) 周瑜（3血）：英姿（被动）、反间（主动）  
5) 黄盖（4血）：苦肉（主动）

- 文件：`sanguosha/generals.py`
- How
  - 新增 5 个 `GeneralDefinition` 常量并加入 `GENERAL_POOL`。
  - 对每个技能补齐 `kind/trigger/description`，其中：
    - 主动：`反间/苦肉`（`kind="active"`, `trigger="play_phase"`）
    - 被动：其余（`kind="passive"`，触发点按标准版填写，如 `damage/judge/draw_phase` 等）

### B. 技能处理函数与注册机制改造（为多人/更多武将扩展）
- 文件：`sanguosha/skills.py`, `sanguosha/game.py`
- What
  - 将 `game.py::_register_generals_skills()` 从硬编码 `elif` 改为“技能注册表”驱动，新增武将只需在 `skills.py` 注册映射。
- How
  - 在 `skills.py` 建立：
    - `ACTIVE_SKILL_HANDLERS: dict[str, ActiveSkillHandler]`
    - `PASSIVE_SKILL_HANDLERS: dict[str, tuple[event_name, handler]]` 或 `PASSIVE_SKILL_REGISTRY: dict[str, list[(event, handler)]]`
  - 在 `game.py` 中：
    - `_register_generals_skills()` 遍历武将技能，按 `kind` 选择注册：
      - `active`：通过 `ACTIVE_SKILL_HANDLERS[skill.name]` 注册
      - `passive`：通过 `PASSIVE_SKILL_HANDLERS[skill.name]` 注册到对应事件
  - 保持现有 `register_active_skill/register_passive_skill` 接口不变，减少 UI/引擎改动面。

### C. 事件与判定管线补齐（支持伤害触发、判定替换、判定后取牌、分牌）
- 文件：`sanguosha/game.py`
- What
  - 引入可复用的伤害结算入口与判定入口，并在关键位置触发事件，使标准版技能可正确挂接且天然支持多人（按 `game.players` 遍历、按 `alive` 过滤）。
- How（建议实现结构）
  1. 伤害管线（为 反馈/遗计/刚烈 等提供统一触发点）
     - 新增 `Game._deal_damage(source: Player | None, victim: Player, amount: int, *, card: Card | None = None, reason: str = "")`
     - 在其中：
       - `victim.take_damage(amount)`
       - `_trigger_event("after_damage", victim=victim, source=source, amount=amount, card=card, reason=reason)`
       - 处理濒死/阵亡检查（必要时将现有散落的 `_check_death` 调整为从这里统一调用）
     - 替换现有各处 `take_damage(...)` 的直接调用（杀/决斗/南蛮/万箭/闪电等），确保技能触发不会漏。
  2. 判定入口（为 鬼才/天妒/刚烈/洛神类技能未来扩展提供基础）
     - 新增 `Game._run_judgment(judge_owner: Player, *, reason_card: Card | None = None, reason_text: str = "") -> Card | None`
     - 流程：
       - 抽取判定牌 `judge = draw_judge_card()`
       - `_trigger_event("before_judge", judge_owner=..., judge_card=judge, reason_card=..., reason_text=...)`
         - 允许“鬼才”用手牌替换：替换后原判定牌进入弃牌堆/或被“天妒”获取（按原版时序）
       - 结算判定结果（由调用方决定条件，如乐/兵/刚烈等）
       - `_trigger_event("after_judge", judge_owner=..., judge_card=final_judge, ...)`
         - “天妒”可将判定牌加入手牌（从而不进入弃牌堆）
       - 若未被获得，则默认 `discard(judge_card)`
  3. 判定区结算复用
     - `_resolve_judgment_area()` 改为对每张延时牌调用 `_run_judgment(...)`，并保持你在 optimize05 中的“判定阶段无懈”时机不变。

### D. 五名武将技能的“原版一致”实现要点（多人适配）
- 文件：`sanguosha/skills.py`, `sanguosha/game.py`
- 通用交互规范（多人适配核心）
  - 目标选择 prompt 统一输出：`技能目标-<技能名>：... [0]玩家A [1]玩家B ...`
  - 选牌 prompt 统一输出：`技能选牌-<技能名>：... [0]牌名 花色点数 ...`
  - 是否发动统一：`(y/n)`，触发 `yesno` 弹窗
  - 不再使用“对方/自己”写死逻辑，统一基于 `game.players` + `alive` 过滤生成候选。

1) 司马懿
  - 反馈（after_damage，victim==owner）
    - 若 `source` 存在且有可取区域：提示选择区域（复用现有 `area_select` 逻辑或新增“技能目标-反馈：选择区域 [h]手牌 [w]武器 ...”索引）
    - 手牌区仍保持随机抽取 1 张（多人也不透视手牌）
  - 鬼才（before_judge，任意判定）
    - 在判定牌翻开后询问 owner 是否发动（y/n）
    - 发动则选择一张手牌替换判定牌（技能选牌），替换牌作为最终判定牌参与结算

2) 郭嘉
  - 天妒（after_judge，judge_owner==owner）
    - 判定牌生效后可选择获得该判定牌（y/n）
  - 遗计（after_damage，victim==owner）
    - 每受到 1 点伤害触发一次：摸 2 张，然后可将其中任意张交给任意其他角色
    - 交牌交互：
      - 先选择要交出的牌索引集合（可复用 `弃牌选择：需弃X张...` 的多选协议，或新增 `技能选牌-遗计：选择要交出的牌编号（空格分隔，可为空）...`）
      - 对每张牌逐张选择目标（技能目标索引列表）

3) 夏侯惇
  - 刚烈（after_damage，victim==owner）
    - 是否发动（y/n）
    - 进行一次判定（复用 `_run_judgment`）
    - 若结果非红桃：令伤害来源选择“弃置2张牌或受到1点伤害”
      - 若来源手牌不足 2：直接受到 1 点伤害
      - 否则来源选择（y/n），选择弃牌则进入 `弃牌选择：需弃2张...`

4) 周瑜
  - 英姿（draw_phase）
    - 摸牌阶段额外摸 1 张（锁定）
    - 实现方式：在 `run_turn` 摸牌前计算 `draw_n = 2 + bonus`，bonus 由事件/技能决定
  - 反间（active，play_phase，限一次）
    - 选择目标（全场其他存活角色）
    - 目标选择花色（索引：♠/♥/♣/♦）
    - 发动者展示并交给目标 1 张手牌（技能选牌）
    - 若展示牌花色 ≠ 目标所选花色：目标受到 1 点伤害（走 `_deal_damage`）

5) 黄盖
  - 苦肉（active，play_phase）
    - 失去 1 点体力，然后摸 2 张
    - 伤害用 `_deal_damage(source=None, victim=owner, amount=1, reason="苦肉")` 或专用“失去体力”分支（标准版是失去体力非伤害，计划中明确区分：优先实现为 `lose_hp` 不触发“受到伤害类技能”）

### E. GUI：主动技能按钮与多人目标弹窗适配
- 文件：`sanguosha/gui.py`
- What
  - 主动技能按钮从“固定数量”改为“根据 `human.active_skills` 动态创建/回收”，避免后续新增武将技能数不一致。
  - 目标/花色等选择继续走现有 `skill_target_select` 弹窗：只要 prompt 以 `[idx]` 列表呈现即可复用（已满足多人）。
- How
  - 在 `_sync_skills()` 中按 `len(human.active_skills)` 动态维护按钮列表：
    - 不足则 `grid_remove()` / 销毁
    - 不够则追加创建
  - 保持 `command` 仍为 `s{idx}` 协议（与 `Game._human_play_phase` 兼容），并确保按钮在出牌阶段可点击。

## Assumptions & Decisions
- 本计划新增武将严格来自“标准版”，并优先选择不依赖“性别/势力/主公技”系统的武将与技能组合，以避免本轮必须引入阵营/身份框架。
- 多人适配的最低标准定义为：
  - 目标选择不写死“对方/自己”，而是基于 `game.players` 动态列出候选；
  - 技能的交互步骤全部可被复用到 N 人对局（即候选列表可扩展、顺序不依赖固定索引）。
- 伤害与“失去体力”在标准版语义不同：`苦肉` 采用“失去体力”实现，不触发“受到伤害后”类技能（如反馈/遗计/刚烈）。

## Verification Steps
### 自动化测试（新增/更新）
- `tests/test_core.py`
  - 反间：目标选花色 + 交牌 + 伤害结算（命中/未命中两条分支）
  - 苦肉：失去体力 + 摸 2（且不触发 after_damage 技能）
  - 刚烈：判定分支 + 弃2/受伤分支
  - 鬼才：替换判定牌影响判定结果
  - 天妒：判定牌生效后可获得，且不进弃牌堆
  - 遗计：受伤后摸 2 并可分配给其他角色（至少覆盖给 1 张给 1 人）
- `tests/test_visual_engine.py`
  - 新武将进入 `GENERAL_POOL` 后，快照可见其主动/被动技能列表（`active_skills/passive_skills`）

### 手动验收（GUI）
- 开始页可选择新增的 5 名武将进入对局。
- 周瑜、黄盖在出牌阶段出现对应主动技能按钮，点击后可完成技能交互并推进回合。
- 涉及“选择目标/选择花色/是否发动”的交互均弹出居中弹窗，且候选以索引列表形式展示（为多人模式复用）。
