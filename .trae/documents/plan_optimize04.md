# plan_optimize04

## Summary
本计划目标是把当前战斗页底部常驻的 4 类交互区改为“按需弹出、居中显示”的模态窗口，避免平时占位和长距离移动鼠标；并把华佗【青囊】目标从“自己/对方二选一”改为“列出场上所有可选武将”：
- 响应区（yes/no）
- 青囊目标（技能目标选择）
- 区域选择（过河拆桥/顺手牵羊等）
- 五谷丰登选择

已确认范围与决策：
- 只替换底部三栏相关交互，不改出牌主流程和弃牌多选流程。
- 使用模态阻塞弹窗（弹窗未处理完前，不允许点击主界面其它操作）。
- 战斗页底部这几块常驻区域完全移除。

成功标准：
- 平时战斗页不再显示“响应区/青囊目标/区域选择/五谷丰登”按钮区。
- 仅在对应 `pending_request.kind` 到来时弹窗，提交后自动关闭。
- 弹窗默认出现在主窗口中间附近（相对主窗体居中），鼠标移动距离明显缩短。
- 华佗【青囊】弹窗目标为动态列表（按提示索引提交），不写死 `0/1`，为后续非 1v1 扩展预留接口。

## Current State Analysis
- `sanguosha/gui.py` 目前在 `_build_battle_page()` 中固定渲染：
  - `_response_bar`（yes/no）
  - `_skill_target_frame`（青囊目标：自己/对方）
  - `_area_frame`（区域选择）
  - `_harvest_frame`（五谷候选）
- 上述区域通过 `_sync_interactions()` 内的：
  - `_sync_response_bar()`
  - `_sync_skill_target_bar()`
  - `_sync_area_bar()`
  - `_sync_harvest_bar()`
  来做启用/禁用，但始终占据页面空间。
- `sanguosha/visual_engine.py` 已能稳定提供请求种类（`yesno` / `skill_target_select` / `area_select` / `harvest_select`），可直接作为弹窗触发条件。
- `sanguosha/skills.py` 中 `qingnang_active()` 当前仅在 `[0]{actor.name} [1]{target.name}` 间选择，写死 1v1 视角，不满足“列出全场武将并可扩展多人”的目标。
- `sanguosha/game.py` 对区域选择与五谷选择仍是文本输入协议，GUI 已通过 `SUBMIT_TEXT` 回传，因此改成弹窗不会破坏规则层接口。

## Proposed Changes

### A. 用统一模态弹窗替代底部常驻交互区
- 文件：`sanguosha/gui.py`
- What
  - 删除战斗页底部常驻的响应区、青囊目标区、区域选择区、五谷丰登区的固定布局。
  - 新增“统一弹窗控制器”，根据 `pending_request.kind` 动态创建并展示对应弹窗内容。
- Why
  - 满足“仅触发时显示、平时不占位”的目标，并提升主界面简洁度。
- How
  - 新增状态字段（如 `_active_modal`, `_active_modal_kind`, `_active_modal_prompt`），保证同一时刻只有一个弹窗实例。
  - 在 `_sync_interactions()` 中不再调用四个 `_sync_*_bar`，改为单入口 `self._sync_modal_request(req, snapshot)`。
  - 当 `req.kind` 属于 `{yesno, skill_target_select, area_select, harvest_select}` 时：
    - 若当前无弹窗或请求已变化：创建/重建对应弹窗；
    - 若请求结束（`req is None` 或 kind 切换到其它类型）：关闭弹窗并清理状态。

### B. 具体弹窗交互映射（严格按触发条件）
- 文件：`sanguosha/gui.py`, `sanguosha/skills.py`
- What
  - `yesno`：显示“提示文本 + 是/否按钮”，点击后提交 `y/n`。
  - `skill_target_select`：显示“技能目标”弹窗，按 prompt 动态解析 `[index]角色名` 列表并生成按钮，点击后提交对应索引。
  - `area_select`：显示“区域选择”弹窗，按钮 `h/w/a/p/m/j` 对应中文区域，点击后提交区域 code。
  - `harvest_select`：显示“五谷丰登”弹窗，解析 prompt 内候选索引并生成候选按钮，点击后提交索引。
- Why
  - 保持与当前规则输入协议完全一致，仅改显示和交互形式。
