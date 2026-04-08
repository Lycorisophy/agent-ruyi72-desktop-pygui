# 如意72 记忆系统设计（v0.1）

> 目标：为如意72提供可扩展的“长期记忆”能力，先支持**结构化存储 + 关键词检索**，后续再演进到向量检索。

## 一、设计目标

- **跨会话的长期记忆**：记忆不按 session 隔离，而是汇总在统一的全局记忆库中。
- **结构化信息**：从对话或文本中提取三类记忆单元：
  1. **事实（Fact）**：稳定的用户画像、偏好、约定等。
  2. **事件（Event）**：带时间线的任务/操作记录。
  3. **事件关系（EventRelation）**：事件之间的因果/前后/相似等关系。
- **渐进引入**：先实现“手动触发记忆抽取”，再考虑后台定时任务在空闲时自动抽取。
- **简单可落地**：首版使用**本地文件存储 + 关键词匹配**做检索，等稳定后再考虑向量数据库。

## 二、数据模型

记忆统一存放在用户目录下：

```text
%USERPROFILE%\.ruyi72\memory\
  facts.jsonl
  events.jsonl
  relations.jsonl
```

### 1. Fact（事实）

适合存放用户画像、偏好、账号别名等稳定信息，例如“用户是安徽人”、“常用编辑器是 VS Code”。

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

### 2. Event（事件）

用于记录“发生过什么事”，带有时间线和参与者。示例：

> 2026 年 4 月 3 日，在本地电脑上，如意72 帮用户整理了工作目录，用户很满意。

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

### 3. EventRelation（事件关系）

用于在事件之间建立图结构，比如“前置条件”、“因果”、“相似”等。

```python
class EventRelation(BaseModel):
    id: str               # rel_xxx
    created_at: datetime
    event_a_id: str
    event_b_id: str
    relation: str         # "因果" | "前置" | "类似" | "对比" 等自然语言标签
    explanation: str      # 简短说明为什么存在这种关系
```

同样写入 `relations.jsonl`，一行一条。

## 三、抽取协议（大模型输出格式）

抽取记忆时，向大模型发送一个专用系统提示 + 用户提供的文本片段，要求**仅返回 JSON**，格式为：

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

后端会负责：

- 解析 JSON，容错（字段缺失时填默认值或跳过）；
- 为缺失的 `id` 自动生成（`uuid4` 或基于时间）；
- 写入对应的 jsonl 文件。

## 四、检索策略（首版：关键词匹配）

### 1. 当前版本

为了快速落地，首版检索采用：

- **关键词匹配 + 简单评分**：
  - 将查询字符串拆分为关键词（可直接用中文/英文分词，或由大模型输出一组“相关关键词”）；
  - 在本地 `facts.jsonl` / `events.jsonl` / `relations.jsonl` 中扫描：
    - Fact：在 `key` / `value` / `summary` 中查找关键词；
    - Event：在 `action` / `result` / `metadata` 中查找；
    - Relation：在 `relation` / `explanation` 中查找；
  - 简单打分（例如命中次数），返回 Top N。

在 ReAct 或 Ask 模式下，可以通过一个 **memory_retrieval 技能** 来触发这类检索，返回若干条最相关记忆给大模型使用。

### 2. 后续规划：向量检索

未来版本考虑：

- 将 Fact 的 `summary`、Event 的 `action + result` 编码为向量；
- 使用本地向量数据库（如 sqlite+faiss 或本地嵌入服务）：
  - 支持“语义相似度”检索，解决纯关键词匹配对同义词/语义近似不敏感的问题；
  - 兼容离线环境（优先使用本地 embedding 模型）。

在那时，当前的 jsonl 存储仍然有效，只需额外构建一个向量索引即可。

## 五、集成方式（v0.1）

### 1. 存储层

- 新增 `src/storage/memory_store.py`：
  - 定义上述三个模型；
  - 提供简单的写入接口：
    - `append_facts(facts: list[Fact])`
    - `append_events(events: list[Event])`
    - `append_relations(relations: list[EventRelation])`

### 2. 抽取器

- 新增 `src/agent/memory_extractor.py`：
  - 函数 `extract_and_store_from_text(llm_cfg: LLMConfig, text: str) -> dict`：
    1. 构造抽取用的 system prompt + 用户提供的文本；
    2. 调用本地 LLM（Ollama）生成 JSON；
    3. 解析后三类记忆写入 `MemoryStore`；
    4. 返回 `{facts: n1, events: n2, relations: n3}` 统计给前端展示。

### 3. 前端手动触发入口

提供**手动记忆抽取**：

- 主界面有「记忆提取」类入口；用户粘贴文本；
- 前端调用 `pywebview.api.extract_memory(text)`；
- 后端使用 `extract_and_store_from_text` 抽取并保存；
- **手动抽取不会更新**自动抽取游标（见下），若与自动任务覆盖同一段对话，可能产生重复记忆条目。

### 4. 闲时自动抽取（配置 `memory_auto_extract`）

后台守护线程按 `interval_sec` 唤醒；仅当本进程**无进行中的 LLM 调用**（含拟人流式、手动记忆抽取等）时，才尝试抽取。

- 从 `storage` 根目录下各会话的 `messages.json` 读取消息列表，按会话维护**已处理消息条数**游标，持久化在 `%USERPROFILE%\.ruyi72\memory_auto_extract_state.json`。
- 每个周期至多处理**一个**会话：将游标之后尚未处理的 `user`/`assistant` 消息拼成文本（过长则取**尾部**以适配 `max_chars_per_batch`），调用与手动相同的 `extract_and_store_from_text`；成功后将游标推进到当前消息总数；失败则游标不前进，下轮空闲会重试。
- 若新片段去空白后短于 `min_chars_to_extract`，则不调用模型，但**仍会推进游标**，避免在极短增量上反复阻塞。
- 默认 `enabled: false`，需在 `ruyi72.yaml` 中显式开启，以免意外消耗 token。  

