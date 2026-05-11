# plan_08_debug

## Summary
本计划修复“多目标锦囊的无懈可击作用范围”错误：对【五谷丰登】【桃园结义】这类多目标锦囊，【无懈可击】只能让锦囊对“当前结算的一个目标”生效/失效，而不能一次性抵消整张锦囊对所有人的效果。  
修复后将补充回归测试，覆盖“五谷丰登每人选牌前单独询问无懈、无懈对无懈、只影响单个目标”的关键分支。

## Current State Analysis
- 代码位置
  - [game.py](file:///workspace/sanguosha/game.py)：
    - `_resolve_nullify_chain(...)` 已实现“从起点逆时针轮询 + 无懈对无懈”的链式反转能力。
    - `_effect_peach_garden(...)` 在结算开始时调用一次 `_is_trick_countered(actor, target, card)`，导致“桃园结义被无懈时整张锦囊直接返回”，对所有目标整体失效。
    - `_effect_harvest(...)` 同样在结算开始时调用一次 `_is_trick_countered(actor, target, card)`，导致“五谷丰登被无懈时整张锦囊直接返回”，从而错误地取消所有目标。
    - 但多目标锦囊按规则应当：以使用者为起点逆时针逐个目标结算，每个目标结算前各自进行一轮无懈询问（并可无懈对无懈），无懈只影响当前目标这一段结算。
- 根因
  - 把多目标锦囊当成“单目标锦囊”在开始阶段进行了一次全局 `_is_trick_countered(...)` 判定，导致无懈作用域扩大为“整张锦囊”。

## Proposed Changes

### A. 多目标锦囊移除“全局无懈”
- 文件：`sanguosha/game.py`
- What
  - 在 `_effect_peach_garden`、`_effect_harvest` 中移除开头的 `_is_trick_countered(actor, target, card)`。
- Why
  - 多目标锦囊不应在整体层面被无懈一次性抵消，应在“每个目标结算前”单独询问无懈。

### B. 桃园结义按目标逐个结算，并为每个目标单独跑无懈链
- 文件：`sanguosha/game.py`
- How
  - 定义目标顺序：`targets = _iter_ccw_alive(actor)`（包含使用者自身，起点为使用者，逆时针一圈）。
  - 对每个 `p in targets`：
    - 调用 `_resolve_nullify_chain(starter=actor, trick_user=actor, trick_name=card.name, target=p, effective=True)`
    - 若返回 `effective=True`：对该 `p` 执行 `heal(1)`
    - 若返回 `effective=False`：跳过该 `p` 的回复（只影响该一个目标）
  - 保持“无懈对无懈”由 `_resolve_nullify_chain` 内部多轮反转实现（每轮从使用者起点逆时针询问）。

### C. 五谷丰登按目标逐个结算：每人选牌前跑一轮无懈链（仅影响该人本次选牌）
- 文件：`sanguosha/game.py`
- How
  - 保持现有：亮牌数 = 存活人数 N，顺序 = `_iter_ccw_alive(actor)`，每人从池中获得 1 张。
  - 对每个 `picker` 在进入选牌前：
    - 调用 `_resolve_nullify_chain(starter=actor, trick_user=actor, trick_name=card.name, target=picker, effective=True)`
    - 若结果 `effective=False`：该 `picker` 本次“跳过选牌”（不获得牌），直接轮到下一个。
    - 若 `effective=True`：正常选牌/最后一张自动获得特例仍保留。
  - 移除或改造 `_is_harvest_pick_skipped`：
    - 以 `_resolve_nullify_chain` 为唯一无懈链实现，避免出现两套不同提示语/判定逻辑导致行为不一致。

### D. 无懈提示语与规则一致性
- 文件：`sanguosha/game.py`
- What
  - 多目标锦囊在每个目标结算前的询问句应与现有 `_resolve_nullify_chain` 文案一致：
    - `"{使用者} 的 {锦囊名} 锦囊即将对 {目标} 生效/失效，是否使用【无懈可击】使其失效/生效？(y/n): "`
- Why
  - 保证玩家理解“当前无懈只作用于这个目标”，并与身份系统后续多人扩展保持一致。

## Assumptions & Decisions
- 本次修复范围严格限定在多目标锦囊【五谷丰登】【桃园结义】；【决斗】等单目标锦囊逻辑不改。
- 1v1 下依旧会体现“多目标按顺序逐个结算”的模型（等价为对两个目标逐个结算），为多人扩展打底。
- “逆时针”顺序继续沿用当前项目的 `_iter_ccw_alive(actor)` 定义。

## Verification Steps
### 自动化测试（新增/更新）
- 文件：`tests/test_core.py`
- 新增用例建议：
  1. 桃园结义单目标无懈不影响其他目标
     - A、B 都受伤；A 使用【桃园结义】；B 对自己那一次结算打出无懈：断言 A 回复、B 不回复。
  2. 五谷丰登无懈只跳过一个人的选牌
     - A 使用【五谷丰登】亮 2 张；A 正常拿 1 张；B 在轮到自己前被无懈导致跳过：断言 B 未获得牌，剩余牌进入弃牌堆。
  3. 无懈对无懈反转（多目标场景）
     - 在某目标结算前，B 无懈使失效，A 再无懈使生效：断言该目标最终仍生效。

### 回归验证
- 运行：`pytest -q`
- 手动（GUI）验证：
  - 五谷丰登中，对某个角色使用无懈只会让该角色跳过本次选牌，不影响其他角色的选牌与结算。

