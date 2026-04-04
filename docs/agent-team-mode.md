# 如意72 Agent 团队模式设计（v0.2）

> 目标：在现有「单 Agent 对话 / ReAct」之外，增加一种**链式多 Agent 会话**：用户消息先进入 **A1**，由 A1 决定**独立完成**、**整包委派**下一 Agent，或**部分完成并委派**；中间 Agent 规则相同；**末位 Agent 不得再委派**，必须收口答复。

**v0.2**：修订与顶层 `llm` 的区分、§2.1 与附录 A 的 `team_size` 上界、`N<M` 时未用槽位、配置变更与伪代码一致性，并见 **§十一 审查纪要**。

---

## 一、场景与约束

### 1.1 用户可见行为

- 左侧栏增加 **「团队会话」**（或「创建团队」）按钮。
- **启用条件**：配置文件 **`team.models`** 中**至少 2 条有效槽位**（见下条「`M` 的定义」）。**与顶层 `llm.model` 无关**：单路对话仍只用 `llm`；团队模式**只**以 `team.models` 为准，避免「只配了一个顶层模型」与「团队槽位数」混淆。
- **`M` 的定义**：**`M = len(team.models)`**；每条 **`model`** 在加载配置时由 **`TeamModelEntry`（Pydantic）** 校验：**去空白后必须非空**，否则 `load_config()` 抛出 **`ValidationError`**（应用启动失败，需修正 YAML）。
- 点击后弹出确认：**Agent 数量** `N`，范围为 **`2 ≤ N ≤ min(4, M)`**，其中 **`M` = 已配置的模型数量**（例如只配了 2 个模型时，只能选 `N=2`；配了 4 个及以上时仍最多选到 4）。默认建议 `N = min(3, M)`。
- 创建成功后，该会话在列表中有**可区分标识**（如图标、标签「团队·N」），避免与普通会话混淆。
- 团队会话仍依赖**工作区**（与现有 `workspace` 一致），便于后续若某 Agent 需要读文件或 ReAct，可共用同一工作区策略。

### 1.2 以 N=3 为例的链路

```text
用户输入
   ↓
  A1 处理
   ↓
  A1 决策 ──→ 直接完成 → 对用户展示 A1 最终答复
   │         或
   │         整包委派 A2 → 用户原始问题（+ 可选 A1 附言）交给 A2
   │         或
   │         部分完成 + 委派 A2 → 明确「已完成部分」「交给 A2 的子任务」
   ↓
  A2 处理（同上）
   ↓
  A2 决策 ──→ … → 委派 A3 或自行完成
   ↓
  A3 处理（末位）
   ↓
  A3 只能完成或澄清，不得再委派
```

### 1.3 硬约束

| 约束 | 说明 |
|------|------|
| 槽位与调用 | **每一跳 `A_k` 使用 `team.models[k-1].model`**。须满足 **`N ≤ min(4, M)`** 且 **`N ≤ M`**；**`M < 2` 时禁止使用团队模式**（见 1.1）。 |
| `N < M` 时 | 共享系统块仍可列出**全部 M 个槽位**（含 `suitable_for`），供委派判断；**实际只调用前 `N` 个模型**，不调用第 `N+1…M` 槽位。 |
| 末位不委派 | 第 `N` 个 Agent（记为 `A_N`）**禁止**产生任何「委派」类决策，只能输出对用户的可见结果（或说明无法完成并给出建议）。 |
| 委派有向无环 | 只允许 `A_i → A_{i+1}`，不允许回跳、不允许跳过（即不能 `A1→A3`），避免状态爆炸。 |
| 轮次上限 | 单次用户消息触发的**链式调用次数**应有上限（建议：`N` 次模型调用为理论满链，另加「每步重试」上限），防止异常循环。 |

---

## 二、概念模型

### 2.1 会话类型扩展

在现有 `SessionMeta` 的 `mode: chat | react` 基础上，团队模式需要额外维度。**已定稿采用方案 A**（与 `mode` 正交），字段名与类型见 **附录 A**。

- `session_variant: "standard" | "team"`
- `team_size: int | null`（团队会话时为 **`2..min(4, M)`**，与附录 A 一致；**不再**写死 `2..4`）

**方案 B**（扩展 `mode` 为 `team`）不作为实现依据，仅作历史记录。

