"""DEBUG 模式：控制台 LLM 请求/响应摘要（脱敏与截断）。"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from typing import Any

_LOG = logging.getLogger("ruyi72.llm")

# 单条日志中 message content / 返回文本的最大字符数
_MAX_FIELD = 3000
_MAX_PREVIEW = 800

_app_debug: bool = False


def _env_debug_enabled() -> bool:
    v = os.environ.get("RUYI72_DEBUG", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def set_debug_from_app(debug: bool) -> None:
    """由 app.main 根据 cfg.app.debug 设置。"""
    global _app_debug
    _app_debug = bool(debug)


def is_debug() -> bool:
    """配置或环境变量 RUYI72_DEBUG 任一开启即视为 DEBUG。"""
    return _app_debug or _env_debug_enabled()


def truncate(s: str | None, max_len: int = _MAX_FIELD) -> str:
    if s is None:
        return ""
    if len(s) <= max_len:
        return s
    return s[:max_len] + f"...（截断，共 {len(s)} 字符）"


def redact_headers(h: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in h.items():
        lk = k.lower()
        if lk == "authorization":
            out[k] = "Bearer ***"
        else:
            out[k] = v
    return out


def safe_messages_for_log(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        content = truncate(str(m.get("content") or ""))
        out.append({"role": role, "content": content})
    return out


def safe_body_for_log(body: dict[str, Any]) -> dict[str, Any]:
    b = deepcopy(body)
    if "messages" in b and isinstance(b["messages"], list):
        b["messages"] = safe_messages_for_log(
            [x for x in b["messages"] if isinstance(x, dict)]
        )
    if "options" in b and isinstance(b["options"], dict):
        opts = dict(b["options"])
        b["options"] = opts
    return b


def log_llm_request(
    caller: str,
    *,
    url: str,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    if not is_debug():
        return
    extra: dict[str, Any] = {
        "url": url,
        "provider": provider,
        "model": model,
        "messages": safe_messages_for_log(messages),
    }
    if body is not None:
        extra["body"] = safe_body_for_log(body)
    if headers:
        extra["headers"] = redact_headers(headers)
    try:
        line = json.dumps(extra, ensure_ascii=False)
    except (TypeError, ValueError):
        line = str(extra)
    _LOG.debug("[LLM][%s] request %s", caller, line)


def log_llm_response(
    caller: str,
    *,
    text: str | None = None,
    error: str | None = None,
    http_status: int | None = None,
) -> None:
    if not is_debug():
        return
    parts: list[str] = []
    if http_status is not None:
        parts.append(f"http={http_status}")
    if error:
        parts.append("error=" + truncate(error, _MAX_PREVIEW))
    if text is not None:
        parts.append("reply=" + truncate(text, _MAX_FIELD))
    _LOG.debug("[LLM][%s] response %s", caller, " ".join(parts))


def log_llm_stream_done(
    caller: str,
    *,
    url: str,
    provider: str,
    model: str,
    content_len: int,
    thinking_len: int,
    content_preview: str,
    thinking_preview: str,
) -> None:
    if not is_debug():
        return
    payload = {
        "url": url,
        "provider": provider,
        "model": model,
        "content_len": content_len,
        "thinking_len": thinking_len,
        "content_preview": truncate(content_preview, _MAX_PREVIEW),
        "thinking_preview": truncate(thinking_preview, _MAX_PREVIEW),
    }
    try:
        line = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        line = str(payload)
    _LOG.debug("[LLM][%s] stream_done %s", caller, line)


def log_send_message_context(
    caller: str,
    *,
    mode: str,
    session_variant: str | None,
    workspace_set: bool,
) -> None:
    if not is_debug():
        return
    _LOG.debug(
        "[LLM][%s] send_message mode=%s session_variant=%s workspace_set=%s",
        caller,
        mode,
        session_variant or "",
        workspace_set,
    )
