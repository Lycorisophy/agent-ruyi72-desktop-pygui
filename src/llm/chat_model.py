"""从 LLMConfig 构造 LangChain ChatModel（默认 Ollama，便于与 ReAct create_agent 对接）。"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from src.config import LLMConfig
from src.llm.ollama import effective_trust_env, resolve_llm_api_key


def chat_model_from_config(cfg: LLMConfig) -> BaseChatModel:
    """
    ReAct 使用 LangChain；默认 provider=ollama，对应 ChatOllama。
    与 httpx 直连的 api_mode（native/openai）独立，由 langchain-ollama / ollama 客户端访问服务。
    """
    if cfg.provider != "ollama":
        raise ValueError(
            f"ReAct（LangChain）当前仅支持 llm.provider=ollama，收到: {cfg.provider!r}"
        )

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
