# plan_12_optimizeUI

## Summary
本计划继续优化 GUI 观感与一致性，并修复武器【青釭剑】“杀无视对方防具”在技能出杀路径下可能失效的问题：
1) 手牌槽位恒宽已实现，但空槽位会显示为“空白按钮”，需隐藏；  
2) 人物栏装备区（武器防具、+1-1）改为合并到一行，减少视觉空旷；  
3) 主界面重新排布：标题水平居中，选将居中偏左、技能描述居中偏右，上下留白更均匀；  
4) 排查并修复【青釭剑】无视防具可能存在的漏洞（尤其是【武圣】等技能转化为【杀】的攻击路径）。

## Current State Analysis
### 1) 手牌空槽位显示为按钮
- [gui.py](file:///workspace/sanguosha/gui.py) `_sync_hand()` 当前为了保证“首行 8 槽位恒宽”，对不足 8 张的部分创建了 `state="disabled"` 且 `text=""` 的按钮：
  - 这会在 UI 上表现为一排“空白按钮”，影响观感。

### 2) 装备区行数过多显空
- 当前人物框使用 4 行信息（base/equip/horse/judge），其中 equip 与 horse 分两行，用户觉得过空。

### 3) 主界面布局偏左上角
- [gui.py](file:///workspace/sanguosha/gui.py) `_build_start_page()`：
  - `page` 未做行权重/上下填充，组件自然贴近左上。
  - 标题虽 `columnspan=2`，但页面整体缺少“居中容器”，左右对称感不强。

### 4) 青釭剑漏洞（技能出杀路径）
- [game.py](file:///workspace/sanguosha/game.py#L587-L594) `_effect_sha_attack()` 会在普通出【杀】前设置 `actor.ignore_armor_on_sha`（青釭剑开关）。
- 但 [skills.py](file:///workspace/sanguosha/skills.py#L23-L43) `wusheng_active()` 直接 `game.resolve_sha(actor, target)`，没有设置 `ignore_armor_on_sha`：
  - 若角色装备青釭剑并用【武圣】当杀，当前实现可能仍会触发对方【八卦阵】判定（即“没有无视防具”）。
- 结论：青釭剑“无视防具”不应依赖某个特定的“出杀来源”，而应由“进入杀结算”统一处理。

## Proposed Changes
### A. 隐藏手牌空槽位但保持恒宽
- 文件：`sanguosha/gui.py`
- Why
  - 需要维持“8 张手牌宽度恒定”，但不显示空白按钮。
- How（推荐实现）
  1. 取消创建空白 disabled 按钮。
  2. 对 `hand_frame` 的前 8 列设置固定 `minsize`（像素）或固定 `padx`，确保列宽恒定：
     - `hand_frame.grid_columnconfigure(i, minsize=<slot_px>)`
  3. 仅为存在的手牌创建按钮并放到对应列 `column=idx`。
  4. 当手牌 > 8 时，第二行及以后继续按换行规则创建按钮（不影响首行恒宽）。
- 关键点
  - 固定列宽应以“正常一张牌按钮”的请求宽度为基准：可通过创建一个临时按钮读取 `winfo_reqwidth()`，或使用现有 `HAND_SLOT_WIDTH` 估算并转成 `minsize` 像素常量。

### B. 人物框：装备信息合并为一行
- 文件：`sanguosha/gui.py`
- How
  - 将 `_self_equip_var` 与 `_self_horse_var` 合并为一个 `StringVar`（例如 `_self_equip2_var`），格式示例：
    - `武器 -  防具 -   +1 -  -1 -`
  - 人物框行结构调整为 3 行固定高度：
    1) base
    2) equip(武器/防具/+1/-1 合并)
    3) 判定区
  - 双方框使用完全相同的 grid 行数与 rowconfigure，保证等高等宽。

### C. 主界面居中与对称排布
- 文件：`sanguosha/gui.py`
- How（不改视觉风格，只改布局）
  - 引入一个 `content_frame` 放在页面中心，页面上下各放一行“弹性占位”（row weight=1）实现垂直居中：
    - `page.grid_rowconfigure(0, weight=1)`（上）
    - `content_frame` 放在 row=1
    - `page.grid_rowconfigure(2, weight=1)`（下）
  - `content_frame` 内部两列等宽：
    - 左列：标题（居中） + “选择我方武将” + combobox + 开始按钮
    - 右列：技能描述 label（wraplength 适配）
  - 标题单独 row 并 `columnspan=2` + `sticky="ew"`，确保水平居中。

### D. 青釭剑无视防具统一化（修复漏洞）
- 文件：`sanguosha/game.py`, `tests/test_core.py`
- Why
  - 确保“任何来源导致的杀结算”（普通出杀、武圣当杀、借刀杀人强制出杀等）都一致应用“青釭剑无视防具”。
- How（推荐实现）
  1. 将“是否无视防具”的判定下沉到 `resolve_sha(actor, target)` 内部：
     - 在进入 `_ask_for_shan(... attacker=actor)` 前，临时设置 `actor.ignore_armor_on_sha = (actor.weapon is 青釭剑)`；
     - 结算结束后恢复为 `False`（避免污染其他阶段）。
  2. ` _effect_sha_attack()` 中不再单独设置/重置该标志（或保留但不依赖它），避免重复与分支遗漏。
  3. 新增测试用例：
     - 攻击者装备青釭剑，目标装备八卦阵；攻击者用【武圣】当杀 → 不应触发八卦阵判定（可以通过“没有判定日志/没有判定相关输出/直接进入出闪判断”来断言）。

## Assumptions & Decisions
- “不显示空槽位按钮”采用“固定列宽 + 不渲染控件”的方式实现；不引入 Canvas 或滚动容器，保持实现轻量。
- 主界面调整只动布局与间距，不改现有文案与功能。
- 青釭剑效果以“无视防具=八卦阵不触发”为当前项目可验证标准（目前项目中主要防具效果即八卦阵）。

## Verification Steps
### GUI 手动验收
- 手牌少于 8 张时不再出现空白按钮，但整体宽度仍维持“8 张牌宽度”的恒定值。
- 人物框装备区合并为一行后观感更紧凑，双方框仍等宽等高。
- 主界面打开后标题水平居中，选将与技能描述左右对称，上下留白更均衡。
- 装备青釭剑并用武圣当杀时，对方八卦阵不再触发判定。

### 自动化回归
- 新增/更新 `tests/test_core.py` 覆盖“青釭剑 + 武圣当杀不触发八卦阵”。
- 运行 `pytest -q`。