本文档：`chat`/`react` 仍表示单 Agent 行为；**P0 团队会话固定 `mode=chat` + `session_variant=team`**，不在此会话使用 ReAct（见第八节）。

### 2.2 Agent 身份与提示词

- 统一记为 **A1 … A_N**，与配置中 **`team.models` 列表顺序一一对应**：`A1` 使用第 1 条模型的 `model` 名调用 LLM，`A2` 使用第 2 条，以此类推（**继承**全局 `llm.base_url`、`api_mode` 等，仅 **`model` 标识不同**，具体见附录 D）。
- **用户为每个模型写的「适合干什么」**（配置字段 **`suitable_for`**，自由文本）用于：
  1. **委派决策**：各跳模型在生成 `team_decision_v1` 时，可对照后续槽位是否更匹配子任务（例如 A1 为小模型、A2 为大模型；或 A1 为 MoE、A2 偏代码、A3 偏推理）。
  2. **系统提示词**：将**整份**「各槽位模型 + 用户说明」作为**同一段固定块**，注入**每一次**团队链路中的 **所有** Agent（见下），使任意一跳都能「看见」整条流水线能力与分工。
- **共享块示例结构**（实现时可微调措辞，语义须保留）：

```text
【团队模型分工（由用户在配置中填写，所有 Agent 均可见）】
- A1（模型: <name>）：<suitable_for>
- A2（模型: <name>）：<suitable_for>
…
- 当前你的角色：<Ak>；仅可向下一槽位委派，末位不得委派。
```

- 每条链式调用使用**独立**的「当前步 system + 上述共享块 + 当前槽位说明 + 上下文」，**不**要求各 Agent 共享同一对话 `messages` 全历史；为可观测性，建议在持久化消息中写入**带角色标签**的片段（见第四节）。

### 2.3 与「单路 LLM」配置的关系

- 现有顶层 **`llm`**（`base_url`、`model`、`temperature` 等）仍作为**默认单 Agent 对话 / ReAct** 与**团队链路除 `model` 外的共用参数**（如连接方式）。
- **`team.models`** 为**有序列表**；团队会话第 `k` 跳使用 `team.models[k-1].model` 作为该次请求的模型名，其它参数可与顶层 `llm` 合并（实现定稿见附录 D）。

### 2.4 委派决策（机器可解析）

每一非末位 Agent 在输出中必须产生**结构化决策**（**定稿 schema 见附录 B：`team_decision_v1`**）。摘要如下：

- `delegate_full`：`handoff` 可为空，表示把**用户本轮原始问题**原样交给下一 Agent（编排层可附加上一跳的附言）。
- `delegate_partial`：**必须**填写 `done_summary` 与 `handoff`。
- 末位 Agent：仅允许 `action: "complete"`；若模型输出委派，**编排层强制覆盖**为「由 A_N 直接生成最终答复」，并记录告警日志。

解析失败时的策略：**一次**重试（简化 prompt）；仍失败则降级为「当前 Agent 直接 complete」，避免卡死。

---

## 三、编排流程（后端）

对**单次用户消息**，编排器伪代码（与附录 B 一致：**每一跳**均解析 `team_decision_v1`，末跳亦同）：

```text
输入: user_text, N, workspace, history（团队会话内可裁剪的共享上下文）
current_index ← 1
loop:
  if current_index > N: break  # 不应发生
  prompt ← build_agent_prompt(index=current_index, user_text, prior_handoffs...)
  response ← LLM( model = team.models[current_index-1], ... )
  decision ← parse_decision(response)  # 必须含 team_decision_v1

  if current_index == N:
    要求 decision.action == complete，取 final_answer 写入会话；否则重试/降级；结束

  if decision.action == "complete":
    取 final_answer 写入会话；结束

  if decision.action starts with "delegate_":
    校验 target == "A{current_index+1}"；更新 prior_handoffs
    current_index ← current_index + 1
    continue
```

**说明**：旧版伪代码在「末位」分支先写「写入 response 正文」易与附录 B（必须 JSON + `final_answer`）冲突，以上以 **统一解析 JSON** 为准。

### 3.1 与现有 `ConversationService` 的关系

