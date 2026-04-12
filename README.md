# 如意72（ruyi72）

Windows 11 桌面端 AI Agent 基础框架：使用 **PyWebView** 作为窗口，通过配置文件连接大语言模型；默认连接本机 **Ollama**。

## 环境要求

- **Windows 11**（或 Windows 10），已安装 **Microsoft Edge WebView2 Runtime**（多数系统已预装或随 Edge 提供）。
- **Python**：建议使用 **3.11 或 3.12**。部分环境下 **3.14** 等过新版本可能因 `pywebview` 依赖链无法顺利安装，请改用 3.12 虚拟环境。
- **Ollama**：本机已安装并运行，且已拉取配置中指定的模型，例如：

  ```text
  ollama pull llama3.2
  ```

## 安装

在项目根目录执行：

```text
pip install -r requirements.txt
```

## 开发与测试

在已安装依赖（见上）、Python 版本符合 [环境要求](#环境要求)（建议 3.11 / 3.12）的前提下，于**项目根目录**运行单元测试：

```text
python -m unittest discover -s tests -v
```

测试文件位于 `tests/`（例如 `tests/test_react_tool_citations.py`）。

## 配置

1. 复制 [config/ruyi72.example.yaml](config/ruyi72.example.yaml) 为以下**任一**位置（按优先级从高到低，命中第一个即生效）：
   - 环境变量 `RUYI72_CONFIG` 指向的绝对/相对路径；
   - 当前工作目录下的 `ruyi72.yaml`；
   - 当前工作目录下的 `config/ruyi72.yaml`；
   - 用户目录 `%USERPROFILE%\.ruyi72\ruyi72.yaml`。

2. 按需修改 `llm.provider`、`llm.base_url`、`llm.model`、`temperature`、`max_tokens` 以及窗口 `app.title`、`width`、`height`。`llm.provider` 支持：`ollama`（本地）、`minimax`、`deepseek`、`qwen`（通义千问，DashScope OpenAI 兼容）。后三者走 OpenAI 兼容 `/v1/chat/completions`，通常需要 `llm.api_key`。

   **LLM 日志（三档）**：

   - **终端 INFO 单行摘要**（推荐日常排障）：配置 `llm.log_summary: true` 或环境变量 `RUYI72_LLM_LOG=1`。每条直连/流式调用会打耗时、模型、URL、HTTP 状态等**不含全文 prompt**；ReAct（LangChain）会在每次子 LLM 调用打摘要。
   - **ReAct 工具调用轨迹**（可选）：环境变量 `RUYI72_REACT_TRACE=1` 时，终端 INFO 输出每次工具调用的名称与**截断后的入参/出参**（便于排查「卡在哪一步」；与 `llm.log_summary` 独立）。
   - **终端 DEBUG 全量摘要**：`app.debug: true` 或 `RUYI72_DEBUG=1`，输出脱敏后的请求/响应片段（可能含对话内容，勿在公共环境开启）。
   - **浏览器控制台**：在界面「模型与 API 设置」勾选「在浏览器控制台记录 LLM 相关 API 耗时与结果」，打开 F12 可见 `send_message` / `persona_send` / `extract_memory` 等调用的耗时与返回摘要。

3. **本地覆盖（可选）**：在界面「模型与 API 设置」中保存的配置会写入 `%USERPROFILE%\.ruyi72\ruyi72.local.yaml`，并在启动时**合并覆盖**主配置文件中同名的 `llm` 字段（便于在不改仓库内 YAML 的情况下切换模型）。

4. **身份与记忆 Markdown（可选）**：在用户目录 `%USERPROFILE%\.ruyi72\` 放置 `SOUL.md`（智能体性格）、`USER.md`（用户身份）、`MEMORY.md`（手写核心记忆）可分别覆盖默认人格与画像，并注入「核心记忆」段落；亦可在头部「身份与记忆提示词」中查看路径、编辑并保存。内容可能含隐私，请勿在公共环境共享该目录。

5. **访问令牌（可选）**：本机默认 Ollama（`127.0.0.1:11434`）一般**不需要** token。若 `base_url` 指向远程服务、Ollama Cloud 或经需鉴权的反向代理，请设置：
   - 配置项 `llm.api_key`（请求头 `Authorization: Bearer …`），或
   - 环境变量 `OLLAMA_API_KEY`（也可用 `RUYI72_OLLAMA_API_KEY`）。

若出现 **HTTP 502**，多为网关无法连上上游或上游未就绪；在 **Windows** 上还常见 **系统代理（HTTP_PROXY 等）** 把对本机 `127.0.0.1` 的请求错误转发，从而 502。程序对 **localhost / 127.0.0.1** 默认已让 httpx **不使用系统代理**（`trust_env` 为 false）；若仍异常，可在配置中显式设置 `llm.trust_env: false`。**若反代只转发 `/v1`**，可改为 `llm.api_mode: openai` 使用 `/v1/chat/completions`。界面顶部会显示 `api_mode`、`trust_env` 与 API Key 是否已配置（不展示密钥）。

若不存在任何配置文件，将使用程序内建默认值（见 `src/config.py` 中 `RuyiConfig`）。

6. **会话与历史目录（可选）**：默认将每个会话保存到 `%USERPROFILE%\.ruyi72\sessions\<sessionId>\`（含 `meta.json` 与 `messages.json`）。可在配置中设置 `storage.sessions_root` 指向自定义根目录。

7. **闲时自动记忆抽取（可选）**：配置块 `memory_auto_extract`（默认 `enabled: false`）在进程**空闲**时按会话游标从各会话 `messages.json` 增量调用抽取器；游标持久化在 `%USERPROFILE%\.ruyi72\memory_auto_extract_state.json`。字段说明见 [config/ruyi72.example.yaml](config/ruyi72.example.yaml) 与记忆设计 **[v1.0 实现](docs/AI智能体ruyi72%20记忆系统（永驻+事件）设计（v1.0）.md)**；演进目标见 **[v2.0](docs/AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md)**。

8. **内置定时任务（可选）**：配置块 `builtin_scheduler`；计划持久化在会话目录 `scheduled_tasks.json` 与 `%USERPROFILE%\.ruyi72\global_scheduled_tasks.json`，由后端线程在空闲时触发；可通过 `pywebview.api.list_scheduled_tasks` / `save_scheduled_task` / `delete_scheduled_task` 管理。详见 [docs/scheduled-tasks-design.md](docs/scheduled-tasks-design.md) 与 [docs/module-design.md](docs/module-design.md) §14。

## 功能概览

- **标准对话（Chat）**：多轮问答，不自动执行工具；可选 **交互确认卡片**（`action_card`），用户确认后可触发后续回复。
- **ReAct**：**LangChain** `create_agent`（底层 **LangGraph**），工具限于工作区内的 `read_file` / `list_dir` / `write_file` / `run_shell` 等，并可加载技能、浏览/检索记忆；步数受「最大步数」限制。**界面上的逐字流式输出仅拟人模式具备**；Chat / ReAct / 团队为「整轮完成后刷新消息」，但 ReAct 会在等待气泡中显示已等待秒数，并在主窗口通过 `evaluate_js` 推送**步骤摘要**（工具调用、模型轮次等），避免长时间无反馈。
- **拟人模式**：流式输出、可打断/暂停；与团队、知识库会话互斥（见界面与会话类型）。
- **团队会话**：多模型链式委派，槽位与约束见 [docs/agent-team-mode.md](docs/agent-team-mode.md)。
- **知识库会话**：将工作区视为知识库根目录，按预设侧重（收录、摘要、问答等）注入系统提示。
- **工作区**：非团队路径下多数模式需有效目录；工具与目录预览均校验路径，禁止越界访问。
- **记忆**：跨会话结构化存储与检索；支持手动「记忆提取」与可选 **闲时自动抽取**（`memory_auto_extract`）。**实现**见 [docs/AI智能体ruyi72 记忆系统（永驻+事件）设计（v1.0）.md](docs/AI智能体ruyi72%20记忆系统（永驻+事件）设计（v1.0）.md)，**演进目标**见 [docs/AI智能体ruyi72 记忆系统（永驻+事件）设计（v2.0）.md](docs/AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md)。
- **内置定时任务**：会话级与全局计划（`noop` / 向会话追加系统提示等），配置 `builtin_scheduler`；设计见 [docs/scheduled-tasks-design.md](docs/scheduled-tasks-design.md)。
- **界面**：会话列表与全文搜索、主题色、**头部「模型与 API 设置」**与 **「身份与记忆提示词」**（`SOUL.md` / `USER.md` / `MEMORY.md`）、右侧任务上下文与技能列表、提示词模板条、分屏下列出工作区目录元信息（`list_workspace_preview`）、主栏上方可选 **会话形象条**（内置 **像素** 或 **Live2D**，依赖与资源见 [docs/session-avatar-design.md](docs/session-avatar-design.md)）等。
- **助手输出检查（可选）**：配置 `output_review` 后，助手消息可展示 Markdown、自动提取链接、异步存疑与按节自检；见 [docs/助手输出检查设计.md](docs/助手输出检查设计.md)。

模块职责、数据流与文件索引见 **[docs/module-design.md](docs/module-design.md)**。

## 界面说明

- 左侧可**新建 / 切换会话**；每个会话可设置**工作区**（本地文件夹路径），对话与 ReAct 均仅允许访问该目录内的文件（工具会校验路径）。
- **会话形象（可选）**：主栏上方 **形象条** 可切换关闭 / 像素 / Live2D；`avatar_mode` 与 `avatar_ref` 写入会话 `meta.json`，可通过 `pywebview.api.update_session`（及专篇中的 `get_session_avatar_meta` / `set_session_avatar`）更新。资源路径、Cubism 许可与降级规则见 [docs/session-avatar-design.md](docs/session-avatar-design.md)。
- **对话**：仅多轮问答，不执行工具。
- **ReAct**：使用 **LangChain** `create_agent`（底层 **LangGraph**）；`provider=ollama` 时为 **ChatOllama**，云端提供商时为 **OpenAI 兼容**客户端，均与当前 `llm` 配置一致；工具为 `read_file` / `list_dir` / `write_file` / `run_shell`（工作区内）。递归深度与「最大步数」相关，达到上限会停止。

## 文档

设计与模块边界说明集中在 [docs/](docs/)：

- **索引**：[docs/README.md](docs/README.md)（含「参考：行动模式与系统提示词」：长篇行动模式指南与 [docs/系统提示词/](docs/系统提示词/) 下可选用协议片段）
- **模块设计总览**：[docs/module-design.md](docs/module-design.md)
- **团队模式**：[docs/agent-team-mode.md](docs/agent-team-mode.md)
- **记忆系统**：[v1.0 当前实现](docs/AI智能体ruyi72%20记忆系统（永驻+事件）设计（v1.0）.md) · [v2.0 目标架构](docs/AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md)

## 运行

在项目根目录执行：

```text
python app.py
```

首次使用前请确保 **Ollama 服务已启动**（默认 `http://127.0.0.1:11434`）。若连接失败或模型不存在，界面会显示可读错误信息。排查模型调用时可开启 `app.debug` 或 `RUYI72_DEBUG=1`（见上文「配置」第 2 步）。

## 项目结构

```text
agent-ruyi72-desktop-pygui/
├── app.py
├── requirements.txt
├── config/
│   └── ruyi72.example.yaml
├── docs/
│   ├── README.md
│   ├── module-design.md
│   ├── agent-team-mode.md
│   ├── AI智能体ruyi72 记忆系统（永驻+事件）设计（v1.0）.md
│   └── AI智能体ruyi72 记忆系统（永驻+事件）设计（v2.0）.md
├── resources/
│   └── knowledge_base/          # 知识库会话通用与预设提示片段
├── skills/                      # 根目录技能（SKILL.md）
├── src/
│   ├── config.py
│   ├── service/
│   │   └── conversation.py      # 对话编排与 Api 业务核心
│   ├── storage/
│   │   ├── session_store.py
│   │   └── memory_store.py
│   ├── llm/
│   │   ├── ollama.py
│   │   ├── ollama_stream.py
│   │   ├── chat_model.py
│   │   ├── prompts.py
│   │   └── knowledge_prompts.py
│   ├── agent/
│   │   ├── react_lc.py
│   │   ├── react.py
│   │   ├── tools.py
│   │   ├── action_card.py
│   │   ├── persona_runtime.py
│   │   ├── team_turn.py
│   │   ├── memory_extractor.py
│   │   └── memory_tools.py
│   └── skills/
│       └── loader.py
└── web/
    ├── index.html
    ├── style.css
    └── app.js
```

## 许可

与仓库主项目一致。
