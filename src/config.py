"""加载与校验 ruyi72 配置文件。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

_DEFAULT_APP_TITLE = "如意72"

# OpenAI 兼容 HTTP 的云厂商（非 Ollama 时仅走 /v1/chat/completions）
LLMProvider = Literal["ollama", "minimax", "deepseek", "qwen"]

LOCAL_OVERRIDE_REL = Path(".ruyi72") / "ruyi72.local.yaml"


def local_override_config_path() -> Path:
    """界面保存的 LLM 等覆盖层，合并优先级高于首个命中的主 YAML。"""
    return Path.home() / LOCAL_OVERRIDE_REL


def llm_provider_presets() -> dict[str, dict[str, str]]:
    """供前端与文档展示的默认 base_url / 示例 model。"""
    return {
        "ollama": {
            "base_url": "http://127.0.0.1:11434",
            "model": "llama3.2",
            "hint": "本地 Ollama；api_mode 可选 native 或 openai",
        },
        "minimax": {
            "base_url": "https://api.minimax.chat/v1",
            "model": "abab6.5s-chat",
            "hint": "MiniMax OpenAI 兼容接口；需 api_key",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "hint": "DeepSeek；需 api_key",
        },
        "qwen": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-turbo",
            "hint": "阿里云 DashScope 兼容模式；需 api_key（或 DASHSCOPE_API_KEY）",
        },
    }


class AppConfig(BaseModel):
    title: str = _DEFAULT_APP_TITLE
    width: int = Field(default=960, ge=400, le=4096)
    height: int = Field(default=640, ge=300, le=4096)
    # True 或环境变量 RUYI72_DEBUG=1 时控制台输出 LLM 请求/响应摘要（可能含对话片段）
    debug: bool = False


class LLMConfig(BaseModel):
    provider: LLMProvider = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3.2"
    temperature: float = Field(default=0.6, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=262144)
    # 本地 Ollama 一般无需填写；远程 / Ollama Cloud / 需鉴权的反代可填，或设环境变量 OLLAMA_API_KEY
    api_key: str | None = None
    # native: POST /api/chat（默认）；openai: POST /v1/chat/completions（部分网关/兼容层只转发 /v1）
    api_mode: Literal["native", "openai"] = "native"
    # None=自动：本机 loopback 不走系统代理（避免 HTTP(S)_PROXY 导致 502）；true/false 可强制
    trust_env: bool | None = None
    # True 或环境变量 RUYI72_LLM_LOG=1 时终端 INFO 输出每条 LLM 调用摘要（不含全文 prompt）；与 app.debug 全量 dump 独立
    log_summary: bool = False

    @model_validator(mode="after")
    def _cloud_forces_openai_mode(self) -> LLMConfig:
        if self.provider in ("minimax", "deepseek", "qwen") and self.api_mode != "openai":
            return self.model_copy(update={"api_mode": "openai"})
        return self


class StorageConfig(BaseModel):
    # 为空则使用 ~/.ruyi72/sessions/<sessionId>/
    sessions_root: str = ""


class AgentConfig(BaseModel):
    react_max_steps_default: int = Field(default=8, ge=1, le=200)


class PersonaConfig(BaseModel):
    """拟人模式：流式、可选流式推理、主动发言等。"""

    stream_think: bool = Field(default=True, description="native 模式下是否向 Ollama 请求 think 流")
    proactive_enabled: bool = False
    proactive_idle_seconds: float = Field(default=120.0, ge=30.0, le=86400.0)
    proactive_max_per_day: int = Field(default=5, ge=0, le=100)


class TeamModelEntry(BaseModel):
    """团队链路槽位：顺序对应 A1、A2…；与顶层 llm 合并后仅 model 不同。"""

    model: str = Field(
        min_length=1,
        description="Ollama 等可用的模型标识；去空白后须非空。",
    )
    suitable_for: str = Field(
        default="",
        description="用户填写：该模型适合做什么，会进入团队模式系统提示词（所有槽位可见）。",
    )

    @field_validator("model", mode="before")
    @classmethod
    def model_strip_nonempty(cls, v: Any) -> str:
        if v is None:
            raise ValueError("team.models 条目的 model 不能省略或为 null")
        s = str(v).strip()
        if not s:
            raise ValueError("team.models 每条目的 model 必须为非空字符串（去空白后不能为空）")
        return s

    @field_validator("suitable_for", mode="before")
    @classmethod
    def suitable_for_strip(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()


class TeamConfig(BaseModel):
    """至少 2 条 models 时才允许团队会话；N ≤ min(4, len(models))。"""

    models: list[TeamModelEntry] = Field(default_factory=list)


class EmbeddingConfig(BaseModel):
    """Ollama /api/embed；base_url 为空时沿用 llm.base_url。"""

    model: str = "qwen3-embedding:8b"
    base_url: str = ""


class MemoryConfig(BaseModel):
    """长期记忆：向量索引与存储后端（见 docs 记忆 v2）。"""

    vector_enabled: bool = False
    # sqlite 路径；空则使用 ~/.ruyi72/memory/memory.db
    sqlite_path: str = ""
    # jsonl | sqlite | dual（dual 为过渡期双写）
    backend: Literal["jsonl", "sqlite", "dual"] = "jsonl"
    # 为 True 时，每次保存会话消息会重建该会话在 memory.db 中的 FTS 索引（见 memory_messages）
    messages_index_enabled: bool = False
    # 主动/闲时记忆抽取单次 LLM 请求的读超时（秒）；大模型或长文本可调高
    extract_llm_timeout_sec: int = Field(default=300, ge=60, le=3600)
    # 单次抽取用户文本最大字符数（含中英文）；超出则拒绝请求，避免超大上下文拖慢或超时
    extract_max_input_chars: int = Field(default=16000, ge=2000, le=500000)
    # 抽取专用生成上限（与主对话 llm.max_tokens 独立，仅影响记忆抽取请求）
    extract_max_tokens: int = Field(default=4096, ge=256, le=131072)
    # 会话冷启动（build_memory_bootstrap_block）：为 True 时事件中排除 world_kind=fictional（v3.0）
    bootstrap_exclude_fictional_events: bool = True


class MemoryAutoExtractConfig(BaseModel):
    """闲时从会话历史自动抽取记忆（游标去重）；默认关闭以免消耗 token。"""

    enabled: bool = False
    interval_sec: int = Field(default=180, ge=30, le=86400)
    max_chars_per_batch: int = Field(default=16000, ge=2000, le=200000)
    min_chars_to_extract: int = Field(default=40, ge=0, le=5000)
    max_sessions_scanned: int = Field(default=30, ge=1, le=500)


class BuiltinSchedulerConfig(BaseModel):
    """内置会话级 + 全局定时任务调度线程。"""

    enabled: bool = True
    tick_interval_sec: int = Field(default=20, ge=5, le=300)
    max_sessions_scanned: int = Field(default=50, ge=1, le=500)
    max_tasks_per_tick: int = Field(default=3, ge=1, le=20)


class RuyiConfig(BaseModel):
    version: int = 1
    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    persona: PersonaConfig = Field(default_factory=PersonaConfig)
    team: TeamConfig = Field(default_factory=TeamConfig)
    memory_auto_extract: MemoryAutoExtractConfig = Field(
        default_factory=MemoryAutoExtractConfig
    )
    builtin_scheduler: BuiltinSchedulerConfig = Field(
        default_factory=BuiltinSchedulerConfig
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _default_dict() -> dict[str, Any]:
    return RuyiConfig().model_dump()


def config_search_paths() -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("RUYI72_CONFIG", "").strip()
    if env:
        paths.append(Path(env).expanduser())
    paths.append(Path.cwd() / "ruyi72.yaml")
    paths.append(Path.cwd() / "config" / "ruyi72.yaml")
    home = Path.home()
    paths.append(home / ".ruyi72" / "ruyi72.yaml")
    return paths


def load_config_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"配置文件根节点必须是映射: {path}")
    return data


def load_config() -> RuyiConfig:
    """
    合并默认配置与首个命中的主 YAML，再合并 ~/.ruyi72/ruyi72.local.yaml（若存在）。
    界面保存写入 local 文件，同名字段覆盖主配置。
    """
    merged: dict[str, Any] = _default_dict()
    for p in config_search_paths():
        try:
            if p.is_file():
                merged = _deep_merge(merged, load_config_file(p))
                break
        except OSError:
            continue
    local = local_override_config_path()
    try:
        if local.is_file():
            merged = _deep_merge(merged, load_config_file(local))
    except OSError:
        pass
    return RuyiConfig.model_validate(merged)


def embedding_http_llm_cfg(cfg: RuyiConfig) -> LLMConfig:
    """供 /api/embed 请求：可单独指定 embedding.base_url。"""
    u = (cfg.embedding.base_url or "").strip()
    if u:
        return cfg.llm.model_copy(update={"base_url": u})
    return cfg.llm


def save_llm_local_yaml(llm: LLMConfig) -> Path:
    """将 llm 块写入 ~/.ruyi72/ruyi72.local.yaml（覆盖同文件中的 llm）。"""
    path = local_override_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    try:
        if path.is_file():
            existing = load_config_file(path)
            if not isinstance(existing, dict):
                existing = {}
    except OSError:
        existing = {}
    existing["version"] = existing.get("version") or 1
    existing["llm"] = llm.model_dump(mode="json")
    text = yaml.safe_dump(
        existing,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    path.write_text(text, encoding="utf-8")
    return path
