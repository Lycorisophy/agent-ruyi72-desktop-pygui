---
name: browse-memory
description: 浏览用户跨会话长期记忆中最近若干条（事实/事件/关系）；只读，数据源依配置为 JSONL 或已迁移的 SQLite，与工作区无关。
---

# browse-memory（浏览记忆）

用于在**不依赖工作区**的情况下，查看已写入如意72记忆库的内容摘要。

## 何时使用

- 用户或任务需要引用「用户偏好、历史约定、过去事件」等**长期记忆**时。
- 需要先确认「当前记忆里有什么」再回答或执行后续步骤时。
- 与「记住」写入相对：本技能侧重**读**最近条目。

## 在 ReAct 中

- 直接调用工具 **`browse_memory`**（参数 `limit` 可选，默认每类最近若干条）。
- 无需 `load_skill` 即可使用；若需更细说明可再 `load_skill(name="browse-memory")`。
- 若关键词字面不匹配但语义相近，可再配合 **`search_memory_semantic`**（需在配置中开启 `memory.vector_enabled` 且 Ollama embedding 可用）。

## 存储与配置（摘要）

- 目录：`%USERPROFILE%\.ruyi72\memory\`
- **JSONL**：`facts.jsonl`、`events.jsonl`、`relations.jsonl`（`memory.backend` 为 `jsonl` 或 `dual` 时持续追加；`dual`/`sqlite` 下常与库双写）。
- **SQLite**：`memory.db`（`memory.backend` 为 `dual` 或 `sqlite` 时；含结构化表、FTS5、可选向量表等）。当库内已有数据时，浏览与检索可能**以 SQLite 为准**读最近条目。
- **永驻事实**（`tier=permanent`）：先入 **`pending_identity.jsonl`**，不会在未确认前直接改身份 Markdown；用户需在界面 **「永驻待合并」** 确认后，才会追加到 `USER.md` / `SOUL.md` / `MEMORY.md`（路径在 `%USERPROFILE%\.ruyi72\` 下由应用解析）。
