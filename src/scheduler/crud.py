"""内置定时任务：供 Api 调用的列表 / 保存 / 删除。"""

from __future__ import annotations

from typing import Any

from src.scheduler.models import ScheduledTask, ScheduledTasksFile
from src.scheduler.persistence import (
    delete_task_from_file,
    load_global_tasks,
    load_session_tasks,
    save_global_tasks,
    save_session_tasks,
    upsert_task_in_file,
)
from src.scheduler.scheduling import ensure_next_run
from src.service.conversation import ConversationService


def list_tasks(svc: ConversationService, payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("kind") or "global").strip().lower()
    store = svc.store
    if kind == "global":
        data = load_global_tasks()
        return {"ok": True, "tasks": [t.model_dump(mode="json") for t in data.tasks]}
    sid = str(payload.get("session_id") or "").strip()
    if not sid:
        return {"ok": False, "error": "kind=session 时需要 session_id"}
    try:
        store.load(sid)
    except (FileNotFoundError, OSError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    data = load_session_tasks(store, sid)
    return {"ok": True, "tasks": [t.model_dump(mode="json") for t in data.tasks]}


def save_task(svc: ConversationService, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        task = ScheduledTask.model_validate(payload)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    task, _ = ensure_next_run(task)
    store = svc.store
    if task.kind == "global":
        data = load_global_tasks()
        data = upsert_task_in_file(data, task)
        save_global_tasks(data)
        return {"ok": True, "task": task.model_dump(mode="json")}
    sid = task.session_id
    if not sid:
        return {"ok": False, "error": "会话级任务需要 session_id"}
    try:
        store.load(sid)
    except (FileNotFoundError, OSError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    data = load_session_tasks(store, sid)
    data = upsert_task_in_file(data, task)
    save_session_tasks(store, sid, data)
    return {"ok": True, "task": task.model_dump(mode="json")}


def delete_task(svc: ConversationService, payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("kind") or "").strip().lower()
    tid = str(payload.get("task_id") or payload.get("id") or "").strip()
    if not tid:
        return {"ok": False, "error": "缺少 task_id"}
    store = svc.store
    if kind == "global":
        data = load_global_tasks()
        data = delete_task_from_file(data, tid)
        save_global_tasks(data)
        return {"ok": True}
    sid = str(payload.get("session_id") or "").strip()
    if not sid:
        return {"ok": False, "error": "kind=session 时需要 session_id"}
    data = load_session_tasks(store, sid)
    data = delete_task_from_file(data, tid)
    save_session_tasks(store, sid, data)
    return {"ok": True}