- **新建路径**：`create_team_session(team_size)` → 写入 `session_variant` + `team_size`。
- **发送路径**：`send_message` 若检测到团队会话，走 **`run_team_turn(...)`** 而非单路 `OllamaClient.chat` / `run_react`。
- **持久化**：`messages.json` 中除 `user`/`assistant` 外，可增加 **`role: "system"` 或扩展 `assistant` 的 metadata**（若前端仅支持两种角色，可用 `assistant` + 前缀如 `[A1]`，与现有渲染兼容）。

### 3.2 中间过程是否展示给用户

- **默认**：仅展示**最终**对用户的 `assistant` 消息（简洁）。
- **可选（设置项）**：展示 A1→A2 委派摘要（调试或透明模式），便于用户理解分工。

---

## 四、消息持久化建议

为兼顾现有前端与审计需求：

| 条目 | 建议 |
|------|------|
| 用户消息 | 照旧一条 `user`。 |
| 最终回复 | 一条 `assistant`，内容仅为用户可见正文。 |
| 链式痕迹（可选） | 使用 `assistant` 多条，带前缀 `[团队·A1]`、`[团队·A2]` …，或写入 `meta.json` 的 `team_trace` 数组（含每步 decision JSON）。 |

首版可只存**最终 assistant** + **磁盘侧 team_trace**，减少 UI 改动。

---

## 五、前端改动要点

1. **侧栏**：「新建」旁或下方增加 **「团队会话」** 按钮；**`team.models` 少于 2 条时禁用**并提示。
2. **弹窗**：选择 `N`，满足 **`2 ≤ N ≤ min(4, M)`**（`M` 为已配置模型数），确认后调用 `create_team_session`（或扩展后的 `create_session`）。
3. **会话列表**：团队会话显示标签「团队 N」或专用图标。
4. **会话栏**：若保留 `mode` 单选，团队会话可禁用或隐藏「ReAct」单选，或显示只读说明「当前为团队模式」。

---

## 六、API 草案

| API | 说明 |
|-----|------|
| `create_team_session(team_size: int, title?: str)` | `2<=team_size<=min(4, M)`；若 `M<2` 返回错误；返回与普通 `open_session` 类似结构 |
| `get_active_session` / `open_session` | 响应 `meta` 中带 `session_variant`、`team_size` |
| `get_settings_snapshot`（或等价接口） | 建议返回 **`team_model_count`**（或 `team_models` 元信息），供前端控制团队按钮与 `N` 的上限 |
| `send_message` | 内部路由到团队编排器；对外接口可不变 |

---

## 七、风险与边界

- **延迟与成本**：一条用户消息最多触发 **N 次**（或 N + 重试）LLM 调用，需在 UI 显示「处理中」。
- **一致性**：各 Agent  persona 差异过大可能导致 handoff 断裂，需模板化 `handoff` 格式与校验。
- **安全**：若某步接 ReAct/工具，需在团队模式下明确**哪一 Agent 可执行工具**、是否需用户二次确认（建议首版**团队模式仅 chat、无工具**，降低风险）。

---

## 八、分阶段落地建议

| 阶段 | 内容 |
|------|------|
| **P0** | `SessionMeta` 扩展 + 创建团队会话 API + 编排循环（纯 chat、JSON 决策解析）+ 前端按钮与列表标识 |
| **P1** | `team_trace` 持久化、可选「透明模式」展示分工 |
| **P2** | 末位或指定 Agent 允许 ReAct/工具（权限模型） |
| **P3** | 各槽位独立 `temperature` / `max_tokens` 覆盖（在 `team.models` 条目上可选扩展） |

---

## 九、与现有文档的关系

- 记忆系统（`docs/memory-system.md`）与团队模式**正交**：团队会话可选择是否沿用全局记忆注入策略；若注入，建议在**仅第一条用户消息**或**每一轮仅 A1** 注入，避免重复 token。

---

## 十、小结

团队模式本质是**固定拓扑的有向流水线**：用户 → A1 → … → A_N，由非末位 Agent 输出**结构化委派决策**，编排器负责解析、拼 handoff、调用下一 Agent；**A_N 仅收口**。前端通过专用入口创建会话并选择 `N`，后端扩展会话元数据与独立编排路径即可渐进实现。

---

## 附录 A：`SessionMeta` 字段定稿（与实现对齐）

