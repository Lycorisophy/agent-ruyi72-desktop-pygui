# 如意72（ruyi72）项目概要设计

> 桌面端 AI Agent 壳：PyWebView + Python 后端 + 本地/云端 LLM。实现细节以源码为准；本文用于快速对齐架构与文档入口。

## 定位与运行时

- **平台**：Windows 10/11；**UI**：PyWebView（Edge WebView2）加载 `web/` 静态前端。
- **入口**：根目录 `app.py`；暴露 `Api` 实例给 `window.pywebview.api`。
- **语言运行时**：Python 3.11/3.12 推荐；依赖见 `requirements.txt`。

## 技术栈（摘要）

| 领域 | 说明 |
|------|------|
| LLM | `OllamaClient`（`/api/chat` 或 OpenAI 兼容 `/v1/chat/completions`）；流式 `stream_chat` |
| ReAct | LangChain `create_agent` + LangGraph（`src/agent/react_lc.py`） |
| 配置 | YAML + Pydantic `RuyiConfig`（`src/config.py`）；可 `~/.ruyi72/ruyi72.local.yaml` 覆盖 `llm` |
| 会话持久化 | 每会话目录：`meta.json`（含可选 `avatar_mode` / `avatar_ref`，见 `docs/session-avatar-design.md`）、`messages.json`；另有 `dialogue_state.json`、`context_checkpoint.json`（上文压缩）、`output_annotations.json`（助手输出检查）、`scheduled_tasks.json` 等 |
| 记忆 | JSONL / SQLite（`memory.backend`）；可选向量与 FTS；设计见 `docs/` 下记忆专篇 |

## 目录与职责（顶层）

```
app.py                 # 启动、Api、调度线程入口
config/ruyi72.example.yaml
docs/                  # 模块设计、团队模式、记忆、定时任务等
resources/             # 静态资源、知识库提示片段等
skills/                # 仓库内技能（safe/act/warn_act）；本 skill 在 skills/safe/ruyi72-project-overview/
web/                   # 前端 HTML/CSS/JS
src/
  config.py            # RuyiConfig
  service/conversation.py   # 会话编排核心
  service/output_review.py  # 助手输出检查（引用/存疑/按节评审）
  storage/session_store.py  # 会话与 checkpoint 等
  agent/               # ReAct、拟人流、工具、上下文压缩等
  llm/                 # Ollama 客户端、流式、Chat 模型封装
  scheduler/           # 内置定时任务 worker
```

## 核心数据流

1. 前端调用 `Api.send_message` / `persona_send` 等 → `ConversationService`。
2. `ConversationService` 按 `SessionMeta.mode` 与 `session_variant` 分支：**chat**（安全模式流式线程）、**react**（后台 ReAct）、**persona**（拟人流式）、**team** / **knowledge**（专用链路）。
3. 消息读写经 `SessionStore`；LLM 调用经 `OllamaClient` 或 LangChain；工具仅限工作区 `safe_child` 校验路径。ReAct 轮次可将工具返回的结构化 `citations`（JSON 优先）或白名单记忆/检索工具正文中的 URL（`extract_urls_as_tool_citation_rows`）合并进助手消息的 `tool_citations` 与 `output_annotations`（见 `docs/助手输出检查设计.md`）。

## 会话与模式

- **standard**：普通会话；可切换 chat / react / persona（团队、知识库对模式有限制）。
- **team**：`team_size` 与 `team.models` 链式多模型（`src/agent/team_turn.py`）。
- **knowledge**：`kb_preset` 注入知识库相关 system（`src/llm/knowledge_prompts.py`）。

## 关键配置文件（概念）

- `llm.*`：provider、base_url、model、api_mode、max_tokens 等。
- `storage.sessions_root`：会话根目录（空则 `~/.ruyi72/sessions`）。
- `persona.*`：拟人、主动发言等。
- `memory.*`、`memory_auto_extract.*`：记忆与闲时抽取。
- `builtin_scheduler.*`：内置定时任务扫描间隔等。
- `context_compression.*`：上文检查点与摘要压缩（见 `docs/module-design.md` 第 15 节）。
- `output_review.*`：助手输出检查（引用链接、异步存疑、按节自检；见 `docs/module-design.md` 第 16 节与 `docs/助手输出检查设计.md`）。

## 与「技能」目录的关系

- 仓库 `skills/` 下为 **可被加载的 SKILL.md 技能**（ReAct `load_skill` 等）；**本概要 skill** 位于 `skills/safe/ruyi72-project-overview/`，供 Agent 回答「本项目架构」类问题，不参与工作区工具执行。

## 权威文档索引

| 主题 | 路径 |
|------|------|
| 模块总览与边界 | `docs/module-design.md` |
| 助手输出检查（引用/存疑） | `docs/助手输出检查设计.md` |
| 会话形象（Live2D / 像素） | `docs/session-avatar-design.md` |
| 文档索引 | `docs/README.md` |
| 行动模式综述（参考） | `docs/AI智能体行动模式设计指南.md` |
| 可选用系统提示（参考） | `docs/系统提示词/` |
| 团队模式 | `docs/agent-team-mode.md` |
| 定时任务设计 | `docs/scheduled-tasks-design.md` |
| 对话状态机 | `docs/对话状态追踪设计.md` |
| 记忆系统 | `docs/AI智能体ruyi72 记忆系统（永驻+事件）设计（v*.0）.md` |
| 根说明与运行 | `README.md` |

## 修订说明

- 架构级变更（新模式、新持久化文件、新全局配置块）应同步更新 **本文**、**`docs/module-design.md`** 相应节，必要时 **根 `README.md`** 功能列表。
- 仅局部实现细节可只改源码注释或专篇，不必膨胀本概要。
