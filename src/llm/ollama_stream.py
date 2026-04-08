"""Ollama / OpenAI 兼容流式 chat：可取消、分通道 content / thinking。"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from src.config import LLMConfig
from src.debug_log import log_llm_request, log_llm_response, log_llm_stream_done
from src.llm.ollama import (
    OllamaClientError,
    effective_trust_env,
    is_openai_cloud,
    openai_compatible_chat_completions_url,
    resolve_llm_api_key,
)


def _base_prefix(cfg: LLMConfig) -> str:
    return cfg.base_url.rstrip("/") + "/"


def stream_chat(
    cfg: LLMConfig,
    messages: list[dict[str, str]],
    *,
    on_delta: Callable[[str, str], None],
    cancel_check: Callable[[], bool],
    model_override: str | None = None,
    think: bool = False,
    caller: str = "stream_chat",
) -> tuple[str, str]:
    """
    流式请求；on_delta(channel, text)，channel 为 \"content\" 或 \"thinking\"。
    返回累积的 (content, thinking)。
    """
    model_name = (model_override or "").strip() or cfg.model
    key = resolve_llm_api_key(cfg)
    headers: dict[str, str] = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    base = _base_prefix(cfg)
    trust = effective_trust_env(cfg)
    content_acc: list[str] = []
    thinking_acc: list[str] = []

    if is_openai_cloud(cfg):
        if not key:
            raise OllamaClientError(
                "当前提供商需要 API Key。请在设置中填写 llm.api_key，或设置对应环境变量。"
            )
        url = openai_compatible_chat_completions_url(cfg)
        body = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
    elif cfg.api_mode == "openai":
        url = base + "v1/chat/completions"
        body = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
    else:
        url = base + "api/chat"
        body = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "think": think,
            "options": {
                "temperature": cfg.temperature,
                "num_predict": cfg.max_tokens,
            },
        }

    log_llm_request(
        caller,
        url=url,
        provider=cfg.provider,
        model=model_name,
        messages=messages,
        body=body,
        headers=headers,
    )
    try:
        with httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            trust_env=trust,
        ) as client:
            with client.stream("POST", url, json=body, headers=headers) as r:
                if r.status_code >= 400:
                    raw = "".join(r.iter_text())[:800]
                    err = f"流式请求失败 HTTP {r.status_code}（POST {url}）。{raw}"
                    log_llm_response(
                        caller, error=err, http_status=r.status_code
                    )
                    raise OllamaClientError(err)
                if is_openai_cloud(cfg) or cfg.api_mode == "openai":
                    _consume_openai_stream(r, on_delta, cancel_check, content_acc, thinking_acc)
                else:
                    _consume_native_stream(r, on_delta, cancel_check, content_acc, thinking_acc)
    except httpx.ConnectError as e:
        log_llm_response(caller, error=f"ConnectError: {e!s}")
        raise OllamaClientError(
            "无法连接到 Ollama。请确认服务已启动且 base_url 正确。" f" ({e!s})"
        ) from e
    except httpx.TimeoutException as e:
        log_llm_response(caller, error=f"Timeout: {e!s}")
        raise OllamaClientError(f"流式请求超时。 ({e!s})") from e

    content_s = "".join(content_acc)
    thinking_s = "".join(thinking_acc)
    log_llm_stream_done(
        caller,
        url=url,
        provider=cfg.provider,
        model=model_name,
        content_len=len(content_s),
        thinking_len=len(thinking_s),
        content_preview=content_s,
        thinking_preview=thinking_s,
    )
    return content_s, thinking_s


def _consume_native_stream(
    r: httpx.Response,
    on_delta: Callable[[str, str], None],
    cancel_check: Callable[[], bool],
    content_acc: list[str],
    thinking_acc: list[str],
) -> None:
    for line in r.iter_lines():
        if cancel_check():
            break
        if not line or not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        msg = obj.get("message")
        if not isinstance(msg, dict):
            continue
        c = msg.get("content")
        if isinstance(c, str) and c:
            content_acc.append(c)
            on_delta("content", c)
        t = msg.get("thinking")
        if isinstance(t, str) and t:
            thinking_acc.append(t)
            on_delta("thinking", t)


def _consume_openai_stream(
    r: httpx.Response,
    on_delta: Callable[[str, str], None],
    cancel_check: Callable[[], bool],
    content_acc: list[str],
    thinking_acc: list[str],
) -> None:
    for line in r.iter_lines():
        if cancel_check():
            break
        if not line:
            continue
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            choices = obj.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            ch0 = choices[0]
            if not isinstance(ch0, dict):
                continue
            delta = ch0.get("delta")
            if not isinstance(delta, dict):
                continue
            c = delta.get("content")
            if isinstance(c, str) and c:
                content_acc.append(c)
                on_delta("content", c)
            # 部分 OpenAI 兼容实现可能用 reasoning_content
            rc = delta.get("reasoning_content")
            if isinstance(rc, str) and rc:
                thinking_acc.append(rc)
                on_delta("thinking", rc)
