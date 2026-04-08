# 如意72 文档索引

本目录存放设计与说明类 Markdown，与代码内的实现注释互补：**快速了解架构与模块边界请读 [module-design.md](module-design.md)**；团队编排、记忆与内置定时任务有独立专篇或设计稿。

| 文档 | 说明 | 适合读者 |
|------|------|----------|
| [module-design.md](module-design.md) | 各功能模块职责、关键文件、数据流与边界（总览） | 贡献者、二次开发、排障 |
| [agent-team-mode.md](agent-team-mode.md) | 链式多 Agent 团队模式：槽位、委派规则、与 `llm` 区分 | 需要改团队行为或配置时 |
| [memory-system.md](memory-system.md) | 长期记忆：事实/事件/关系模型、存储与检索策略 | 需要扩展记忆或对接抽取流程时 |
| [scheduled-tasks-design.md](scheduled-tasks-design.md) | 会话级与全局内置定时任务：概念、持久化、调度语义与 API 说明 | 扩展调度行为或 UI 前阅读 |

根目录 [README.md](../README.md) 提供安装、配置、运行与功能清单；细节以本目录为准。
