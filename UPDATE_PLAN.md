# 如意72 (ruyi72) 桌面AI Agent 更新计划

> 参考项目: Claude Code (npm source map), DeerFlow2 (字节跳动), OpenClaw
> 生成日期: 2025年
> 当前版本: v0.1.0

---

## 项目参考分析

### 1. Claude Code (npm source map 泄露版)

**核心架构:**
```
├── cli.ts              # CLI 入口，命令解析
├── core/
│   ├── index.ts         # 核心逻辑入口
│   ├── permissions.ts  # 权限系统
│   ├── prompt.ts        # Prompt 管理
│   └── history.ts       # 历史记录
├── lib/
│   ├── agent.ts         # Agent 逻辑
│   ├── blocker.ts       # 阻塞检测
│   ├── transporter.ts   # 消息传输
│   └── transporter-http.ts
├── tools/               # 工具定义
│   ├── index.ts
│   ├── bash.ts
│   ├── glob.ts
│   ├── grep.ts
│   ├── read.ts
│   ├── write.ts
│   └── websearch.ts
└── types.ts             # 类型定义
```

**可借鉴特性:**
- **Rule-based 权限系统**: `~/.claude/.claude.json` 定义允许/禁止的操作
- **Permission 验证**: 每次敏感操作前检查权限
- **Compact/Expand 模式**: 简化或详细输出切换
- **内联编辑**: `@` 命令直接编辑文件
- **智能 History**: 按项目/全局分离，markdown 格式存储

---

### 2. DeerFlow2 (字节跳动 B/S 架构)

**核心架构:**
```
├── deer_flow2/
│   ├── app.py                    # Flask/Sanic 主应用
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py         # Agent 基类 (ReAct)
│   │   ├── research_agent.py     # 研究 Agent
│   │   ├── writer_agent.py       # 写作 Agent
│   │   └── executor_agent.py     # 执行 Agent
│   ├── harness/
│   │   ├── __init__.py
│   │   ├── executor.py           # 任务编排器
│   │   └── response_collector.py # 响应收集
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── loop_detector.py      # 循环检测
│   │   ├── token_counter.py      # Token 计数
│   │   ├── memory_manager.py     # 内存管理
│   │   └── audit.py              # 审计日志
│   ├── skills/                   # 技能系统
│   │   ├── __init__.py
│   │   ├── base_skill.py
│   │   ├── file_skill.py
│   │   ├── search_skill.py
│   │   └── web_skill.py
│   └── storage/
│       ├── __init__.py
│       ├── session_store.py      # 会话存储
│       └── file_store.py         # 文件存储
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
└── requirements.txt
```

**可借鉴特性:**
- **Middleware Pipeline**: 链式中间件处理请求/响应
- **多 Agent 协作**: Research → Write → Execute 工作流
- **Harness 架构**: 解耦的任务编排系统
- **Skill 抽象层**: 统一的技能接口
- **SQLite 持久化**: 会话和文件存储

---

### 3. OpenClaw (已安装本地)

**核心架构:**
```
openclaw/
├── openclaw/                    # 主包
│   ├── __init__.py
│   ├── cli.py                  # CLI 入口
│   ├── config.py               # 配置管理
│   ├── agent.py                # Agent 核心
│   ├── plugins/
│   │   ├── __init__.py
│   │   ├── plugin_manager.py  # 插件管理器
│   │   ├── base_plugin.py      # 插件基类
│   │   └── ...                 # 内置插件
│   └── skills/
│       ├── skill_manager.py    # 技能管理器
│       └── ...                 # 内置技能
├── plugins/                     # 用户插件目录
├── skills/                      # 用户技能目录
├── configs/                     # 配置目录
└── README.md
```

**可借鉴特性:**
- **SKILL.md 格式**: 声明式技能定义
- **Plugin 系统**: 热插拔插件架构
- **Config 分层**: defaults → system → user
- **MCP 协议支持**: 外部工具集成

---

## 当前项目状态 (v0.1.0)

