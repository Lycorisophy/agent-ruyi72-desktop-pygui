# AI 智能体 ruyi72 记忆系统（永驻 + 事件）设计（v3.0 · 三期）

> **文档性质**：在 [v2.0](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md) 已定义的分级、SQLite/FTS、向量、永驻队列等基础上的**演进设计**；全文除 **§十「与本仓库」** 外仍以目标与行为约定为主。  
> **本仓库已落地（事件 v3 字段）**：数据模型、JSONL、SQLite（`planned_window` 列存为 `planned_window_json`）、抽取 JSON 契约与 `format_memory_entries` 已贯通 `world_kind`（默认 `real`）、`temporal_kind`（默认 `past`）、`planned_window`（默认 `{}`）。**`search_memory`** 已支持可选 **`event_world_kinds` / `event_temporal_kinds`**。**冷启动**默认排除 **`fictional`**，并可选 **`bootstrap_planned_summary_enabled`** 下单独 **「近期计划（摘要）」**（`future_planned` / `future_uncertain`）。**`event_embeddings` + 抽取后索引**：默认 **`vector_index_fictional_events: false`** 不向量化虚构事件；**`search_memory_semantic`** 可检索事实与事件向量，参数 **`include_fictional_events`** 控制是否命中虚构事件向量。**仍为后续目标**：M9 计划窗口强归一化/兑现状态、历史事件向量回填等。  
> **排期声明**：阶段与验收为产品/技术对齐用，**不构成交付承诺**。

## 一、三期相对二期的增量

| 维度 | v2.0 已有 | v3.0 三期目标 |
|------|-----------|----------------|
| 事件「是否发生」 | `assertion`：话语内**模态**（actual / negative / possible / not_occurred） | 增加与**世界层**、**时间层**正交的分类，区分**虚构叙事**、**计划/未来**与**已发生事实** |
| 时间语义 | 字段 `time` 为自由文本 | 结构化 **时间锚类型** + 可选 **计划窗口**（ISO 或相对短语归一化） |
| 检索与注入 | 浏览/关键词/向量/历史 | 默认策略**按事件类型过滤**；工具显式参数控制是否包含虚构、计划、未兑现项 |
| 关系 | 11 类有向关系 | 可扩展：**计划—兑现**、**虚构内引用**（弱边，默认不参与因果推理） |

**设计原则**：与 v2 的 `assertion`**并存**——`assertion` 描述「这句话怎么断言事件」；三期字段描述「在用户的知识世界里，这件事属于哪一类」。

---

## 二、事件扩展：`world_kind`（世界层：是否虚构）

描述该条事件在用户意图中是否为**真实世界已发生/将发生**的片段，还是**故事、假设、玩笑、反事实**等。

| 建议值 | 含义 | 示例 |
|--------|------|------|
| `real` | 用户陈述为**真实世界**中的事（含计划将来要做的事，时间层见下节） | 「我昨天跑了 5 公里」「我打算下周交报告」 |
| `fictional` | **虚构作品/角色扮演/明显编造**中的事件，不应当作用户生活事实 | 「小说里主角登上了塔」「D&D 里队伍击败了龙」 |
| `hypothetical` | **假设、思想实验**，非已发生也非单纯讲故事 | 「如果明天下雨，我就不出门」 |
| `unknown` | 抽取时**无法区分**或用户混用；默认按 `real` 处理但**降低注入优先级**（实现可选） |

**默认迁移**：历史无该字段的事件 → **`world_kind = real`**（与 v2 默认「叙事即事实」相容）。

**与 `assertion` 组合示例**：

- 「他**没有**辞职」→ `assertion=negative`，`world_kind=real`。  
- 「**假如**他辞职了，项目会延期」→ `assertion=possible` 或 `hypothetical` 话语标记，`world_kind=hypothetical`。  
- 「昨天对话里我们编的段子：**外星人**来了」→ `world_kind=fictional`（若模型能识别为虚构语境）。