以下字段写入各会话目录下的 `meta.json`，与现有 `SessionMeta` **向后兼容**：旧文件缺少新字段时，实现上应视为 `session_variant="standard"`、`team_size=null`。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | `string` | 是 | 现有：会话 ID |
| `title` | `string` | 是 | 现有 |
| `workspace` | `string` | 是 | 现有 |
| `mode` | `"chat"` \| `"react"` | 是 | 现有；**团队会话 P0 固定为 `"chat"`** |
| `react_max_steps` | `int` | 是 | 现有；团队会话下可忽略或仍保留默认值 |
| `updated_at` | `string` | 是 | 现有 ISO 时间 |
| `session_variant` | `"standard"` \| `"team"` | 否 | **默认** `"standard"`（缺省按此处理） |
| `team_size` | `int` \| `null` | 否 | **当且仅当** `session_variant=="team"` 时为 **2…min(4,M)**；标准会话为 `null` 或省略 |

**约束：**

- `session_variant=="team"` ⇒ `team_size ∈ {2,…,min(4,M)}`（`M` 为配置中团队模型数），且 `mode=="chat"`（P0）；并满足 **`team_size ≤ M`**。
- `session_variant=="standard"` ⇒ `team_size` 应为 `null` 或省略。

**API 响应中的 `meta`：** 与 `SessionMeta.model_dump()` 一致，前端依 `session_variant` / `team_size` 渲染「团队·N」标签。

---

## 附录 B：委派决策 JSON `team_decision_v1`

模型在**每一跳**须输出一段可被解析的 JSON（建议放在 Markdown 的 **JSON 代码围栏**内，或整段回复即为 JSON），字段如下。

### B.1 Schema

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | `string` | 是 | 固定为 **`"team_decision_v1"`** |
| `action` | `string` | 是 | 见 B.2 |
| `target` | `string` \| `null` | 条件 | 下一跳 Agent  id，**仅**允许 `"A1"`…`"A{N}"` 中的**下一个**（见 B.3） |
| `done_summary` | `string` \| `null` | 条件 | `delegate_partial` 时**必填**；其余可为 `null` |
| `handoff` | `string` \| `null` | 条件 | `delegate_partial` 时**必填**；`delegate_full` 可为 `null`（表示不再附加子任务描述，由编排层传用户原问题） |
| `user_visible` | `boolean` | 否 | 默认 **`false`**。为 `true` 时，可将 `progress_note` 展示给用户（若产品开启透明模式） |
| `final_answer` | `string` \| `null` | 条件 | **`action=="complete"` 时必填**，为用户可见最终回复 |
| `progress_note` | `string` \| `null` | 否 | 委派前可选进度说明；**不**替代 `handoff` |

### B.2 `action` 取值

| 值 | 含义 |
|----|------|
| `complete` | 由当前 Agent 收口，`final_answer` 给用户 |
| `delegate_full` | 将本轮任务**整包**交给 `target`（下一 Agent） |
| `delegate_partial` | 已部分完成 `done_summary`，剩余由 `target` 执行 `handoff` |

末位 Agent（`A_N`）：仅允许 `complete`；若出现 `delegate_*`，编排层丢弃委派并强制要求模型仅输出 `complete`（或拼接告警文案，见产品策略）。

### B.3 `target` 规则

- 当前为 **A_k**（`1 ≤ k < N`）时：若 `action` 为 `delegate_full` 或 `delegate_partial`，则 **`target` 必须为 `"A{k+1}"`**（字符串，大小写敏感）。
- 当前为 **A_N**：`target` 必须为 `null`，且 `action` 为 `complete`。

### B.4 校验失败与默认值

- `user_visible` 缺省 → `false`。
- `schema_version` 缺失或不是 `team_decision_v1` → 整段解析失败，走「重试一次 → 降级 complete」流程（第二节 2.4）。

---

## 附录 C：`team_trace`（可选持久化，P1）

用于审计与「透明模式」，可与 `messages.json` 分离存放，例如 `session_dir/team_trace.jsonl`（每行一条 JSON），或嵌入 `meta` 的扩展字段（大时慎用）。

**单行结构（建议）：**

```json
{
  "schema_version": "team_trace_entry_v1",
  "turn_id": "uuid或递增整数",
  "user_message_id": "可选，关联本轮 user",
  "steps": [
    {
      "agent": "A1",
      "raw_decision": { },
      "resolved_action": "delegate_partial",
      "ts": "ISO8601"
    }
  ]
}
```

