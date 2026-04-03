---
name: browse-memory
description: 浏览用户跨会话长期记忆中最近若干条（事实/事件/关系），只读本地 JSONL，与工作区无关。
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

## 存储位置

- 默认：`%USERPROFILE%\.ruyi72\memory\` 下的 `facts.jsonl`、`events.jsonl`、`relations.jsonl`。