---

## 三、事件扩展：`temporal_kind`（时间层：过去 / 现在 / 计划未来）

描述事件在**时间轴**上的位置，与 `time` 字符串互补：`time` 保留人类可读；`temporal_kind` 供过滤与调度。

| 建议值 | 含义 | 典型 `time` |
|--------|------|-------------|
| `past` | **已发生**（相对对话锚点已过） | `2026-04-01`、`上周三` |
| `present` | **正在进行或刚发生**（与「现在」重叠） | `现在`、`今天上午` |
| `future_planned` | **用户意图中确定或倾向要做的未来行动** | `下周一开始`、`明天去体检` |
| `future_uncertain` | **可能发生但未承诺** | `也许下个月换工作` |
| `atemporal` | **无明确时间**的习惯、规律、泛化陈述 | 「我通常周末跑步」→ 可映射为习惯事实，事件层可少用或 `atemporal` |

**计划类事件（用户明确关心）**：

- 建议增加可选字段 **`planned_window`**（对象）：  
  - `start` / `end`：ISO 8601 日期或日期时间（由抽取或后置归一化填充）；  
  - 或 `resolution: fuzzy` + `text: "下周"` 保留原文，避免错误强解析。  
- 与 **`future_planned`** 配合：冷启动注入、ReAct 工具可默认 **只展示未来 7～30 天内的计划**（可配置）。

**默认迁移**：无字段 → **`temporal_kind = past`** 或 **`atemporal`**（由实现选定：若旧数据多为「已发生叙事」则 `past`）。

---

## 四、抽取协议补充（JSON 契约增量）

在 v2 `events[]` 项上**可选扩展**（缺失则走默认迁移规则）：

```json
{
  "events": [
    {
      "action": "用户计划下周完成季度总结并发给主管",
      "result": "",
      "time": "下周",
      "temporal_kind": "future_planned",
      "world_kind": "real",
      "planned_window": { "text": "下周", "resolution": "fuzzy" },
      "assertion": "actual",
      "triggers": ["计划", "总结"],
      "subject_actors": ["用户"],
      "object_actors": []
    },
    {
      "action": "主角在第三章发现了密室",
      "result": "",
      "world_kind": "fictional",
      "temporal_kind": "atemporal",
      "metadata": { "fiction_context": true }
    }
  ]
}
```

**抽取提示词要求（实现时）**：

- 明确区分：**真实经历 / 计划 / 虚构叙事 / 假设**。  
- 「下周」「明天」类 → 优先 `future_planned` + `planned_window.text`。  
- 用户说「我记得小说里…」「游戏里…」→ `world_kind=fictional`。

---

## 五、存储与索引（目标）

- **`memory_events` 表（本仓库）**：已增加列 `world_kind`、`temporal_kind`（TEXT，应用层归一化）；`planned_window` 以 **`planned_window_json`** 存 `json.dumps` 文本，读路径映射为 `planned_window` 字典。  
- **FTS + 事件过滤**：索引 `body` 已包含 `world_kind` / `temporal_kind` 等；关键词检索 **`search_memory`** 在 SQLite 路径下对 `memory_events` **JOIN** 后按 `world_kind` / `temporal_kind` 子集过滤（见实现）。  
- **向量**：**`fact_embeddings`** 与 **`event_embeddings`**（表 `event_embeddings.world_kind` 便于检索时排除 `fictional`）；索引策略见 **`memory.vector_index_fictional_events`**；语义检索见 **`search_memory_semantic`**（`include_events` / `include_fictional_events`）。

---

## 六、检索、注入与工具（行为约定）