P0 可不写；实现时以附录 B 的解析结果为准写入 `steps[].raw_decision`。

---

## 附录 D：配置文件中的团队模型列表（定稿）

### D.1 目的

- 决定 **团队模式是否可用**（`len(models) ≥ 2`）。
- 决定 **`N` 的上界**：`N ≤ min(4, len(models))`。
- 为每个槽位提供 **`model` 名称**（调用时与顶层 `llm` 合并）及用户填写的 **`suitable_for`**，拼入 **2.2** 所述共享系统块，**发给团队链路中的每一个模型**。

### D.2 YAML 形态（示例）

与 `ruyi72.yaml` 并存；**不写 `team` 或 `models` 为空**时视为未启用团队多模型（与旧配置兼容）。

```yaml
# 团队多模型（可选）。顺序即 A1、A2、A3…；至少 2 条才允许创建团队会话。
team:
  models:
    - model: "qwen2.5:7b"
      suitable_for: "小模型、延迟低，适合理解与拆分需求、简单路由"
    - model: "qwen2.5-coder:32b"
      suitable_for: "擅长代码与仓库内读写"
    - model: "deepseek-r1:14b"
      suitable_for: "擅长长链推理与复杂结论归纳"
```

说明：

- **`model`**：在 **`llm.base_url`** 上可拉起的模型名（与单路 `llm.model` 含义相同）。
- **`suitable_for`**：用户自由文本，描述体量（小/大）、架构（如 MoE）、领域（代码/推理）等；**原样进入系统提示词**，供当前 Agent 判断是否委派给下一槽位。

### D.3 与顶层 `llm` 的合并规则（实现约定）

- 每次团队调用：**请求参数** = 顶层 `LLMConfig` 的副本，仅将 **`model`** 覆盖为当前槽位的 `team.models[k-1].model`。
- 若未来某槽位需单独 `temperature`，可在列表项中增加可选字段（P3），未指定时沿用顶层 `llm.temperature`。

### D.4 `get_settings_snapshot` 建议字段

| 字段 | 说明 |
|------|------|
| `team_model_count` | `len(team.models)`；**`>=2` 时才允许团队会话** |
| `team_max_agents` | **`min(4, team_model_count)` 当且仅当 `team_model_count >= 2`，否则 `0`**，避免 `M=1` 时误得到 `1` 而误判可组团队 |

---

## 十一、设计审查纪要（一致性 / 风险）

以下为对 v0.1 成文的**对照审查**结论，已吸收进正文或本节。

| 项 | 问题 | 处理 |
|----|------|------|
| **§2.1 与附录 A** | `team_size` 曾写「2..4」，与 **`M` 约束**不一致 | v0.2 统一为 **`2..min(4,M)`** |
| **顶层 `llm` vs `team.models`** | 易误解「只有一个顶层模型就不能团队」 | §1.1 明确团队**仅看** `team.models`；单路仍用 `llm.model` |
| **`M` 与空 `model`** | 若允许空字符串，`M` 虚高 | **`TeamModelEntry` 已校验**：非空 `model`（见 `src/config.py`） |
| **`N < M`** | 未说明未用槽位是否仍展示 | §1.3 表：共享块可列 **M** 条，**只调用前 N 个模型** |
| **§3 伪代码 vs 附录 B** | 末位先写「response 正文」未提 JSON | §3 改为**每跳**解析 `team_decision_v1`，末位取 `final_answer` |
| **`team_max_agents`（`M=1`）** | `min(4,1)=1` 易让前端以为可组 1 人团队 | 实现改为 **`M>=2` 才非零**（见 `app.py`） |
| **配置变更** | 用户改小 `team.models` 后，旧会话 `team_size` 可能 **`> M`** | **须在打开会话或发消息时校验**：若 `team_size > M`（或 `> min(4,M)`），提示重新配置或强制改为标准会话（实现待定） |
| **委派与「跳过」** | 拓扑上不能 `A1→A3`；若模型错误输出 `target: A3`，编排层应**拒绝并重试或规范为 `A2`** | 保持附录 B.3 |
| **记忆注入（§九）** | 团队多跳时 token 重复 | 维持「首条或仅 A1」策略；实现时勿对 A2…重复注入大块记忆 |
| **成本** | 每用户消息最多 **N 次**主模型调用 + 解析失败重试 | §七；UI 必显式「处理中」 |
