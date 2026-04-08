"""内置定时任务：执行单条计划。"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from src.llm.ollama import OllamaClientError
from src.scheduler.models import (
    AppendSystemMessageAction,
    CallLlmOnceAction,
    NoopAction,
    ScheduledTask,
)
from src.scheduler.persistence import append_global_task_runs_log
from src.scheduler.timeutil import to_iso_utc, utc_now

if TYPE_CHECKING:
    from src.service.conversation import ConversationService
    from src.storage.session_store import SessionStore

_LOG = logging.getLogger("ruyi72.scheduler")


def _label_kv(task: ScheduledTask) -> dict[str, str]:
    lab = (task.label or "").strip()
    return {"label": lab} if lab else {}


def _truncate(s: str, max_len: int) -> str:
    t = s or ""
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _append_task_runs_log(session_dir: Path, record: dict) -> None:
    p = session_dir / "task_runs.log"
    line = json.dumps(record, ensure_ascii=False) + "\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(line)


def _log_global_llm(
    task: ScheduledTask,
    now_iso: str,
    *,
    ok: bool,
    act: CallLlmOnceAction,
    reply: str | None,
    err: str | None,
    latency_ms: int,
    llm_cfg,
) -> None:
    rec: dict = {
        "ts": now_iso,
        "task_id": task.id,
        "action": "call_llm_once",
        "ok": ok,
        "ask_only": bool(act.ask_only),
        "model": llm_cfg.model,
        "provider": llm_cfg.provider,
        "latency_ms": latency_ms,
        "system_prompt": _truncate(act.system_prompt, 4000),
        "user_prompt": _truncate(act.user_prompt, 8000),
        **_label_kv(task),
    }
    if ok and reply is not None:
        rec["assistant_text"] = _truncate(reply, 24000)
    if not ok and err:
        rec["error"] = err[:4000]
    append_global_task_runs_log(rec)


def execute_scheduled_task(
    task: ScheduledTask,
    svc: ConversationService,
    store: SessionStore,
) -> tuple[bool, str | None]:
    """
    执行一条任务。返回 (success, error_message)。
    全局：noop、call_llm_once；会话：noop、append_system_message、call_llm_once。
    """
    now_iso = to_iso_utc(utc_now())
    sid = task.session_id
    llm_cfg = svc._cfg.llm

    if task.kind == "global":
        if isinstance(task.action, AppendSystemMessageAction):
            return False, "全局任务暂不支持 append_system_message"
        if isinstance(task.action, NoopAction):
            _LOG.info("scheduler noop global task=%s", task.id[:8])
            append_global_task_runs_log(
                {
                    "ts": now_iso,
                    "task_id": task.id,
                    "action": "noop",
                    "ok": True,
                    **_label_kv(task),
                }
            )
            return True, None

        if isinstance(task.action, CallLlmOnceAction):
            act = task.action
            t0 = time.perf_counter()
            try:
                reply = svc.run_scheduler_llm_once(
                    system_prompt=act.system_prompt,
                    user_prompt=act.user_prompt,
                    ask_only=act.ask_only,
                    task_kind=task.kind,
                    session_id=task.session_id,
                )
                ms = int((time.perf_counter() - t0) * 1000)
                _log_global_llm(
                    task,
                    now_iso,
                    ok=True,
                    act=act,
                    reply=reply,
                    err=None,
                    latency_ms=ms,
                    llm_cfg=llm_cfg,
                )
                _LOG.info(
                    "scheduler call_llm_once global task=%s ask_only=%s ms=%s",
                    task.id[:8],
                    act.ask_only,
                    ms,
                )
                return True, None
            except OllamaClientError as e:
                ms = int((time.perf_counter() - t0) * 1000)
                _log_global_llm(
                    task,
                    now_iso,
                    ok=False,
                    act=act,
                    reply=None,
                    err=str(e),
                    latency_ms=ms,
                    llm_cfg=llm_cfg,
                )
                _LOG.warning("scheduler global LLM failed task=%s: %s", task.id[:8], e)
                return False, str(e)
            except Exception as e:
                ms = int((time.perf_counter() - t0) * 1000)
                _log_global_llm(
                    task,
                    now_iso,
                    ok=False,
                    act=act,
                    reply=None,
                    err=str(e),
                    latency_ms=ms,
                    llm_cfg=llm_cfg,
                )
                _LOG.exception("scheduler global LLM failed task=%s", task.id)
                return False, str(e)

        return False, "未知动作"

    assert sid is not None
    session_dir = store.root / sid
    if not session_dir.is_dir():
        return False, "会话目录不存在"

    try:
        if isinstance(task.action, NoopAction):
            _LOG.info("scheduler noop session=%s task=%s", sid[:8], task.id[:8])
            if task.persist_output_to in ("task_runs_log", "both"):
                _append_task_runs_log(
                    session_dir,
                    {
                        "ts": now_iso,
                        "task_id": task.id,
                        "action": "noop",
                        "ok": True,
                        **_label_kv(task),
                    },
                )
            return True, None

        if isinstance(task.action, AppendSystemMessageAction):
            text = task.action.text.strip()
            if task.persist_output_to in ("messages", "both"):
                svc.append_message_from_scheduler(
                    sid, role="system", content=text
                )
            if task.persist_output_to in ("task_runs_log", "both"):
                _append_task_runs_log(
                    session_dir,
                    {
                        "ts": now_iso,
                        "task_id": task.id,
                        "action": "append_system_message",
                        "preview": text[:200],
                        "ok": True,
                        **_label_kv(task),
                    },
                )
            return True, None

        if isinstance(task.action, CallLlmOnceAction):
            act = task.action
            t0 = time.perf_counter()
            try:
                reply = svc.run_scheduler_llm_once(
                    system_prompt=act.system_prompt,
                    user_prompt=act.user_prompt,
                    ask_only=act.ask_only,
                    task_kind=task.kind,
                    session_id=task.session_id,
                )
                ms = int((time.perf_counter() - t0) * 1000)
                rec = {
                    "ts": now_iso,
                    "task_id": task.id,
                    "action": "call_llm_once",
                    "ok": True,
                    "ask_only": bool(act.ask_only),
                    "model": llm_cfg.model,
                    "provider": llm_cfg.provider,
                    "latency_ms": ms,
                    "system_prompt": _truncate(act.system_prompt, 4000),
                    "user_prompt": _truncate(act.user_prompt, 8000),
                    "assistant_text": _truncate(reply, 24000),
                    **_label_kv(task),
                }
                _append_task_runs_log(session_dir, rec)
                if task.persist_output_to in ("messages", "both"):
                    head = "[定时任务"
                    lab = (task.label or "").strip()
                    head += f" · {lab}]" if lab else "]"
                    svc.append_message_from_scheduler(
                        sid,
                        role="assistant",
                        content=f"{head}\n\n{reply}",
                    )
                _LOG.info(
                    "scheduler call_llm_once session=%s task=%s ms=%s",
                    sid[:8],
                    task.id[:8],
                    ms,
                )
                return True, None
            except OllamaClientError as e:
                ms = int((time.perf_counter() - t0) * 1000)
                _append_task_runs_log(
                    session_dir,
                    {
                        "ts": now_iso,
                        "task_id": task.id,
                        "action": "call_llm_once",
                        "ok": False,
                        "ask_only": bool(act.ask_only),
                        "error": str(e)[:4000],
                        "model": llm_cfg.model,
                        "provider": llm_cfg.provider,
                        "latency_ms": ms,
                        "system_prompt": _truncate(act.system_prompt, 4000),
                        "user_prompt": _truncate(act.user_prompt, 8000),
                        **_label_kv(task),
                    },
                )
                _LOG.warning(
                    "scheduler session LLM failed sid=%s task=%s: %s",
                    sid[:8],
                    task.id[:8],
                    e,
                )
                return False, str(e)
            except Exception as e:
                ms = int((time.perf_counter() - t0) * 1000)
                _append_task_runs_log(
                    session_dir,
                    {
                        "ts": now_iso,
                        "task_id": task.id,
                        "action": "call_llm_once",
                        "ok": False,
                        "ask_only": bool(act.ask_only),
                        "error": str(e)[:4000],
                        "model": llm_cfg.model,
                        "provider": llm_cfg.provider,
                        "latency_ms": ms,
                        "system_prompt": _truncate(act.system_prompt, 4000),
                        "user_prompt": _truncate(act.user_prompt, 8000),
                        **_label_kv(task),
                    },
                )
                _LOG.exception("scheduler session LLM failed task=%s", task.id)
                return False, str(e)

    except Exception as e:
        _LOG.exception("scheduler execute failed task=%s", task.id)
        return False, str(e)

    return False, "未知动作"