| 场景 | 建议默认行为 |
|------|----------------|
| 会话冷启动记忆块 | **已实现**：排除 **`fictional`**；**`bootstrap_planned_*`** 控制主事件区与 **「近期计划（摘要）」** 分轨（条数上限见配置） |
| `browse_memory` / `search_memory` | `search_memory` 已实现可选 **`event_world_kinds` / `event_temporal_kinds`**（仅事件）；`browse_memory` 仍可按产品需要再加分页或类型折叠；`include_fictional` 类全局默认仍为配置目标 |
| ReAct | 用户问「我下周要做什么」→ 显式查 **`temporal_kind=future_planned`**；问「小说剧情」→ 允许 `fictional` |

---

## 七、三期其它可演进能力（设想）

以下与「虚构/未来」正交，可按优先级拆分迭代：

1. **计划生命周期**：`future_planned` 事件后续状态 **`fulfilled` / `cancelled` / `postponed`**（用户确认或对话抽取更新），避免永久显示过期计划。  
2. **与内置调度联动**：用户明确「提醒我下周三…」时，可选生成 **定时任务** 记录（与现有 `builtin_scheduler` 设计衔接），**不**替代 `memory_events` 真源。  
3. **轻量矛盾提示**：同一主题下 `real` + 互斥 `action`/`result`（或事实 key 冲突）→ 仅 **日志或侧栏提示**，不自动删数。  
4. **衰减与合并**：老旧 `important` 事实或低频引用事件 → 周期性摘要为一条「里程碑」事件（可选 LLM，需人工或策略闸门）。  
5. **来源批次**：`extract_batch_id` 便于「撤销本次抽取」或审计。  
6. **隐私标签**（可选）：`sensitivity: normal | private`，浏览接口默认折叠 private（实现阶段再定）。

---

## 八、迁移与兼容

1. **旧 `events.jsonl` / SQLite 行**：无 `world_kind` → `real`；无 `temporal_kind` → `past`（或 `atemporal`，与二期第七节策略一致并**写死一种**）。  
2. **`assertion` 不变**：不替代三期字段；抽取层同时输出二者。  
3. **关系**：`fictional` 事件之间允许 `relation_type` 边，但 **ReAct 因果链工具默认不跨越 `world_kind` 混用**（避免「小说因果」污染「用户日程」）。

---

## 九、里程碑建议（在 v2 M1–M6 之后）

| 阶段 | 内容 | 验收要点（一句话） |
|------|------|---------------------|
| M7 | `world_kind` + `temporal_kind` 入模型、入库、迁移默认值 | 新抽取可区分虚构与计划；旧数据行为不变 |
| M8 | 检索/冷启动默认过滤 + 工具参数 | 用户不勾虚构时，摘要里不出现小说事件 |
| M9 | 计划窗口归一化 +（可选）兑现状态与调度钩子 | 「下周做什么」可查；过期计划可标记或隐藏 |

---

## 十、与 v2.0 / 实现的链接

- **二期目标与契约**：[AI智能体ruyi72 记忆系统（永驻+事件）设计（v2.0）.md](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md) §4.1.1（`assertion`）、§6 抽取 JSON。  
- **当前代码（v3）**：[memory_store.py](../src/storage/memory_store.py)、[memory_sqlite.py](../src/storage/memory_sqlite.py)（含 **`event_embeddings`**、冷启动主区/计划区 SQL）、[memory_extractor.py](../src/agent/memory_extractor.py)（`_index_events_vector`）、[memory_tools.py](../src/agent/memory_tools.py)、[config.py](../src/config.py)。**仍待后续迭代**：计划生命周期（fulfilled/…）、jsonl 全量 **事件向量回填**、RRF 合并等。

---

## 十一、开放决策（三期实现前建议锁定）

- `unknown` 与 `real` 的默认注入策略是否区分。  
- `planned_window` 强解析（ISO）与 `fuzzy` 保留原文的优先级。  
- 冷启动中 **计划事件** 展示条数上限与时间窗（天）。  
- 是否与 **定时任务** 产品形态合并入口（「计划记忆」一键转提醒）。