```
agent-ruyi72-desktop-pygui/
├── src/
│   ├── __init__.py
│   ├── config.py           # ✓ 已实现
│   ├── logger.py          # ✓ 已实现
│   ├── llm/
│   │   └── ollama.py       # ✓ 已实现
│   ├── agent/
│   │   ├── base.py        # ✓ 已实现
│   │   └── runner.py      # ✓ 已实现
│   ├── memory/
│   │   └── session.py      # ✓ 已实现
│   └── skills/
│       ├── __init__.py
│       ├── base.py         # ✓ 已实现
│       ├── builtin.py      # ✓ 已实现
│       ├── registry.py     # ✓ 已实现
│       └── manager.py      # ✓ 已实现
├── backend/
│   └── server.py           # ✓ 已实现
├── frontend/
│   ├── index.html         # ✓ 已实现
│   ├── style.css          # ✓ 已实现
│   └── app.js             # ✓ 已实现
├── skills/                  # ✓ 已实现
├── app.py                  # ✓ PyWebView 主应用
├── requirements.txt        # ✓ 已实现
└── README.md               # ✓ 已实现
```

---

## 更新计划

### Phase 1: 权限系统 ⭐⭐⭐ (高优先级)

**目标**: 参考 Claude Code 的 rule-based 权限系统

**实现内容:**
- [ ] 权限配置文件 `~/.ruyi72/permissions.json`
- [ ] 权限类别:
  - `commands`: 允许执行的命令白名单
  - `paths`: 允许访问的路径白名单
  - `network`: 网络请求权限
  - `dangerous`: 危险操作确认
- [ ] 权限验证中间件
- [ ] 交互式权限申请界面

**文件结构:**
```
src/security/
├── __init__.py
├── permissions.py      # 权限配置和验证
├── sandbox.py          # 沙箱执行环境
└── validator.py        # 输入验证器
```

**权限配置示例:**
```json
{
  "version": 1,
  "commands": {
    "allowed": ["git", "python", "node", "npm", "uv"],
    "denied": ["rm -rf /", "format", "del /f /s /q"],
    "require_confirmation": ["rm", "del", "drop", "truncate"]
  },
  "paths": {
    "allowed": ["C:/project", "D:/workspace", "~"],
    "blocked": ["C:/Windows/System32", "C:/$Recycle.Bin"]
  },
  "network": {
    "allowed_domains": ["api.github.com", "ollama.ai"],
    "require_confirmation": true
  }
}
```

---

### Phase 2: 中间件系统 ⭐⭐⭐ (高优先级)

**目标**: 参考 DeerFlow2 的 middleware pipeline

**实现内容:**
- [ ] 中间件基类和接口
- [ ] 内置中间件:
  - `LoopDetector`: 检测重复执行模式
  - `TokenCounter`: Token 使用统计
  - `MemoryManager`: 上下文窗口管理
  - `AuditLogger`: 操作审计日志
- [ ] 中间件注册和排序
- [ ] 中间件配置系统

**文件结构:**
```
src/middleware/
├── __init__.py
├── base.py             # 中间件基类
├── chain.py            # 中间件链
├── loop_detector.py    # 循环检测
├── token_counter.py     # Token 计数
├── memory_manager.py    # 内存管理
└── audit.py            # 审计日志
```

---

### Phase 3: 会话持久化 (SQLite) ⭐⭐ (中优先级)

**目标**: 参考 DeerFlow2 的存储系统

**实现内容:**
- [ ] SQLite 数据库设计
- [ ] 会话表: id, title, created_at, updated_at, metadata
- [ ] 消息表: id, session_id, role, content, timestamp, tokens
- [ ] 会话管理器 (CRUD)
- [ ] 历史消息导出 (JSON/Markdown)

**数据库 Schema:**
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT  -- JSON
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    role TEXT,  -- 'user' | 'assistant' | 'system'
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tokens INTEGER,
    metadata TEXT  -- JSON
);

CREATE INDEX idx_messages_session ON messages(session_id);
```

---

### Phase 4: 插件系统 ⭐⭐ (中优先级)

**目标**: 参考 OpenClaw 的插件架构

**实现内容:**
- [ ] 插件基类 `BasePlugin`
- [ ] 插件管理器 `PluginManager`
- [ ] 插件发现机制 (扫描 plugins/ 目录)
- [ ] 插件生命周期管理
- [ ] 内置插件:
  - `FileExplorer`: 文件浏览器
  - `Terminal`: 终端模拟器
  - `GitUI`: Git 图形界面

**文件结构:**
```
plugins/
├── __init__.py
├── base.py              # 插件基类
├── manager.py           # 插件管理器
├── builtin/             # 内置插件
│   ├── file_explorer.py
│   ├── terminal.py
│   └── git_ui.py
└── README.md

