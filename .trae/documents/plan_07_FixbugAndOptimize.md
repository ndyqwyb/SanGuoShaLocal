# plan_07_FixbugAndOptimize

## Summary
本计划修复并优化新增武将/技能带来的交互与日志问题，重点包括：判定展示信息不完整、【遗计】/【鬼才】交互时机与结算不符合预期、技能选牌与弃牌缺少清晰提示、开始页窗口尺寸与布局问题、以及新增“查看敌方技能说明”的入口。  
整体目标是让所有“需要玩家输入”的场景在 GUI 中都能稳定可操作（不受当前回合归属影响），并且提示信息足够明确，避免出现“按钮全灰只能重开”的死锁体验。

## Current State Analysis
1) 判定牌显示不完整
- [game.py](file:///workspace/sanguosha/game.py) 中判定相关输出目前只显示花色/点数：
  - 判定区结算：`self.output(f"{actor.name} 判定【{delayed.name}】：{judge.suit} {judge.rank}")`
  - 八卦阵：`self.output(f"[响应] {p.name} 的【八卦阵】判定：{judge.suit} {judge.rank}")`
  - `run_judgment/_run_judgment` 返回 `Card`，但未统一格式化输出牌名。

2) 【遗计】结算顺序与提示问题
- [skills.py](file:///workspace/sanguosha/skills.py) `yiji_after_damage` 当前先 `draw_cards(owner, 2)`，只输出“摸2张牌”，不会展示摸到的具体两张牌。
- `yiji_after_damage` 的交互使用多段输入（是否发动/是否给牌/技能选牌/技能目标），理论上能触发 `visual_engine.py` 的 `skill_card_select/skill_target_select/yesno` 分类，但实际 GUI 会因“当前回合不是玩家”而禁用按钮导致卡死（见第 3 点）。

3) 【遗计】（以及类似“非自己出牌阶段的玩家输入”）会让 GUI 按钮全灰
- [gui.py](file:///workspace/sanguosha/gui.py) `_sync_interactions` 对 `discard_select/skill_card_select` 的可点击条件包含 `snapshot.current_player == human_name`：
  - 这会导致“在电脑回合触发、但需要玩家响应”的输入（如：玩家受伤触发遗计、电脑夏侯惇刚烈要求玩家弃牌等）被错误禁用，出现“无法点击只能重开”的现象。
- 当前 `PendingRequest` 未携带“当前请求归属玩家”，GUI 无法通过快照字段判断该输入是否属于人类玩家；但由于 `input()` 只会对人类阻塞，直接放开限制是安全的。

4) 【鬼才】询问时机与判定牌展示
- [skills.py](file:///workspace/sanguosha/skills.py) `guicai_before_judge` 在询问“是否发动鬼才”之前，没有先展示当前判定牌是什么。
- [game.py](file:///workspace/sanguosha/game.py) `_run_judgment` 在触发 `before_judge` 前没有统一输出“判定牌翻开结果”。

5) 【鬼才】替换后“获得判定牌”未实现
- 当前 `_run_judgment` 逻辑在替换时会 `discard(final)`，并将替换牌作为最终判定牌；不会把原判定牌交给司马懿。
- 本需求按你的描述调整为：发动鬼才后，替换牌成为判定牌，且司马懿获得原判定牌。

6) 技能选牌缺少“你现在要做什么”的提示
- `visual_engine.py` 只做输入类型分类，不会把 prompt 显示到 GUI 主区域；GUI 当前主要依靠 `_hint_var` 的固定文案（如“技能选牌：请先选择一张手牌”），但：
  - 文案不包含技能名/目的，玩家可能不知道“要选来做什么”。
  - 多个技能共用 `skill_card_select`，需要更精确的提示文本。
- 已确认涉及技能：武圣/青囊/鬼才/反间，以及“刚烈要求玩家弃置”这一类输入。

7) 弃牌阶段缺少明确提示
- 虽然 `game.py` 的 prompt 已包含 `弃牌选择：需弃X张...`，GUI 只有在点击牌后才显示“还需选择 X 张”，进入阶段时缺少醒目的提示。

8) 选将界面调整窗口高度会影响对局界面
- [gui.py](file:///workspace/sanguosha/gui.py) `show()` 仅切换页面，不会根据页面重新设置窗口最小尺寸/推荐尺寸。
- `start` 页布局较小，用户在选将页调整 y 轴后，进入 battle 页窗口仍保持同样高度，导致对局界面显示不佳。

9) 缺少查看敌方技能入口
- battle 页 `enemy_box` 仅展示对方名称/血量/装备等信息，没有“查看技能与描述”的按钮。
- 技能描述来源可直接复用 `GENERAL_POOL` 中的 `SkillDefinition.description`。

## Proposed Changes

### A. 判定显示补齐牌名（全判定统一格式）
- 文件：`sanguosha/game.py`
- 改动点
  - 将所有判定相关输出统一为：`牌名 + 花色符号 + 点数`，例如：`杀 ♠7`。
  - 覆盖：
    - 判定区结算（乐/兵/闪电）
    - 八卦阵判定
    - 其他未来通过 `run_judgment` 引入的判定点
- 实现方式
  - 新增一个内部格式化函数（如 `_format_card_short(card)`），在输出中复用，避免散落拼接导致漏改。

### B. 【遗计】结算顺序与可见性优化
- 文件：`sanguosha/skills.py`
- 改动点
  1. 摸牌后先展示摸到的两张牌，再询问是否分配给他人：
     - 具体做法：在遗计里“逐张抽牌”并记录两张 `Card`，输出 `"[信息] 遗计摸到：[0]xxx [1]yyy"`。
  2. 分配交互保持“索引选牌 + 索引选目标”：
     - 选牌仍走 `技能选牌-遗计：...`
     - 选目标仍走 `技能目标-遗计：...`

