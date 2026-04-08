"""内置定时任务：执行单条计划。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.scheduler.models import (
    AppendSystemMessageAction,
    NoopAction,
    ScheduledTask,
)
from src.scheduler.persistence import append_global_task_runs_log
from src.scheduler.timeutil import to_iso_utc, utc_now

if TYPE_CHECKING:
    from src.service.conversation import ConversationService
    from src.storage.session_store import SessionStore

_LOG = logging.getLogger("ruyi72.scheduler")


def _append_task_runs_log(session_dir: Path, record: dict) -> None:
    p = session_dir / "task_runs.log"
    line = json.dumps(record, ensure_ascii=False) + "\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(line)


def execute_scheduled_task(
    task: ScheduledTask,
    svc: ConversationService,
    store: SessionStore,
) -> tuple[bool, str | None]:
    """
    执行一条任务。返回 (success, error_message)。
    全局任务仅支持 noop；会话级支持 noop 与 append_system_message。
    """
    now_iso = to_iso_utc(utc_now())
    sid = task.session_id

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
                }
            )
            return True, None
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
                    },
                )
            return True, None
    except Exception as e:
        _LOG.exception("scheduler execute failed task=%s", task.id)
        return False, str(e)

    return False, "未知动作"
