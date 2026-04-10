# AI 智能体 ruyi72 记忆系统（永驻+事件）设计（v1.0）

> **v1.0 范围**：本文档描述**当前已实现并稳定使用**的长期记忆架构——**JSONL 文件存储 + 子串关键词检索**，以及与抽取器、ReAct 记忆工具、闲时自动抽取的集成方式。  
> **演进目标架构**：已独立为 [AI智能体ruyi72 记忆系统（永驻+事件）设计（v2.0）.md](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md)（事实三级、SQLite+FTS5、向量、身份 Markdown 治理等）；第六节仅保留摘要与链接。

## 一、设计目标

- **跨会话的长期记忆**：记忆不按 session 隔离，汇总在统一的全局记忆库中（路径见下）。
- **结构化信息**：从对话或文本中提取三类记忆单元：
  1. **事实（Fact）**：稳定的用户画像、偏好、约定等。
  2. **事件（Event）**：带时间线的任务/操作记录。
  3. **事件关系（EventRelation）**：事件之间的因果/前后/相似等关系。
- **渐进引入**：支持**手动记忆抽取**与可选的**闲时自动抽取**（`memory_auto_extract`）。
- **v1.0 检索**：本地 **jsonl 扫描 + 关键词子串匹配**（`browse_memory` / `search_memory`），无向量、无全文索引引擎。

## 二、数据模型与存储布局

记忆统一存放在用户目录下：

```text
%USERPROFILE%\.ruyi72\memory\
  facts.jsonl
  events.jsonl
  relations.jsonl
```

### 1. Fact（事实）

适合存放用户画像、偏好、账号别名等稳定信息。

```python
class Fact(BaseModel):
    id: str               # fact_xxx，全局唯一
    created_at: datetime
    source: str           # 文本来源描述（可选，例如 "manual"、"chat_snippet"）
    key: str              # 机器可读键，如 "user.home_province"
    value: str            # 原始值，如 "安徽"
    summary: str          # 一句话总结，如 "用户来自安徽"
    confidence: float     # 0~1，模型给出的自信度，允许保守估计
    tags: list[str]       # ["profile", "preference"] 等
```

每条 Fact 以一行 JSON 写入 `facts.jsonl`。

#### v1.0 已实现：事实无分级落库策略

当前实现（`memory_extractor` → `MemoryStore.append_facts`）对事实的处理是：

- 只要 `key`、`value` 非空，即写入 `facts.jsonl`；**不按**「永驻 / 重要 / 非重要」分流。
- 字段 **`confidence`（0~1）** 与 **`tags`** 会原样持久化，但 **v1.0 中未参与**丢弃、向量路由或写入身份 Markdown 的决策。
- **非重要事实仍会写入 jsonl**（若模型在 JSON 里输出了该条且通过键值校验）；**尚未**实现「非重要不存」。
- **`%USERPROFILE%\.ruyi72\` 下的 `USER.md`、`SOUL.md`、`MEMORY.md`** 由用户（或界面）**手动编辑**，经 `src/llm/ruyi72_identity_files.py` 合并进系统提示；**记忆抽取不会自动**把事实追加到上述文件。

事件（Event）与关系（EventRelation）在 v1.0 中同样为**统一写入**对应 jsonl，无与「事实三级」联动的单独策略。

### 2. Event（事件）

用于记录「发生过什么事」，带有时间线和参与者。

```python
class Event(BaseModel):
    id: str               # event_xxx（如未提供则自动生成）
    created_at: datetime
    time: str             # 人类可读时间，如 "2026-04-03 10:30" 或 "约 2026 年 4 月"
    location: str         # "本地电脑"、"公司"、"合肥" 等
    actors: list[str]     # ["用户", "如意72", "同事小王"]
    action: str           # 做了什么（1 句）
    result: str           # 结果怎样（1 句）
    metadata: dict        # 附加字段，如 {"skill": "file-organizer"}
```

存储格式：一行一个 JSON，写入 `events.jsonl`。

**目标架构扩展**（会话 ID、主体/客体角色、触发词、断言等）见 [AI智能体ruyi72 记忆系统（永驻+事件）设计（v2.0）.md](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md) **第四节、第六节**。

### 3. EventRelation（事件关系）

用于在事件之间建立图结构，例如「前置条件」「因果」「相似」等。

```python
class EventRelation(BaseModel):
    id: str               # rel_xxx
    created_at: datetime
    event_a_id: str
    event_b_id: str
    relation: str         # "因果" | "前置" | "类似" | "对比" 等自然语言标签
    explanation: str      # 简短说明为什么存在这种关系
