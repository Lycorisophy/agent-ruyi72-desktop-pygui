"""内置定时任务：JSON 持久化（全局与会话目录）。"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from src.scheduler.models import ScheduledTasksFile
from src.storage.session_store import SessionStore

_FILE_LOCK = threading.Lock()

GLOBAL_REL = Path(".ruyi72") / "global_scheduled_tasks.json"
SESSION_TASKS_NAME = "scheduled_tasks.json"


def global_tasks_path() -> Path:
    return Path.home() / GLOBAL_REL


def session_tasks_path(store: SessionStore, session_id: str) -> Path:
    return store.root / session_id / SESSION_TASKS_NAME


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_global_tasks() -> ScheduledTasksFile:
    p = global_tasks_path()
    with _FILE_LOCK:
        if not p.is_file():
            return ScheduledTasksFile()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ScheduledTasksFile()
    if not isinstance(raw, dict):
        return ScheduledTasksFile()
    try:
        return ScheduledTasksFile.model_validate(raw)
    except Exception:
        return ScheduledTasksFile()


def save_global_tasks(data: ScheduledTasksFile) -> None:
    p = global_tasks_path()
    text = data.model_dump_json(ensure_ascii=False, indent=2)
    with _FILE_LOCK:
        _atomic_write(p, text)


def load_session_tasks(store: SessionStore, session_id: str) -> ScheduledTasksFile:
    p = session_tasks_path(store, session_id)
    with _FILE_LOCK:
        if not p.is_file():
            return ScheduledTasksFile()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ScheduledTasksFile()
    if not isinstance(raw, dict):
        return ScheduledTasksFile()
    try:
        return ScheduledTasksFile.model_validate(raw)
    except Exception:
        return ScheduledTasksFile()


def save_session_tasks(store: SessionStore, session_id: str, data: ScheduledTasksFile) -> None:
    p = session_tasks_path(store, session_id)
    text = data.model_dump_json(ensure_ascii=False, indent=2)
    with _FILE_LOCK:
        _atomic_write(p, text)


def upsert_task_in_file(
    data: ScheduledTasksFile,
    task,
) -> ScheduledTasksFile:
    """按 id 替换或追加。"""
    tid = task.id
    tasks = [t for t in data.tasks if t.id != tid]
    tasks.append(task)
    tasks.sort(key=lambda x: x.id)
    return ScheduledTasksFile(version=data.version, tasks=tasks)


def delete_task_from_file(data: ScheduledTasksFile, task_id: str) -> ScheduledTasksFile:
    tasks = [t for t in data.tasks if t.id != task_id]
    return ScheduledTasksFile(version=data.version, tasks=tasks)
