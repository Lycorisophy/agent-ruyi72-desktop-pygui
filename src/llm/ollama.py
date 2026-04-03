"""Ollama HTTP 客户端：原生 /api/chat 或 OpenAI 兼容 /v1/chat/completions。"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from src.config import LLMConfig


def resolve_llm_api_key(cfg: LLMConfig) -> str | None:
    """配置文件 api_key 优先，否则读环境变量 OLLAMA_API_KEY / RUYI72_OLLAMA_API_KEY。"""
    if cfg.api_key and str(cfg.api_key).strip():
        return str(cfg.api_key).strip()
    for name in ("OLLAMA_API_KEY", "RUYI72_OLLAMA_API_KEY"):
        v = os.environ.get(name, "").strip()
        if v:
            return v
    return None


def effective_trust_env(cfg: LLMConfig) -> bool:
    """是否让 httpx 使用系统代理环境变量。本机 loopback 默认 False，避免代理导致 502。"""
    if cfg.trust_env is not None:
        return cfg.trust_env
    host = (urlparse(cfg.base_url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return False
    if host.startswith("127."):
        return False
    return True


def _base_prefix(cfg: LLMConfig) -> str:
    return cfg.base_url.rstrip("/") + "/"


class OllamaClientError(Exception):
    """可展示给用户的 LLM 调用错误。"""


class OllamaClient:
    def __init__(self, cfg: LLMConfig) -> None:
        self._cfg = cfg
        base = _base_prefix(cfg)
        self._native_chat_url = urljoin(base, "api/chat")
        self._openai_chat_url = urljoin(base, "v1/chat/completions")

    def _request_chat_url(self) -> str:
        if self._cfg.api_mode == "openai":
            return self._openai_chat_url
        return self._native_chat_url

    def chat(self, messages: list[dict[str, str]]) -> str:
        if self._cfg.provider != "ollama":
            raise OllamaClientError(f"当前仅支持 provider=ollama，收到: {self._cfg.provider}")

        headers: dict[str, str] = {}
        key = resolve_llm_api_key(self._cfg)
        if key:
            headers["Authorization"] = f"Bearer {key}"

        chat_url = self._request_chat_url()
        trust = effective_trust_env(self._cfg)

        if self._cfg.api_mode == "openai":
            body: dict[str, Any] = {
                "model": self._cfg.model,
                "messages": messages,
                "stream": False,
                "temperature": self._cfg.temperature,
                "max_tokens": self._cfg.max_tokens,
            }
        else:
            body = {
                "model": self._cfg.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self._cfg.temperature,
                    "num_predict": self._cfg.max_tokens,
                },
            }

        try:
            with httpx.Client(
                timeout=httpx.Timeout(120.0, connect=10.0),
                trust_env=trust,
            ) as client:
                r = client.post(chat_url, json=body, headers=headers)
        except httpx.ConnectError as e:
            raise OllamaClientError(
                "无法连接到 Ollama。请确认 Ollama 已启动，且配置中的 base_url 正确。"
                f" ({e!s})"
            ) from e
        except httpx.TimeoutException as e:
            raise OllamaClientError(f"请求超时，请稍后重试或检查模型是否过大。 ({e!s})") from e

        if r.status_code == 404:
            raise OllamaClientError(
                f"未找到接口或模型（HTTP 404）。请求: POST {chat_url}。"
                f" 若使用网关，可尝试将 llm.api_mode 设为 openai（/v1/chat/completions）。"
                f" 并确认已 `ollama pull {self._cfg.model}`。"
            )
        if r.status_code == 502:
            detail = (r.text or "")[:500]
            hint = (
                f"网关或上游不可用（HTTP 502）。请求: POST {chat_url}。\n"
                "常见原因：1) 本机访问仍走了系统代理——可在 ruyi72.yaml 设置 "
                "`llm.trust_env: false`（loopback 默认已关闭代理；若仍 502 请显式设置）；"
                "2) 反代只转发 /v1——尝试 `llm.api_mode: openai`；"
                "3) 上游 Ollama 未启动或地址错误。"
            )
            if key:
                hint += " 若服务端要求鉴权，请确认 api_key / OLLAMA_API_KEY 正确。"
            raise OllamaClientError(hint + (f"\n详情: {detail}" if detail else ""))
        if r.status_code == 401 or r.status_code == 403:
            detail = (r.text or "")[:500]
            raise OllamaClientError(
                f"鉴权失败（HTTP {r.status_code}）。请检查 llm.api_key 或 OLLAMA_API_KEY 是否正确。"
                + (f" 详情: {detail}" if detail else "")
            )
        if r.status_code >= 400:
            detail = (r.text or "")[:500]
            raise OllamaClientError(
                f"Ollama 返回错误 HTTP {r.status_code}（POST {chat_url}）。"
                + (f" 详情: {detail}" if detail else "")
            )

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            raise OllamaClientError(f"无法解析 Ollama 响应 JSON。 ({e!s})") from e

        if self._cfg.api_mode == "openai":
            return self._parse_openai_response(data, r.text)

        return self._parse_native_response(data, r.text)

    def _parse_native_response(self, data: Any, raw: str) -> str:
        msg = data.get("message") if isinstance(data, dict) else None
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content

        raise OllamaClientError(
            "Ollama 响应中缺少 assistant 内容。响应: " + (raw[:800] if raw else "(空)")
        )

    def _parse_openai_response(self, data: Any, raw: str) -> str:
        if not isinstance(data, dict):
            raise OllamaClientError("OpenAI 兼容响应格式无效（非 JSON 对象）。")
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        return content
        raise OllamaClientError(
            "OpenAI 兼容响应中缺少 choices[0].message.content。响应: "
            + (raw[:800] if raw else "(空)")
        )


def ollama_chat(cfg: LLMConfig, messages: list[dict[str, str]]) -> str:
    return OllamaClient(cfg).chat(messages)
