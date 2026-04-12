---
name: ruyi72-project-overview
description: >-
  提供如意72（agent-ruyi72-desktop-pygui）桌面 Agent 项目的架构概要、模块边界与文档索引；只读，无脚本。
  用户问本项目架构、模块职责、技术栈、数据流、会话与配置目录、ReAct/拟人/团队、上下文压缩、助手输出检查、文档在哪时使用。
  Use when the user asks what this project is, how modules fit together, tech stack, data flow,
  where sessions/config live, ruyi72 overview, or for a high-level design summary of this repository.
---

# ruyi72 项目概要（safe）

**风险等级**：`safe(0)` — 仅文档与索引，不执行命令、不访问用户磁盘业务数据。

## 何时使用

- 用户询问：**本项目是做什么的**、**架构**、**模块职责**、**技术栈**、**会话/配置存在哪**、**和 ReAct/拟人/团队的关系**。
- 需要快速对齐 **文档入口**（`docs/module-design.md` 等）而不翻完整仓库时。

## 如何回答

1. **优先阅读** 与本 skill 同目录的 [OVERVIEW.md](OVERVIEW.md)（概要设计正文）。
2. 需要细节时，按 OVERVIEW 中的「权威文档索引」打开仓库内对应 `docs/*.md` 或 `README.md`。
3. 不要编造未在文档或源码中出现的路径；不确定时说明「以源码为准」并指出应查看的文件。

## 开发新功能后的文档检查（Agent 必做）

完成或合并一项**用户可见或架构相关**的改动后，在收尾时**至少检查一遍**是否需更新：

| 变更类型 | 建议更新 |
|----------|----------|
| 新模块、新数据文件、新 API 行为 | `docs/module-design.md` 相应节；必要时 [OVERVIEW.md](OVERVIEW.md) |
| 配置项新增/重命名 | `src/config.py` / `config/ruyi72.example.yaml` 注释 |
| 用户可感知功能列表 | 根目录 `README.md`「功能概览」等 |
| 侧栏/会话形象、Live2D、像素、`avatar_*` | `docs/session-avatar-design.md`；`docs/module-design.md` §3 |
| 新增/修改 `docs/系统提示词/` 或《行动模式》指南 | `docs/README.md`「参考：行动模式与系统提示词」 |
| 仅内部重构、无行为变化 | 可不更新对外文档 |

若更新了概要内容，**同步修订 [OVERVIEW.md](OVERVIEW.md)**，保持与本 skill 描述一致。

## 与其它技能的区别

- 本 skill **不**替代 `load_skill` 加载的业务技能（如 `browse-memory`）；仅服务「理解本仓库自身」的问答。
- 用户问的是**业务工作区里的项目**时，不要用本 skill 冒充；仅当上下文明确是 **如意72 / agent-ruyi72-desktop-pygui 本仓库** 时使用。
