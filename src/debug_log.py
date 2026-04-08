"""DEBUG 模式：控制台 LLM 请求/响应摘要（脱敏与截断）。"""

from __future__ import annotations

import json
import logging
import os
import time
from copy import deepcopy
from typing import Any
from uuid import UUID

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


def _env_llm_summary_enabled() -> bool:
    v = os.environ.get("RUYI72_LLM_LOG", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def is_llm_summary_enabled(llm_cfg: Any | None = None) -> bool:
    """终端 INFO 单行摘要：环境变量 RUYI72_LLM_LOG 或 llm.log_summary。"""
    if _env_llm_summary_enabled():
        return True
    if llm_cfg is not None and bool(getattr(llm_cfg, "log_summary", False)):
        return True
    return False


def _env_react_trace_enabled() -> bool:
    v = os.environ.get("RUYI72_REACT_TRACE", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def is_react_trace_enabled() -> bool:
    """ReAct 工具调用 INFO 轨迹：环境变量 RUYI72_REACT_TRACE=1。"""
    return _env_react_trace_enabled()


def log_llm_summary(
    caller: str,
    *,
    llm_cfg: Any | None,
    url: str,
    elapsed_ms: float,
    ok: bool,
    http_status: int | None = None,
    error: str | None = None,
    reply_chars: int | None = None,
    extra: str | None = None,
) -> None:
    """不含完整 prompt/正文，仅用于排障。"""
    if not is_llm_summary_enabled(llm_cfg):
        return
    provider = getattr(llm_cfg, "provider", "?") if llm_cfg is not None else "?"
    model = getattr(llm_cfg, "model", "?") if llm_cfg is not None else "?"
    url_s = url
    try:
        from urllib.parse import urlparse

        pu = urlparse(url)
        path = pu.path or ""
        if len(path) > 64:
            path = path[:61] + "..."
        url_s = f"{pu.scheme}://{pu.netloc}{path}"
    except Exception:
        if len(url_s) > 120:
            url_s = url_s[:117] + "..."
    parts = [
        f"ok={ok}",
        f"ms={elapsed_ms:.0f}",
        f"provider={provider}",
        f"model={model}",
        f"url={url_s}",
    ]
    if http_status is not None:
        parts.append(f"http={http_status}")
    if error:
        parts.append("err=" + truncate(error, 400))
    if reply_chars is not None:
        parts.append(f"reply_chars={reply_chars}")
    if extra:
        parts.append(extra)
    _LOG.info("[LLM summary][%s] %s", caller, " ".join(parts))


def log_llm_stream_summary(
    caller: str,
    *,
    llm_cfg: Any | None,
    url: str,
    elapsed_ms: float,
    ok: bool,
    error: str | None = None,
    content_len: int | None = None,
    thinking_len: int | None = None,
) -> None:
    if not is_llm_summary_enabled(llm_cfg):
        return
    extra_parts: list[str] = []
    if content_len is not None:
        extra_parts.append(f"content_len={content_len}")
    if thinking_len is not None:
        extra_parts.append(f"thinking_len={thinking_len}")
    extra = " ".join(extra_parts) if extra_parts else None
    log_llm_summary(
        caller,
        llm_cfg=llm_cfg,
        url=url,
        elapsed_ms=elapsed_ms,
        ok=ok,
        error=error,
        extra=extra,
    )


from langchain_core.callbacks import BaseCallbackHandler


class LangChainLlmSummaryHandler(BaseCallbackHandler):
    """LangChain / LangGraph 内每次 LLM 调用的起止摘要。"""

    def __init__(self, llm_cfg: Any, *, label: str = "langchain") -> None:
        super().__init__()
        self._llm_cfg = llm_cfg
        self._label = label
        self._t0: dict[str, float] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if not is_llm_summary_enabled(self._llm_cfg):
            return
        self._t0[str(run_id)] = time.perf_counter()

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> Any:
        rid = str(run_id)
        t0 = self._t0.pop(rid, None)
        if t0 is None or not is_llm_summary_enabled(self._llm_cfg):
            return
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        n = 0
        try:
            gens = getattr(response, "generations", None) if response is not None else None
            if isinstance(gens, list):
                for gen_list in gens:
                    if not isinstance(gen_list, list):
                        continue
                    for part in gen_list:
                        txt = getattr(part, "text", None)
                        if isinstance(txt, str):
                            n += len(txt)
        except Exception:
            pass
        _LOG.info(
            "[LLM summary][%s][LangGraph] ok=True ms=%.0f llm_end reply_chars~=%s",
            self._label,
            elapsed_ms,
            n,
        )

    def on_llm_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        t0 = self._t0.pop(rid, None)
        if not is_llm_summary_enabled(self._llm_cfg):
            return
        elapsed_ms = (time.perf_counter() - t0) * 1000.0 if t0 is not None else 0.0
        _LOG.info(
            "[LLM summary][%s][%s] ok=False ms=%.0f err=%s",
            self._label,
            "LangGraph",
            elapsed_ms,
            truncate(str(error), 400),
        )


_LOG_REACT = logging.getLogger("ruyi72.react")
_REACT_TOOL_SNIP = 500


class ReactTraceToolCallbackHandler(BaseCallbackHandler):
    """ReAct / LangGraph 内每次工具调用的 INFO 单行日志（需 RUYI72_REACT_TRACE=1）。"""

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if not is_react_trace_enabled():
            return
        name = ""
        if isinstance(serialized, dict):
            name = str(serialized.get("name") or serialized.get("id") or "")
        inp = truncate(str(input_str or ""), _REACT_TOOL_SNIP)
        _LOG_REACT.info("[ReAct trace] tool_start name=%s run_id=%s in=%s", name, run_id, inp)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        if not is_react_trace_enabled():
            return
        out = truncate(str(output or ""), _REACT_TOOL_SNIP)
        _LOG_REACT.info("[ReAct trace] tool_end run_id=%s out=%s", run_id, out)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        if not is_react_trace_enabled():
            return
        _LOG_REACT.info(
            "[ReAct trace] tool_error run_id=%s err=%s",
            run_id,
            truncate(str(error), 400),
        )


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
