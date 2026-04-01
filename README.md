# 如意 Agent (ruyi72)

> 基于 PyWebView + FastAPI + Ollama 的桌面 AI Agent 应用

如意72桌面版，采用前后端一体化架构，支持技能系统扩展。

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    桌面窗口 (PyWebView)                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   Web 前端 (HTML/CSS/JS)              │   │
│  │  [对话]  [技能]  [设置]                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↕ JavaScript API                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Python 绑定 (PyWebView)                 │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI 后端 (独立线程)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  /api/chat  /api/skills  /api/session              │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Agent Runner                        │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │   ReAct 循环: Think → Act → Observe         │     │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  SkillManager (技能系统)                             │   │
│  │  内置技能 + 自定义 SKILL.md 技能                     │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ollama (本地 LLM)                        │
│              qwen3.5:35b-a3b-q8_0-nothink                   │
└─────────────────────────────────────────────────────────────┘
```

## 项目结构

```
agent-ruyi72-desktop-pygui/
├── app.py                    # PyWebView 入口
├── requirements.txt          # Python 依赖
│
├── src/                      # 核心源码
│   ├── __init__.py
│   ├── config.py             # 配置管理
│   ├── logger.py             # 日志系统
│   ├── llm/                  # LLM 接口
│   │   ├── ollama.py         # Ollama 提供商
│   │   └── prompts.py        # 提示词模板
│   ├── agent/                # Agent 系统
│   │   ├── base.py           # Agent 基类
│   │   └── runner.py         # Agent 运行器
│   ├── skills/               # 技能系统
│   │   ├── base.py           # 技能基类
│   │   ├── manager.py        # 技能管理器
│   │   ├── registry.py       # 技能注册表
│   │   ├── builtin.py        # 内置技能
│   │   └── ...
│   └── memory/               # 记忆系统
│       └── session.py        # 会话记忆
│
├── skills/                   # 自定义技能目录
│   ├── filesystem/           # 文件系统技能
│   │   └── file_tree/        # 文件树技能
│   │       ├── SKILL.md
│   │       ├── file_tree.py
│   │       └── file_tree.ps1
│   ├── code/                 # 代码技能
│   │   └── code_review/
│   ├── web/                  # Web 技能
│   │   └── url_info/
│   └── system/               # 系统技能
│       └── system_info/
│
├── config/
│   └── config.yaml           # 配置文件
│
├── frontend/                 # Web 前端
│   ├── index.html
│   ├── css/
│   │   └── main.css
│   └── js/
│       └── app.js
│
└── backend/
    └── server.py             # FastAPI 后端
```

## 技能系统

### 内置技能

| 技能名 | 描述 | 类别 |
|--------|------|------|
| Read | 读取文件 | filesystem |
| Write | 写入文件 | filesystem |
| Glob | 文件搜索 | filesystem |
| Grep | 文本搜索 | filesystem |
| Bash | 执行命令 | execution |
| Python | 执行 Python | execution |
| WebSearch | 网页搜索 | web |
| WebFetch | 获取网页 | web |

### 自定义技能

在 `skills/` 目录下创建技能：

```
skills/
└── my_skill/
    ├── SKILL.md      # 技能定义
    └── script.py     # 技能脚本 (Python 或 PowerShell)
```

### SKILL.md 格式

```markdown
# 技能名称

## Skill: my_skill

技能唯一标识符。

## Description

技能的详细描述。

## Parameters

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| param1 | string | 是 | - | 参数1描述 |

## Examples

```
my_skill param1="value1"
```

## Triggers

- 触发词1
- 触发词2
```

### 脚本协议

脚本通过 stdin/stdout 传递 JSON：

**输入：**
```json
{"param1": "value1", "param2": 123}
```

**输出：**
```json
{
    "success": true,
    "output": "执行结果",
    "error": null,
    "metadata": {"execution_time": 1.23}
}
```

## 安装与运行

### 前置要求

- Python 3.10+
- [Ollama](https://ollama.ai/) 已安装并运行
- 模型已下载：`ollama pull qwen3.5:35b-a3b-q8_0-nothink`

### 安装步骤

```bash
# 1. 进入项目目录
cd agent-ruyi72-desktop-pygui

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Linux/macOS

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动 Ollama（如果未运行）
ollama serve

# 6. 运行应用
python app.py
```

### 配置

编辑 `config/config.yaml`：

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "qwen3.5:35b-a3b-q8_0-nothink"

agent:
  default_mode: "general"
  max_iterations: 50
```

## 打包为桌面应用

### PyInstaller 打包

```bash
# 1. 安装 PyInstaller
pip install pyinstaller

# 2. 创建 spec 文件 (build.spec)
pyinstaller --name ruyi72 --windowed --add-data "frontend;frontend" --add-data "skills;skills" --add-data "config;config" app.py

# 3. 或者直接打包
pyinstaller app.py --onedir --noconfirm
```

### Windows 打包命令

```bash
pyinstaller app.py ^
    --name "ruyi72" ^
    --windowed ^
    --add-data "frontend;frontend" ^
    --add-data "skills;skills" ^
    --add-data "config;config" ^
    --hidden-import "uvicorn" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols" ^
    --hidden-import "uvicorn.protocols.http" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.protocols.websockets" ^
    --hidden-import "uvicorn.protocols.websockets.auto" ^
    --hidden-import "uvicorn.lifespan" ^
    --hidden-import "uvicorn.lifespan.on" ^
    --hidden-import "fastapi" ^
    --hidden-import "starlette"
```

## API 接口

### 对话接口

```bash
# 非流式
POST /api/chat
{
    "message": "你好",
    "agent_mode": "general",
    "session_id": "default"
}

# 流式
POST /api/chat/stream
# 返回 SSE 流
```

### 技能接口

```bash
# 列出技能
GET /api/skills

# 执行技能
POST /api/skills/execute
{
    "skill_name": "Read",
    "params": {"path": "/tmp/test.txt"}
}
```

### 会话接口

```bash
# 获取历史
GET /api/session/{session_id}/history

# 清空会话
DELETE /api/session/{session_id}
```

### 系统接口

```bash
# 系统信息
GET /api/system/info

# 健康检查
GET /api/system/health
```

## 开发指南

### 添加新技能

1. 在 `skills/` 下创建目录
2. 添加 `SKILL.md` 定义文件
3. 添加执行脚本 `.py` 或 `.ps1`
4. 技能自动加载

### 修改前端

编辑 `frontend/` 目录下的文件，刷新页面即可生效。

### 调试后端

```bash
# 独立运行后端
cd agent-ruyi72-desktop-pygui
python backend/server.py
```

## 常见问题

### Q: PyWebView 窗口无法打开
**A:** 确保已安装 WebView2 运行时（Windows 11 已内置）

### Q: Ollama 连接失败
**A:** 确保 Ollama 服务运行中：
```bash
curl http://localhost:11434/api/tags
```

### Q: 技能执行失败
**A:** 检查技能脚本是否有执行权限

## 许可证

MIT License

## 相关资源

- [PyWebView 文档](https://pywebview.flowrl.com/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Ollama 文档](https://github.com/ollama/ollama)