### C. 修复“非自己回合的输入导致按钮全灰”（遗计/刚烈等卡死根因）
- 文件：`sanguosha/gui.py`
- 改动点
  - `_sync_interactions` 中：
    - `discard_select`、`skill_card_select` 不再依赖 `snapshot.current_player == human_name`，只要 `pending_request.kind` 匹配就允许点击手牌与确认/取消。
    - `yesno/skill_target_select/area_select/harvest_select` 弹窗也不再依赖当前回合（本身已独立于回合）。
- 原因
  - 引擎线程只有在需要人类输入时才会产生 `pending_request`，因此放开限制不会使 AI 的输入被误操作。
- 额外加固（可选）
  - 若后续引入多人且多个真人，则再扩展 `PendingRequest` 增加 `requester_name` 字段；本轮先以“1 真人 + 若干 AI”的假设修复现有死锁问题。

### D. 【鬼才】判定牌展示 + 替换后获得判定牌
- 文件：`sanguosha/game.py`, `sanguosha/skills.py`
- 改动点
  1. 在询问是否发动鬼才前，明确展示当前判定牌：
     - 在 `_run_judgment` 抽到判定牌后先输出一条 `"[判定] <判定者> 判定牌：<牌名 花色点数>"`。
     - `guicai_before_judge` 的 prompt 中也包含判定牌信息（便于 GUI 模态窗口直接看见）。
  2. 鬼才发动后获得原判定牌：
     - 当 `guicai_before_judge` 返回替换牌时：
       - 将“被替换掉的原判定牌”加入司马懿手牌（不进弃牌堆）
       - 替换牌成为最终判定牌参与结算
     - 与天妒冲突处理：
       - 天妒只对“最终判定牌”生效；鬼才获得的是“原判定牌”，两者不冲突。

### E. 技能选牌/弃牌提示优化（覆盖所有相关技能）
- 文件：`sanguosha/gui.py`, `sanguosha/skills.py`, `sanguosha/game.py`
- 方向
  - GUI 主提示 `_hint_var` 不再使用过于泛化的“技能选牌：请先选择要弃置的手牌”，改为从 `pending_request.prompt` 提取更具体的短提示：
    - `技能选牌-武圣：...` → 展示“武圣：请选择一张牌”
    - `技能选牌-青囊：...` → 展示“青囊：请选择要弃置的牌”
    - `技能选牌-鬼才：...` → 展示“鬼才：请选择替换的牌”
    - `技能选牌-反间：...` → 展示“反间：请选择要交出的牌”
  - 弃牌阶段进入时自动展示“需弃 X 张”的提示（从 `弃牌选择：需弃X张...` 解析）。
- 代码侧补齐
  - 检查所有技能/阶段的输入 prompt 是否都带上 `技能选牌-<技能名>：` 或 `弃牌选择：需弃X张...` 这样的标准前缀，避免再次落入 `visual_engine.py` 的 `kind=text` 导致无 UI。

### F. 选将页与窗口尺寸优化
- 文件：`sanguosha/gui.py`
- 改动点
  - 设置统一窗口最小尺寸与初始尺寸（对齐 battle 页的理想高度），避免 start 页太小造成后续页面被“锁死”在小高度。
  - 重排 start 页 UI：
    - 左侧：武将下拉选择
    - 右侧：实时展示该武将的技能与描述（复用 `GENERAL_POOL`），减少“选将只看名字”的信息不足
  - 在 `show()` 切换到 battle 页时（或初始化时）调用 `root.minsize`/`root.geometry` 进行一次对齐，确保 y 轴足够显示日志与手牌区。

### G. 敌方武将卡新增“查看技能”按钮
- 文件：`sanguosha/gui.py`
- 改动点
  - 在 `enemy_box` 增加按钮“查看技能”，点击后弹出居中窗口：
    - 显示敌方武将名
    - 列出其全部技能（主动/被动）与描述
  - 弹窗复用现有居中逻辑（`Toplevel + transient + grab_set + _center_modal`），保证鼠标距离短。

## Assumptions & Decisions
- 本轮仍以“1 真人 + AI 对手”的运行模式为基准修复交互死锁；多人真人输入的 `PendingRequest.requester_name` 扩展不在本轮强制范围内（但提示文本/候选列表格式保持多人可扩展）。
- “鬼才发动后获得判定牌”按你提出的规则实现（与部分原版细节差异以你的需求为准）。
- 提示优化以“不增加新的常驻按钮区”为前提，优先通过现有 `_hint_var` 与模态弹窗内容增强完成。

## Verification Steps
### 自动化测试
- `pytest -q`
- 新增/更新用例建议：
  - 判定输出包含牌名（判定区 + 八卦阵）
  - 遗计：摸到两张牌会在日志中展示；并且在电脑回合触发时 GUI 输入不会被禁用（用 visual_engine 测试覆盖 `pending_request.kind=skill_card_select` 时不依赖 current_player）
  - 鬼才：prompt 中包含判定牌信息；发动后司马懿手牌数增加（获得原判定牌）

### GUI 手动验收
- 判定区/八卦阵判定日志显示“牌名 + 花色 + 点数”。
- 玩家在电脑回合触发遗计、或被电脑刚烈要求弃牌时，手牌与确认按钮可点击且能继续对局。
- 遗计摸牌后会先看到两张牌，再决定是否给他人；给牌流程不会卡死。
- 鬼才先显示判定牌后询问是否替换；发动后获得原判定牌。
- 选将界面与对局界面窗口高度一致/足够大，切换页面不会继承过小高度导致布局挤压。
- 敌方武将卡可点击“查看技能”弹窗查看技能与描述。