```

写入 `relations.jsonl`，一行一条。

**目标架构**：事件关系改为整型 **`relation_type`**、有向语义与「无关系不落库」等见 [AI智能体ruyi72 记忆系统（永驻+事件）设计（v2.0）.md](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md) **§4.1.2、第六节、第七节**。

## 三、抽取协议（大模型输出格式）

抽取记忆时，向大模型发送专用系统提示 + 用户提供的文本片段，要求**仅返回 JSON**，格式示例：

```json
{
  "facts": [
    {
      "key": "user.home_province",
      "value": "安徽",
      "summary": "用户说自己是安徽人",
      "confidence": 0.9,
      "tags": ["profile"]
    }
  ],
  "events": [
    {
      "id": "e_20260403_1",
      "time": "2026-04-03 10:30",
      "location": "本地电脑",
      "actors": ["用户", "如意72"],
      "action": "如意72 帮用户整理了桌面上的文件和项目目录",
      "result": "用户对整理结果很满意",
      "metadata": {"skill": "file-organizer"}
    }
  ],
  "relations": [
    {
      "event_a_id": "e_20260403_1",
      "event_b_id": "e_20260405_1",
      "relation": "因果",
      "explanation": "4 月 3 日整理文件后，4 月 5 日用户更快完成了报告"
    }
  ]
}
```

后端负责：解析 JSON 与容错、为缺失 `id` 补全、写入对应 jsonl。

## 四、检索策略（v1.0）

### 1. 当前实现：关键词子串匹配

- 在 `facts.jsonl` / `events.jsonl` / `relations.jsonl` 中按行读取，对选定字段做**子串包含**判断（见 `MemoryStore` 与 `memory_tools` 实现）。
- Fact：主要在 `key` / `value` / `summary` 等字段上匹配；Event / Relation 同理在叙述性字段上匹配。
- 返回按相关度简单排序后的 Top N，供 ReAct 中 `browse_memory` / `search_memory` 使用。

### 2. 与「未来展望」的边界

v1.0 **不包含**：全文分词器、BM25、向量相似度、跨会话消息表的 SQL 查询。这些归入第六节。

## 五、集成方式（v1.0 实现）

### 1. 存储层

- `src/storage/memory_store.py`：上述三类模型与 jsonl 追加、浏览、关键词检索接口。

### 2. 抽取器

- `src/agent/memory_extractor.py`：`extract_and_store_from_text(llm_cfg, text) -> dict`  
  构造抽取提示、调用 LLM、解析 JSON、写入 `MemoryStore`，返回各类型条数统计。

### 3. 前端与 API

- 手动「记忆提取」：用户粘贴文本 → `extract_memory` → 同上抽取逻辑。  
- **手动抽取不推进**闲时自动抽取游标；与同一段对话的自动任务叠加时可能产生重复条目，需在 UI 或后续去重策略中说明。

### 4. 闲时自动抽取（`memory_auto_extract`）

- 配置见 `ruyi72.yaml` 与仓库内示例；默认 `enabled: false`。
- 守护线程按 `interval_sec` 唤醒；仅当进程判定**空闲**（无占用中的 LLM 等）时执行。
- 从各会话 `messages.json` 按**每会话游标**增量取文，游标持久化在 `%USERPROFILE%\.ruyi72\memory_auto_extract_state.json`。
- 单周期通常处理有限会话/批次，过长文本取尾部以适配 `max_chars_per_batch`；过短增量可推进游标避免空转。

### 5. 与对话历史的边界（v1.0）

- **会话消息**仍由 `SessionStore` 以 `messages.json` 为主存储；**全局记忆库**是独立 jsonl，二者通过抽取逻辑关联，而非同一物理表。

---

## 六、未来展望（摘要 → v2.0）

以下方向**尚未作为 v1.0 交付范围**。**可评审的目标架构**（表模型、FTS5 列范围、抽取协议 `tier`/`identity_target`、`messages.json` 与 SQLite 关系、jsonl 迁移、里程碑）已写入专篇：

**[AI智能体ruyi72 记忆系统（永驻+事件）设计（v2.0）.md](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md)**

此处仅保留三句摘要，避免与 v2.0 重复维护：

1. **SQLite + FTS5**：对话与事件（及可选事实摘要）结构化存储与全文检索，替代或补充 jsonl 全表扫描。  
2. **事实三级**：非重要不落库、重要入向量、永驻经治理写入 `USER.md` / `SOUL.md` / `MEMORY.md`（默认建议用户确认后再合并）。  
3. **实施顺序**：分级不落库 → 向量 → 永驻合并 → SQLite/FTS → ReAct 工具组合查询（详见 v2.0 第八节；**非承诺排期**）。

---

## 七、文档与代码对照

| 文档章节 | 代码入口（v1.0） |
|---------|------------------|
| 存储模型 | `src/storage/memory_store.py` |
| 抽取 | `src/agent/memory_extractor.py` |
| ReAct 工具 | `src/agent/memory_tools.py` |
| 闲时抽取 | `src/agent/memory_auto_extract.py`、配置 `memory_auto_extract` |
| 身份 Markdown（手动，非抽取写入） | `src/llm/ruyi72_identity_files.py`、`src/llm/prompts.py` 说明 |

若实现与本文不一致，以代码为准，并应回写修订本节或版本说明。

**二期对照预留**：事实 `tier`、向量库、`USER.md`/`SOUL.md`/`MEMORY.md` 自动合并等实现落地后，应在本表增加行，并同步更新 [v2.0 设计](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md) 中「开放决策」与里程碑状态。