src/plugins/
├── __init__.py
├── loader.py            # 插件加载器
└── registry.py          # 插件注册表
```

---

### Phase 5: MCP 支持 ⭐⭐ (中优先级)

**目标**: 支持 Model Context Protocol

**实现内容:**
- [ ] MCP 客户端实现
- [ ] MCP 服务器发现
- [ ] MCP 工具映射到 ruyi72 skills
- [ ] MCP 资源订阅
- [ ] 内置 MCP 服务器示例

**MCP 配置:**
```json
{
  "mcp": {
    "servers": [
      {
        "name": "filesystem",
        "command": "npx",
        "args": ["@modelcontextprotocol/server-filesystem", "C:/"]
      },
      {
        "name": "github",
        "command": "npx",
        "args": ["@modelcontextprotocol/server-github"],
        "env": {
          "GITHUB_TOKEN": "${GITHUB_TOKEN}"
        }
      }
    ]
  }
}
```

---

### Phase 6: 多渠道集成 ⭐ (低优先级)

**目标**: 支持多种前端渠道

**实现内容:**
- [ ] REST API 服务化
- [ ] WebSocket 实时通信
- [ ] CLI 终端界面
- [ ] API 认证系统

**架构:**
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Web UI    │     │    CLI      │     │  REST API   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Gateway    │
                    │  (WebSocket)│
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Core Agent │
                    └─────────────┘
```

---

### Phase 7: 高级功能 ⭐ (后期)

**目标**: 增强用户体验

**实现内容:**
- [ ] 上下文压缩 (类似 Claude 的 summarization)
- [ ] 思维链可视化
- [ ] 代码执行沙箱 (Docker/Basalang)
- [ ] 多模态支持 (图片理解)
- [ ] Agent 协作模式

---

## 配置文件扩展

### 统一配置格式

```yaml
# ruyi72.yaml
version: 1

# LLM 配置
llm:
  provider: ollama
  model: qwen2.5:7b
  base_url: http://localhost:11434
  temperature: 0.7
  max_tokens: 4096

# 权限配置
permissions:
  config_file: ~/.ruyi72/permissions.json
  default_policy: ask  # allow | deny | ask

# 中间件配置
middleware:
  - name: loop_detector
    enabled: true
    max_iterations: 100
  - name: token_counter
    enabled: true
    warn_threshold: 8000
  - name: memory_manager
    enabled: true
    max_context: 10
  - name: audit
    enabled: true
    log_file: ~/.ruyi72/logs/audit.jsonl

# 插件配置
plugins:
  auto_load: true
  dirs:
    - ~/.ruyi72/plugins
    - ./plugins

# MCP 配置
mcp:
  enabled: false
  servers: []

# 存储配置
storage:
  type: sqlite
  path: ~/.ruyi72/sessions.db

# UI 配置
ui:
  theme: auto  # light | dark | auto
  language: zh-CN
  compact_mode: false
```

---

## 测试计划

### 单元测试
```bash
pytest tests/unit/
├── test_permissions.py
├── test_middleware.py
├── test_skills.py
└── test_storage.py
```

### 集成测试
```bash
pytest tests/integration/
├── test_agent_flow.py
├── test_skill_execution.py
└── test_mcp_integration.py
```

### E2E 测试
- PyWebView UI 测试
- CLI 交互测试
- API 端点测试

---

## 版本路线图

| 版本 | 主要功能 | 目标日期 |
|------|---------|---------|
| v0.1.0 | 基础框架、Skill 系统 | ✅ 已完成 |
| v0.2.0 | 权限系统、中间件 | Q1 2025 |
| v0.3.0 | SQLite 持久化 | Q1 2025 |
| v0.4.0 | 插件系统 | Q2 2025 |
| v0.5.0 | MCP 支持 | Q2 2025 |
| v0.6.0 | 多渠道集成 | Q3 2025 |
| v1.0.0 | 高级功能、发布 | Q4 2025 |

---

## 参考资源

- [Claude Code GitHub](https://github.com/rishikavikode/Claude-Code)
- [DeerFlow2 GitHub](https://github.com/bytedance/DeerFlow2)
- [OpenClaw GitHub](https://github.com/nicehero/OpenClaw)
- [Model Context Protocol](https://modelcontextprotocol.io)

---

*本文档由 Matrix Agent 生成*
