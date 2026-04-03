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

## 配置

1. 复制 [config/ruyi72.example.yaml](config/ruyi72.example.yaml) 为以下**任一**位置（按优先级从高到低，命中第一个即生效）：
   - 环境变量 `RUYI72_CONFIG` 指向的绝对/相对路径；
   - 当前工作目录下的 `ruyi72.yaml`；
   - 当前工作目录下的 `config/ruyi72.yaml`；
   - 用户目录 `%USERPROFILE%\.ruyi72\ruyi72.yaml`。

2. 按需修改 `llm.base_url`、`llm.model`、`temperature`、`max_tokens` 以及窗口 `app.title`、`width`、`height`。

3. **访问令牌（可选）**：本机默认 Ollama（`127.0.0.1:11434`）一般**不需要** token。若 `base_url` 指向远程服务、Ollama Cloud 或经需鉴权的反向代理，请设置：
   - 配置项 `llm.api_key`（请求头 `Authorization: Bearer …`），或
   - 环境变量 `OLLAMA_API_KEY`（也可用 `RUYI72_OLLAMA_API_KEY`）。

若出现 **HTTP 502**，多为网关无法连上上游或上游未就绪；在 **Windows** 上还常见 **系统代理（HTTP_PROXY 等）** 把对本机 `127.0.0.1` 的请求错误转发，从而 502。程序对 **localhost / 127.0.0.1** 默认已让 httpx **不使用系统代理**（`trust_env` 为 false）；若仍异常，可在配置中显式设置 `llm.trust_env: false`。**若反代只转发 `/v1`**，可改为 `llm.api_mode: openai` 使用 `/v1/chat/completions`。界面顶部会显示 `api_mode`、`trust_env` 与 API Key 是否已配置（不展示密钥）。

若不存在任何配置文件，将使用程序内建默认值（见 `src/config.py` 中 `RuyiConfig`）。

4. **会话与历史目录（可选）**：默认将每个会话保存到 `%USERPROFILE%\.ruyi72\sessions\<sessionId>\`（含 `meta.json` 与 `messages.json`）。可在配置中设置 `storage.sessions_root` 指向自定义根目录。

## 界面说明

- 左侧可**新建 / 切换会话**；每个会话可设置**工作区**（本地文件夹路径），对话与 ReAct 均仅允许访问该目录内的文件（工具会校验路径）。
- **对话**：仅多轮问答，不执行工具。
- **ReAct**：模型按 JSON 输出调用 `read_file` / `list_dir` / `run_shell`，直至 `finish` 或达到「最大步数」。

## 运行

在项目根目录执行：

```text
python app.py
```

首次使用前请确保 **Ollama 服务已启动**（默认 `http://127.0.0.1:11434`）。若连接失败或模型不存在，界面会显示可读错误信息。

## 项目结构

```text
agent-ruyi72-desktop-pygui/
├── app.py
├── requirements.txt
├── config/ruyi72.example.yaml
├── src/
│   ├── config.py
│   ├── llm/ollama.py
│   ├── storage/session_store.py
│   ├── service/conversation.py
│   └── agent/ (react.py, tools.py)
└── web/
    ├── index.html
    ├── style.css
    └── app.js
```

## 许可

与仓库主项目一致。
