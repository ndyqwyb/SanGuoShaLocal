# plan_optimize02

## Summary
本计划针对你新提出的 7 项优化，采用“同一计划两阶段”实施：
- **阶段 A（交互与信息可读性）**：弃牌阶段自选、多区域定向拆/牵、GUI 日志整理、五谷丰登可视化选牌、开局选将（玩家先选，AI 随机）。
- **阶段 B（规则一致性与武将重构）**：基于标准版官方口径，补全手牌花色点数可视化，重做当前 4 名武将为官方技能版本，并修正由此引起的触发时机和交互。

你确认的关键决策：
- 规则基线：**标准版官方**。
- CLI：**可放弃，仅 GUI 为主路径**。
- 顺手牵羊/过河拆桥：需要**精确点选敌方区域**（手牌/武器/防具/+1/-1/判定区）。
- 弃牌阶段：**多选后确认**。
- 五谷丰登：遵循官方先后顺序（谁使用谁先选），AI 使用均衡评分。
- 日志风格：**事件分组日志**（声明 -> 响应 -> 结算）。
- 选将流程：**玩家先选，AI 从剩余武将随机**。

## Current State Analysis
基于仓库当前实现的只读核查：

### 1) 弃牌阶段
- 当前 `sanguosha/game.py` 的 `_discard_to_limit()` 直接从手牌 `pop(0)` 自动弃置，未提供玩家自选交互。
- 当前 GUI `sanguosha/gui.py` 没有“弃牌阶段专用多选确认区”。

### 2) 顺手牵羊/过河拆桥目标选择
- 当前 `sanguosha/game.py::_resolve_dismantle()` 通过 `_pop_target_asset()` 按固定优先级自动取牌（手牌优先），不支持玩家定向指定“手牌/武器/防具/+1/-1/判定区”。
- GUI 目前只支持“选卡后确认”，未提供“区域点选”二次交互。

### 3) 日志噪声与顺序
- `sanguosha/game.py::_human_play_phase()` 每轮都会输出“你当前体力...手牌...”文本，与 GUI 面板信息重复。
- `resolve_sha()` 中“响应日志”与 `play_card()` 返回消息在 UI 里可能呈现先后不符合直觉（你反馈“打闪在前，使用杀在后”）。
- `sanguosha/gui.py` 当前滚动日志是原始逐条 append，未做事件分组或标签化。

### 4) 五谷丰登交互
- 当前 `sanguosha/game.py::_effect_harvest()` 自动分配（行动者拿首张，另一方拿剩余），没有“展示候选牌 + 人类点选 + AI 评分选牌”的流程。

### 5) 武将技能官方一致性
- `sanguosha/generals.py` 和 `sanguosha/skills.py` 当前是简化实现：
  - 华佗 `青囊` 现在是“回合开始自动回血”被动，与你指出的官方规则不一致。
- 手里虽已有 `Card.suit/rank` 字段（见 `sanguosha/cards.py`），但 GUI 未完整展示每张手牌花色点数，且技能流程未依赖花色做官方判定。

### 6) 选将随机
- `sanguosha/visual_engine.py::_run_game()` 当前写死：
  - 人类 `general="关羽"`
  - AI `general="华佗"`
- 导致你观察到“永远关羽打华佗”。

## Proposed Changes

## 阶段 A：交互与信息可读性

### A1. 弃牌阶段改为 GUI 多选确认
- 文件：`sanguosha/game.py`, `sanguosha/ui_protocol.py`, `sanguosha/visual_engine.py`, `sanguosha/gui.py`
- What
  - 引擎在弃牌阶段发出“需要弃 X 张”的输入请求（新 request kind，例如 `discard_select`）。
  - GUI 展示手牌多选区（可勾选/按钮选中），显示“还需弃置 X 张”，点击确认提交。
- Why
  - 满足“自选弃牌”而非自动弃牌。
- How
  - `game.py`：新增弃牌选择入口函数（人类走输入协议、AI 走评分自动弃置）。
  - `ui_protocol.py`：扩展 `PendingRequest` 与快照字段，支持弃牌请求上下文。
  - `visual_engine.py`：把 GUI 选择结果转成引擎可消费格式（例如索引列表字符串或结构化 `UIAction`）。
  - `gui.py`：新增弃牌阶段专用面板（多选 + 确认按钮 + 剩余计数）。

### A2. 顺手牵羊/过河拆桥支持区域精确点选
- 文件：`sanguosha/game.py`, `sanguosha/ui_protocol.py`, `sanguosha/visual_engine.py`, `sanguosha/gui.py`
- What
  - 对 `顺手牵羊`、`过河拆桥` 增加“目标区域选择”步骤：手牌/武器/防具/+1/-1/判定区。
  - 当选“手牌区”时按规则随机 1 张（不透视手牌）。
- Why
  - 满足你要求的“可指定拆/牵敌方哪个区域”。
- How
  - `game.py`：替换 `_pop_target_asset()` 自动优先级逻辑为“显式区域参数”逻辑；校验区域是否有牌。
  - `gui.py`：在打出对应锦囊后弹出/底栏区域选项按钮。
  - `visual_engine.py`：新增 area-select 请求桥接，提交区域 code 给规则层。

### A3. 日志分组与冗余状态抑制
- 文件：`sanguosha/game.py`, `sanguosha/gui.py`, `sanguosha/visual_engine.py`
- What
  - 在 GUI 模式下抑制 `_human_play_phase()` 的重复状态播报（体力/手牌清单）。
  - 日志改为事件分组：`[声明]` -> `[响应]` -> `[结算]`。
  - 修正“使用杀在前、闪响应在后”的输出顺序。
