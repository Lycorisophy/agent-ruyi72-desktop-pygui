# 如意72 文档索引

本目录存放设计与说明类 Markdown，与代码内的实现注释互补：**快速了解架构与模块边界请读 [module-design.md](module-design.md)**；团队编排、记忆与内置定时任务有独立专篇或设计稿。

| 文档 | 说明 | 适合读者 |
|------|------|----------|
| [module-design.md](module-design.md) | 各功能模块职责、关键文件、数据流与边界（总览） | 贡献者、二次开发、排障 |
| [agent-assisted-development-sop.md](agent-assisted-development-sop.md) | **Agent 辅助开发 SOP**：DST→PRD 五步法→设计五步法→实现/测试/修复/闭环与反馈 | 需求到交付全流程对齐、与 Agent 协作时 |
| [服务端研发AI辅助工作范式.md](服务端研发AI辅助工作范式.md) | **服务端视角**：需求澄清→PRD 实例化→设计对齐→编码/智能测试/闭环；工具链与度量 | 后端、分布式与 API 研发使用 AI 时 |
| [企业级Agent工具调用综合方案.md](企业级Agent工具调用综合方案.md) | **企业级工具调用**：L0–L4 流式解析、解析侧纠错（L1）、执行侧重试与错误回灌（R）、可观测与安全闸门；文末与本仓库 ReAct（`create_agent`）对照 | 架构、Agent 基础设施、评估演进路线时 |
| [对话状态追踪设计.md](对话状态追踪设计.md) | **全模式**统一 `DialoguePhase`、事件、`dialogue_state.json`（含 `state_extension`：团队槽位、ReAct 步序）；Web 状态条展示 | 编排会话与 UI、断线恢复、可观测性时 |
| [agent-team-mode.md](agent-team-mode.md) | 链式多 Agent 团队模式：槽位、委派规则、与 `llm` 区分 | 需要改团队行为或配置时 |
| [AI智能体ruyi72 记忆系统（永驻+事件）设计（v1.0）.md](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v1.0）.md) | **当前实现**：JSONL、抽取与检索、ReAct 工具与闲时任务 | 对照代码与行为、修 bug |
| [AI智能体ruyi72 记忆系统（永驻+事件）设计（v2.0）.md](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v2.0）.md) | **目标架构**：事实三级、SQLite+FTS5、向量、身份 Markdown 治理、迁移与工具契约 | 评审演进、拆分迭代、约定抽取 JSON |
| [AI智能体ruyi72 记忆系统（永驻+事件）设计（v3.0）.md](AI智能体ruyi72%20记忆系统（永驻+事件）设计（v3.0）.md) | **三期演进**：事件 `world_kind`（真实/虚构/假设）、`temporal_kind`（过去/计划未来等）、计划窗口与检索注入策略；附其它可演进项 | 评审事件本体与里程碑 M7+ |
| [scheduled-tasks-design.md](scheduled-tasks-design.md) | 会话级与全局内置定时任务：概念、持久化、调度语义与 API 说明 | 扩展调度行为或 UI 前阅读 |

根目录 [README.md](../README.md) 提供安装、配置、运行与功能清单；细节以本目录为准。
