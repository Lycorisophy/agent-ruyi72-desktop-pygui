"""从 LLMConfig 构造 LangChain ChatModel（Ollama 或 OpenAI 兼容云 API）。"""

from __future__ import annotations

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None  # type: ignore[misc, assignment]

from src.config import LLMConfig
from src.llm.ollama import effective_trust_env, is_openai_cloud, resolve_llm_api_key


def _openai_base_for_langchain(cfg: LLMConfig) -> str:
    """ChatOpenAI 的 base_url 需含 /v1 后缀（库会再请求 chat/completions）。"""
    b = cfg.base_url.rstrip("/")
    if b.endswith("/v1"):
        return b
    return b + "/v1"


def chat_model_from_config(cfg: LLMConfig) -> BaseChatModel:
    """
    ReAct 使用 LangChain：Ollama 用 ChatOllama；MiniMax / DeepSeek / 通义千问 用 ChatOpenAI 兼容层。
    """
    if is_openai_cloud(cfg):
        if ChatOpenAI is None:
            raise ValueError(
                "使用云端模型需要安装 langchain-openai：pip install langchain-openai"
            )
        key = resolve_llm_api_key(cfg)
        if not key:
            raise ValueError(
                f"llm.provider={cfg.provider!r} 需要配置 api_key 或对应环境变量。"
            )
        trust = effective_trust_env(cfg)
        http_client = httpx.Client(
            trust_env=trust,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        base = _openai_base_for_langchain(cfg)
        try:
            return ChatOpenAI(
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                api_key=key,
                base_url=base,
                http_client=http_client,
            )
        except TypeError:
            return ChatOpenAI(
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                openai_api_key=key,
                openai_api_base=base,
                http_client=http_client,
            )

    if cfg.provider != "ollama":
        raise ValueError(f"ReAct（LangChain）不支持的 llm.provider: {cfg.provider!r}")

    trust = effective_trust_env(cfg)
    headers: dict[str, str] = {}
    key = resolve_llm_api_key(cfg)
    if key:
        headers["Authorization"] = f"Bearer {key}"

    sync_kw: dict = {"trust_env": trust}
    if headers:
        sync_kw["headers"] = headers

    kw: dict = {
        "base_url": cfg.base_url.rstrip("/"),
        "model": cfg.model,
        "temperature": cfg.temperature,
        "num_predict": cfg.max_tokens,
        "sync_client_kwargs": sync_kw,
    }
    try:
        return ChatOllama(**kw, reasoning=False)
    except TypeError:
        return ChatOllama(**kw)