- Why
  - 提高可读性，减少噪声，便于快速捕捉局势。
- How
  - `game.py`：将关键 action 的日志发射顺序前置并标签化。
  - `visual_engine.py`：可增加日志事件类型（可选），便于 GUI 分组显示。
  - `gui.py`：滚动区增加简易分组样式（前缀标签 + 空行分段）。

### A4. 五谷丰登“展示候选 + 先后选牌”
- 文件：`sanguosha/game.py`, `sanguosha/ui_protocol.py`, `sanguosha/visual_engine.py`, `sanguosha/gui.py`
- What
  - 1v1 下展示翻开的两张牌。
  - 谁使用五谷谁先选：
    - 玩家使用：玩家先选 1 张，AI 自动得剩余。
    - AI 使用：AI 先按均衡评分选 1 张，玩家得剩余。
- Why
  - 对齐你要求的官方顺序与可视化。
- How
  - `game.py`：重构 `_effect_harvest()` 支持“候选池 -> 先选 -> 后选”。
  - AI 评分采用均衡：结合当前血量、手牌结构、回合进攻机会。
  - `gui.py`：新增候选牌展示与点击选择控件。

### A5. 开局选将流程改造（玩家选，AI随机）
- 文件：`sanguosha/visual_engine.py`, `sanguosha/gui.py`, `sanguosha/ui_protocol.py`, `sanguosha/game.py`
- What
  - 去掉 `visual_engine.py` 的硬编码武将。
  - 开局先进入选将页/对话框：玩家从可选池选 1 名，AI 从剩余池随机 1 名。
- Why
  - 解决“永远关羽 vs 华佗”的问题。
- How
  - `gui.py`：在开始页增加选将入口和确认逻辑。
  - `visual_engine.py`：启动 game 前注入玩家所选武将；AI 随机由 `game.py` 处理或引擎预选。

## 阶段 B：标准版技能与花色点数体系

### B1. 手牌花色点数全可视化
- 文件：`sanguosha/cards.py`, `sanguosha/ui_protocol.py`, `sanguosha/visual_engine.py`, `sanguosha/gui.py`
- What
  - GUI 手牌明确显示：牌名 + 花色 + 点数（例如 `杀 ♥7`）。
  - 快照中为手牌条目提供结构化信息（而非纯名字字符串）。
- Why
  - 为官方技能实现（如关羽红牌判定）提供玩家可见基础。
- How
  - `ui_protocol.py` 增加 `CardView`（name/suit/rank）。
  - `visual_engine.py` 将 `Player.hand` 转换为 `CardView`。
  - `gui.py` 手牌渲染与颜色提示（红黑）。

### B2. 四名武将改为标准版官方技能
- 文件：`sanguosha/generals.py`, `sanguosha/skills.py`, `sanguosha/game.py`, `tests/test_core.py`
- What
  - 关羽、张飞、黄月英、华佗按标准版技能重做（包括触发时机与效果）。
  - 修复华佗当前“回合开始自动回血”偏差。
- Why
  - 满足你“官方版本技能”要求。
- How
  - 重构技能定义（描述、主动/被动、触发点）。
  - `skills.py` 重写对应技能逻辑，按花色点数规则判定。
  - `game.py` 必要时补触发钩子与技能可用性校验。

### B3. 日志与技能说明可视化升级
- 文件：`sanguosha/gui.py`, `sanguosha/generals.py`
- What
  - 技能区显示简短描述（hover 或固定文本行）。
  - 日志内关键技能触发统一模板输出（便于识别是技能效果还是牌效果）。
- Why
  - 你提出“现在看不清、看不懂是否符合官方”。

## Assumptions & Decisions
- 本计划默认 GUI 主路径，CLI 不再作为完整玩法目标。
- 仍限定 1v1 模式，不扩展多人。
- 手坑（手牌区）目标选择仍保持不可见具体牌；选择“手牌区”时随机取 1 张。
- 五谷丰登在 1v1 保持完整“展示 + 先后选择”流程。
- 日志优化优先信息密度与顺序正确，不做复杂富文本系统。

## Verification Steps

### 自动化验证（必须新增）
- `tests/test_core.py`
  - 弃牌阶段：人类多选弃牌协议 + AI 弃牌策略。
  - 顺手/过拆：区域选择正确性（含手牌区随机、装备区精确）。
  - 五谷丰登：玩家先选与 AI 先选两条链路。
  - 武将官方技能：4 名武将至少各 2 条核心用例。
  - 日志顺序：声明在前、响应在后、结算最后。
- `tests/test_visual_engine.py`
  - 新增 request kind（弃牌选择、区域选择、五谷选牌）桥接测试。
  - 选将流程：玩家选择 + AI 随机且非固定组合。

### 手动验收（GUI）
- 开局可手选武将，AI 随机从剩余池抽取。
- 弃牌阶段可多选并确认，不再自动弃置。
- 顺手牵羊/过河拆桥可精确指定敌方区域；选手牌区时随机拿/拆 1 张。
- 五谷丰登显示两张候选牌并按“使用者先选”执行。
- 日志中无每回合重复体力/手牌噪声；能快速看清“声明-响应-结算”。
- 华佗等四将技能表现与标准版官方描述一致（含时机）。