- How
  - 复用现有提交接口：`self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=...))`。
  - `gui.py`：复用并扩展 `_parse_indexed_options()`，同时支持“目标候选”和“五谷候选”两类索引按钮渲染。
  - `skills.py`：重构 `qingnang_active()` 的人类目标输入提示，改为通用格式（例如 `技能目标-青囊：请选择回复目标 [0]张飞 [1]关羽 ...`），候选集合来自“全场存活且受伤角色”而非 actor/target 二元组。
  - 为 area/havest 弹窗增加“当前提示文案”行，降低误点概率。

### C. 居中显示与主窗口依附
- 文件：`sanguosha/gui.py`
- What
  - 所有交互弹窗使用 `Toplevel`，设置为主窗口子窗口并居中定位到主窗口可视区域中间附近。
- Why
  - 满足“弹出在偏中间，不需要挪很远鼠标”的交互要求。
- How
  - 使用 `transient(self.root)` + `grab_set()` 实现模态依附。
  - 在创建后执行几何定位：基于主窗口 `winfo_rootx/y/width/height` 和弹窗 `winfo_reqwidth/height` 计算中心坐标。
  - 对坐标做最小边界保护，确保弹窗不会出现在屏幕外。
  - 统一应用到 4 类弹窗，避免位置行为不一致。

### D. 清理旧代码路径并保持兼容
- 文件：`sanguosha/gui.py`
- What
  - 移除或下线 `_sync_response_bar/_sync_skill_target_bar/_sync_area_bar/_sync_harvest_bar` 与对应控件引用。
  - 保留原有 `_submit_response/_submit_skill_target/_submit_area/_submit_harvest`（或合并为弹窗内部回调），减少提交行为回归风险。
- Why
  - 避免“新旧两套 UI 并存”导致状态冲突。
- How
  - 统一从弹窗回调进入既有提交函数，保证引擎协议不变。
  - 在 `_cancel_selection()` 或页面切换时附加弹窗清理，防止重开后遗留窗口。

### E. 青囊目标选择的多人扩展接口
- 文件：`sanguosha/skills.py`, `sanguosha/game.py`（如需最小辅助方法）
- What
  - 【青囊】目标从“自己/对方”改为“全场可选角色列表”，由规则层生成可选项，GUI 仅按索引展示和提交。
- Why
  - 满足你提出的“未来非 1v1 模式可复用”要求，避免再次重做目标选择协议。
- How
  - 在 `qingnang_active()` 内基于 `game.players` 过滤 `alive and hp < max_hp` 的候选。
  - 人类输入时输出稳定索引列表（0..n-1），并按索引映射到候选角色。
  - AI 逻辑保持当前优先级思路（低血优先自救/治疗受伤目标），但作用于通用候选列表。
  - 若 `game.py` 缺少便利用法，可补一个只读辅助方法（如“获取存活玩家列表”），不改现有输入协议类型。

## Assumptions & Decisions
- 不新增 `PendingRequest` 字段，仍复用 `prompt + kind` 机制；多人目标通过 prompt 索引文本承载。
- 出牌区、手牌区、弃牌多选不改成交互弹窗（遵循“仅替换底部三栏”）。
- 区域选择弹窗先保持现有 6 区按钮模型；可选区域校验仍由规则层处理（非法选择会提示并再次请求）。
- 若后续希望“仅显示合法区域按钮”，再单独规划对 `prompt` 或 `PendingRequest` 结构化扩展。

## Verification Steps

### 代码级验证
- 运行 `pytest -q`，确认现有核心与引擎测试不回归。
- 重点观察 `tests/test_visual_engine.py`：`yesno/area_select/harvest_select` 请求流仍可被提交并推进对局。
- 补充/更新 `tests/test_core.py` 或 `tests/test_visual_engine.py`：
  - 校验【青囊】目标提示包含动态多候选索引格式；
  - 校验提交任一有效索引都能正确治疗对应角色（不依赖固定 `0/1` 语义）。

### 手动验收（GUI）
- 常态页面检查：
  - 进入对局后，战斗页不再出现底部“响应区/青囊目标/区域选择/五谷丰登”常驻条。
- 触发弹窗检查：
  - 被要求响应【杀】或【无懈可击】时，弹出 yes/no 居中窗口。
  - 华佗发动【青囊】需要选目标时，弹出“全场可选武将列表”窗口，而非“自己/对方”二选一。
  - 使用【过河拆桥】或【顺手牵羊】时，弹出区域选择窗口。
  - 使用【五谷丰登】分配时，弹出候选牌窗口。
- 位置与可用性检查：
  - 每次弹窗均在主窗口中间附近出现，不需要把鼠标移到页面最底部。
  - 弹窗关闭后不残留；下一次触发可再次正常弹出。
