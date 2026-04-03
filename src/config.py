"""加载与校验 ruyi72 配置文件。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

_DEFAULT_APP_TITLE = "如意72"


class AppConfig(BaseModel):
    title: str = _DEFAULT_APP_TITLE
    width: int = Field(default=960, ge=400, le=4096)
    height: int = Field(default=640, ge=300, le=4096)


class LLMConfig(BaseModel):
    provider: str = "ollama"
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


class StorageConfig(BaseModel):
    # 为空则使用 ~/.ruyi72/sessions/<sessionId>/
    sessions_root: str = ""


class AgentConfig(BaseModel):
    react_max_steps_default: int = Field(default=8, ge=1, le=200)


class RuyiConfig(BaseModel):
    version: int = 1
    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)


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
    merged: dict[str, Any] = _default_dict()
    for p in config_search_paths():
        try:
            if p.is_file():
                merged = _deep_merge(merged, load_config_file(p))
                break
        except OSError:
            continue
    return RuyiConfig.model_validate(merged)
