"""Ollama HTTP 客户端：原生 /api/chat 或 OpenAI 兼容 /v1/chat/completions。"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from src.config import LLMConfig
from src.debug_log import (
    is_llm_summary_enabled,
    log_llm_request,
    log_llm_response,
    log_llm_summary,
)

_LOG_HTTP = logging.getLogger("ruyi72.llm")


def _messages_from_body(body: dict[str, Any]) -> list[dict[str, str]]:
    raw = body.get("messages")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for m in raw:
        if isinstance(m, dict):
            out.append(
                {
                    "role": str(m.get("role") or ""),
                    "content": str(m.get("content") or ""),
                }
            )
    return out


def is_openai_cloud(cfg: LLMConfig) -> bool:
    return cfg.provider in ("minimax", "deepseek", "qwen")


def openai_compatible_chat_completions_url(cfg: LLMConfig) -> str:
    """OpenAI 兼容 POST …/chat/completions 的完整 URL。"""
    b = cfg.base_url.rstrip("/")
    if b.endswith("/v1"):
        return b + "/chat/completions"
    return b + "/v1/chat/completions"


def resolve_llm_api_key(cfg: LLMConfig) -> str | None:
    """配置文件 api_key 优先，否则按 provider 读常见环境变量。"""
    if cfg.api_key and str(cfg.api_key).strip():
        return str(cfg.api_key).strip()
    p = cfg.provider
    env_lists: tuple[str, ...]
    if p == "ollama":
        env_lists = ("OLLAMA_API_KEY", "RUYI72_OLLAMA_API_KEY")
    elif p == "minimax":
        env_lists = ("MINIMAX_API_KEY", "RUYI72_MINIMAX_API_KEY")
    elif p == "deepseek":
        env_lists = ("DEEPSEEK_API_KEY", "RUYI72_DEEPSEEK_API_KEY")
    elif p == "qwen":
        env_lists = ("DASHSCOPE_API_KEY", "QWEN_API_KEY", "RUYI72_DASHSCOPE_API_KEY")
    else:
        env_lists = ()
    for name in env_lists:
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

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model_override: str | None = None,
        caller: str = "OllamaClient.chat",
        read_timeout_sec: float | None = None,
        max_tokens_override: int | None = None,
    ) -> str:
        model_name = (model_override or "").strip() or self._cfg.model
        key = resolve_llm_api_key(self._cfg)
        trust = effective_trust_env(self._cfg)
        max_tokens = (
            int(max_tokens_override)
            if max_tokens_override is not None
            else int(self._cfg.max_tokens)
        )

        if is_openai_cloud(self._cfg):
            if not key:
                raise OllamaClientError(
                    "当前提供商需要 API Key。请在设置中填写 llm.api_key，或设置对应环境变量。"
                )
            chat_url = openai_compatible_chat_completions_url(self._cfg)
            headers: dict[str, str] = {"Authorization": f"Bearer {key}"}
            body: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "temperature": self._cfg.temperature,
                "max_tokens": max_tokens,
            }
            return self._post_chat_json(
                chat_url, headers, body, trust, caller, read_timeout_sec=read_timeout_sec
            )

        if self._cfg.provider != "ollama":
            raise OllamaClientError(f"未知 llm.provider: {self._cfg.provider!r}")

        headers = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        chat_url = self._request_chat_url()

        if self._cfg.api_mode == "openai":
            body: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "temperature": self._cfg.temperature,
                "max_tokens": max_tokens,
            }
        else:
            body = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                # Ollama「思考」类模型：默认可能输出 reasoning；显式关闭仅要最终回答
                "think": False,
                "options": {
                    "temperature": self._cfg.temperature,
                    "num_predict": max_tokens,
                },
            }

        return self._post_chat_json(
            chat_url, headers, body, trust, caller, read_timeout_sec=read_timeout_sec
        )

    def _post_chat_json(
        self,
        chat_url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        trust: bool,
        caller: str,
        *,
        read_timeout_sec: float | None = None,
    ) -> str:
        model_name = str(body.get("model") or self._cfg.model)
        msgs = _messages_from_body(body)
        log_llm_request(
            caller,
            url=chat_url,
            provider=self._cfg.provider,
            model=model_name,
            messages=msgs,
            body=body,
            headers=headers,
        )
        t0 = time.perf_counter()

        def _sum(
            ok: bool,
            *,
            http_status: int | None = None,
            error: str | None = None,
            reply_chars: int | None = None,
        ) -> None:
            if not is_llm_summary_enabled(self._cfg):
                return
            log_llm_summary(
                caller,
                llm_cfg=self._cfg,
                url=chat_url,
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
                ok=ok,
                http_status=http_status,
                error=error,
                reply_chars=reply_chars,
            )

        read_sec = 120.0 if read_timeout_sec is None else float(read_timeout_sec)
        _LOG_HTTP.info(
            "http chat POST begin caller=%s model=%s read_timeout_sec=%.1f "
            "connect_timeout_sec=10.0 url=%s",
            caller,
            model_name,
            read_sec,
            chat_url,
        )
        try:
            with httpx.Client(
                timeout=httpx.Timeout(read_sec, connect=10.0),
                trust_env=trust,
            ) as client:
                r = client.post(chat_url, json=body, headers=headers)
        except httpx.ConnectError as e:
            log_llm_response(caller, error=f"ConnectError: {e!s}")
            _sum(False, error=f"ConnectError: {e!s}")
            raise OllamaClientError(
                "无法连接到语言模型服务。请确认 base_url 正确且网络可达。"
                f" ({e!s})"
            ) from e
        except httpx.TimeoutException as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            log_llm_response(caller, error=f"Timeout: {e!s}")
            _sum(False, error=f"Timeout: {e!s}")
            _LOG_HTTP.warning(
                "http chat POST TIMEOUT caller=%s read_timeout_sec=%.1f elapsed_ms=%.0f "
                "url=%s model=%s detail=%s",
                caller,
                read_sec,
                elapsed_ms,
                chat_url,
                model_name,
                str(e)[:200],
            )
            raise OllamaClientError(f"请求超时，请稍后重试或检查模型是否过大。 ({e!s})") from e

        if r.status_code == 404:
            hint404 = f"未找到接口或模型（HTTP 404）。请求: POST {chat_url}。"
            if not is_openai_cloud(self._cfg):
                hint404 += (
                    " 若使用网关，可尝试将 llm.api_mode 设为 openai（/v1/chat/completions）。"
                    f" 并确认已 `ollama pull {self._cfg.model}`。"
                )
            log_llm_response(caller, error=hint404, http_status=404)
            _sum(False, http_status=404, error=hint404[:400])
            raise OllamaClientError(hint404)
        if r.status_code == 502:
            detail = (r.text or "")[:500]
            hint = (
                f"网关或上游不可用（HTTP 502）。请求: POST {chat_url}。\n"
                "常见原因：1) 本机访问仍走了系统代理——可在 ruyi72.yaml 设置 "
                "`llm.trust_env: false`（loopback 默认已关闭代理；若仍 502 请显式设置）；"
                "2) 反代只转发 /v1——尝试 `llm.api_mode: openai`；"
                "3) 上游 Ollama 未启动或地址错误。"
            )
            if resolve_llm_api_key(self._cfg):
                hint += " 若服务端要求鉴权，请确认 api_key 或对应环境变量正确。"
            err = hint + (f"\n详情: {detail}" if detail else "")
            log_llm_response(caller, error=err, http_status=502)
            _sum(False, http_status=502, error=err[:400])
            raise OllamaClientError(err)
        if r.status_code == 401 or r.status_code == 403:
            detail = (r.text or "")[:500]
            err = (
                f"鉴权失败（HTTP {r.status_code}）。请检查 llm.api_key 或 OLLAMA_API_KEY 是否正确。"
                + (f" 详情: {detail}" if detail else "")
            )
            log_llm_response(caller, error=err, http_status=r.status_code)
            _sum(False, http_status=r.status_code, error=err[:400])
            raise OllamaClientError(err)
        if r.status_code >= 400:
            detail = (r.text or "")[:500]
            err = (
                f"Ollama 返回错误 HTTP {r.status_code}（POST {chat_url}）。"
                + (f" 详情: {detail}" if detail else "")
            )
            log_llm_response(caller, error=err, http_status=r.status_code)
            _sum(False, http_status=r.status_code, error=err[:400])
            raise OllamaClientError(err)

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            log_llm_response(
                caller,
                error=f"JSON 解析失败: {e!s}",
                http_status=r.status_code,
            )
            _sum(False, http_status=r.status_code, error=f"JSON 解析失败: {e!s}")
            raise OllamaClientError(f"无法解析 Ollama 响应 JSON。 ({e!s})") from e

        try:
            if is_openai_cloud(self._cfg) or self._cfg.api_mode == "openai":
                text = self._parse_openai_response(data, r.text)
            else:
                text = self._parse_native_response(data, r.text)
        except OllamaClientError as err:
            log_llm_response(caller, error=str(err), http_status=r.status_code)
            _sum(False, http_status=r.status_code, error=str(err)[:400])
            raise
        elapsed_ok_ms = (time.perf_counter() - t0) * 1000.0
        _LOG_HTTP.info(
            "http chat POST ok caller=%s http_status=%d elapsed_ms=%.0f reply_chars=%d",
            caller,
            r.status_code,
            elapsed_ok_ms,
            len(text),
        )
        log_llm_response(caller, text=text, http_status=r.status_code)
        _sum(True, http_status=r.status_code, reply_chars=len(text))
        return text

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
    return OllamaClient(cfg).chat(messages, caller="ollama_chat")


def ollama_embed_one(
    cfg: LLMConfig,
    model: str,
    text: str,
    *,
    caller: str = "ollama_embed_one",
) -> list[float]:
    """POST /api/embed；仅支持 provider=ollama。"""
    if cfg.provider != "ollama":
        raise OllamaClientError("当前仅在本机 Ollama（llm.provider=ollama）下支持 embedding。")
    t = (text or "").strip()
    if not t:
        raise OllamaClientError("embedding 输入文本为空。")
    m = (model or "").strip() or cfg.model
    base = _base_prefix(cfg)
    embed_url = urljoin(base, "api/embed")
    key = resolve_llm_api_key(cfg)
    trust = effective_trust_env(cfg)
    headers: dict[str, str] = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body: dict[str, Any] = {"model": m, "input": t}
    try:
        with httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            trust_env=trust,
        ) as client:
            r = client.post(embed_url, json=body, headers=headers)
    except httpx.ConnectError as e:
        raise OllamaClientError(
            "无法连接 Ollama 以获取 embedding。请确认服务已启动且 base_url 正确。"
            f" ({e!s})"
        ) from e
    except httpx.TimeoutException as e:
        raise OllamaClientError(f"embedding 请求超时。 ({e!s})") from e
    if r.status_code >= 400:
        detail = (r.text or "")[:500]
        raise OllamaClientError(
            f"Ollama /api/embed 返回 HTTP {r.status_code}。{detail}"
        )
    try:
        data = r.json()
    except json.JSONDecodeError as e:
        raise OllamaClientError(f"无法解析 embedding 响应 JSON。 ({e!s})") from e
    emb = data.get("embedding")
    if not isinstance(emb, list) or not emb:
        raise OllamaClientError("Ollama embedding 响应缺少非空 embedding 数组。")
    try:
        return [float(x) for x in emb]
    except (TypeError, ValueError) as e:
        raise OllamaClientError(f"embedding 元素非数值。 ({e!s})") from e
