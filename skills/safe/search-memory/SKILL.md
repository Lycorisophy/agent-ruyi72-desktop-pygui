---
name: search-memory
description: 按关键词检索事实/事件/关系；已启用 SQLite 且 memory.db 中有数据时走 FTS5，否则回退为 JSONL 子串匹配。search_memory 可对事件按 world_kind / temporal_kind 可选过滤。
---

# search-memory（检索记忆）

在如意72全局记忆库中按**关键词**查找相关条目：当 `memory.backend` 为 `dual`/`sqlite` 且数据库内已有记忆行时，优先使用 **FTS5**；否则在 **`facts.jsonl` / `events.jsonl` / `relations.jsonl`** 上做**子串**扫描。与 **`browse_memory`**（只看每类最近若干条）分工不变：需要「翻全库」时用本工具。

## 何时使用

- 用户提到具体名词、项目名、错误号、日期片段等，需要在**全部记忆**中**定位**相关条目时。
- `browse_memory` 只看到最近若干条，若不够再使用 **`search_memory`** 扩大查找范围。

## 在 ReAct 中

- 直接调用工具 **`search_memory`**：
  - `query`：检索关键词或短语（必填）。
  - `max_per_kind`：每类最多返回条数（可选，默认 15）。
  - `event_world_kinds`：可选，逗号分隔，仅过滤**事件**。取值：`real`、`fictional`、`hypothetical`、`unknown`；留空表示不按世界层过滤。
  - `event_temporal_kinds`：可选，逗号分隔，仅过滤**事件**。取值：`past`、`present`、`future_planned`、`future_uncertain`、`atemporal`；留空表示不按时间层过滤。

## 局限与补充工具

- **字面检索**：子串与 FTS 仍可能漏掉**同义词、换表述**；需要语义近义命中时请用 **`search_memory_semantic`**（需 `memory.vector_enabled` + Ollama embedding）。
- **会话原文**：若要在历史对话里搜片段，使用 **`search_history`**（需 `memory.messages_index_enabled`，且 `memory.backend` 为 `dual`/`sqlite`）。
- 需要时可换关键词或再结合 **`browse_memory`** 看最新摘要。
