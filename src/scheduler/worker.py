"""内置定时任务：后台调度线程。"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta

from src.config import BuiltinSchedulerConfig
from src.scheduler.executor import execute_scheduled_task
from src.scheduler.models import (
    DailyAtTrigger,
    IntervalTrigger,
    ScheduledTask,
    ScheduledTasksFile,
)
from src.scheduler.persistence import (
    load_global_tasks,
    load_session_tasks,
    save_global_tasks,
    save_session_tasks,
    upsert_task_in_file,
)
from src.scheduler.scheduling import advance_next_run, ensure_next_run
from src.scheduler.timeutil import (
    next_fire_daily_at_local,
    parse_iso_utc,
    to_iso_utc,
    utc_now,
)
from src.service.conversation import ConversationService

_LOG = logging.getLogger("ruyi72.scheduler")


def _missed_enough_for_skip_policy(task: ScheduledTask, nxt: datetime, now: datetime) -> bool:
    """判定是否属于「漏了多轮」而非同一天内略晚，供 missed_run_after_wake=skip 仅改期不执行。"""
    tr = task.trigger
    if isinstance(tr, DailyAtTrigger):
        l_n = nxt.astimezone()
        l_now = now.astimezone()
        return l_n.date() < l_now.date()
    if isinstance(tr, IntervalTrigger):
        return (now - nxt).total_seconds() >= 2 * tr.value
    return False


def _maybe_reschedule_skip_missed(task: ScheduledTask, now: datetime) -> tuple[ScheduledTask, bool]:
    """skip 策略：多轮遗漏时跳过执行，将 next_run_at 推到下一次合理时刻。"""
    if task.missed_run_after_wake != "skip" or not task.enabled:
        return task, False
    nxt = parse_iso_utc(task.next_run_at)
    if nxt is None or nxt >= now:
        return task, False
    if not _missed_enough_for_skip_policy(task, nxt, now):
        return task, False
    tr = task.trigger
    if isinstance(tr, DailyAtTrigger):
        new_nxt = to_iso_utc(next_fire_daily_at_local(tr.value, now))
    elif isinstance(tr, IntervalTrigger):
        new_nxt = to_iso_utc(now + timedelta(seconds=tr.value))
    else:
        return task, False
    _LOG.debug(
        "skip missed runs for task %s: next %s -> %s",
        task.id[:8],
        task.next_run_at,
        new_nxt,
    )
    return task.model_copy(update={"next_run_at": new_nxt}), True


def _apply_skip_policy_for_missed_tasks(
    svc: ConversationService, cfg: BuiltinSchedulerConfig, now: datetime
) -> None:
    store = svc.store
    data = load_global_tasks()
    changed = False
    tasks_out: list[ScheduledTask] = []
    for t in data.tasks:
        t2, ch = _maybe_reschedule_skip_missed(t, now)
        tasks_out.append(t2)
        changed = changed or ch
    if changed:
        save_global_tasks(ScheduledTasksFile(version=data.version, tasks=tasks_out))

    for m in store.list_sessions()[: cfg.max_sessions_scanned]:
        sf = load_session_tasks(store, m.id)
        changed = False
        tasks_out = []
        for t in sf.tasks:
            tt = t.model_copy(update={"session_id": m.id, "kind": "session"})
            t2, ch = _maybe_reschedule_skip_missed(tt, now)
            tasks_out.append(t2)
            changed = changed or ch
        if changed:
            save_session_tasks(
                store, m.id, ScheduledTasksFile(version=sf.version, tasks=tasks_out)
            )


def _fix_and_save_global() -> None:
    data = load_global_tasks()
    changed = False
    tasks: list[ScheduledTask] = []
    for t in data.tasks:
        t2, ch = ensure_next_run(t)
        tasks.append(t2)
        changed = changed or ch
    if changed:
        save_global_tasks(ScheduledTasksFile(version=data.version, tasks=tasks))


def _fix_and_save_session(store, session_id: str) -> None:
    data = load_session_tasks(store, session_id)
    changed = False
    tasks: list[ScheduledTask] = []
    for t in data.tasks:
        t2 = t.model_copy(update={"session_id": session_id, "kind": "session"})
        t3, ch = ensure_next_run(t2)
        tasks.append(t3)
        changed = changed or ch
    if changed:
        save_session_tasks(store, session_id, ScheduledTasksFile(version=data.version, tasks=tasks))


def _collect_tasks(svc: ConversationService, max_sessions: int) -> list[ScheduledTask]:
    store = svc.store
    _fix_and_save_global()
    out: list[ScheduledTask] = []
    g = load_global_tasks()
    for t in g.tasks:
        if t.enabled:
            t2, _ = ensure_next_run(t)
            out.append(t2)
    for m in store.list_sessions()[:max_sessions]:
        _fix_and_save_session(store, m.id)
        sf = load_session_tasks(store, m.id)
        for t in sf.tasks:
            if t.enabled:
                t2 = t.model_copy(update={"session_id": m.id, "kind": "session"})
                t3, _ = ensure_next_run(t2)
                out.append(t3)
    return out


def process_due_tasks(svc: ConversationService, cfg: BuiltinSchedulerConfig) -> None:
    store = svc.store
    now = utc_now()
    _apply_skip_policy_for_missed_tasks(svc, cfg, now)
    all_tasks = _collect_tasks(svc, cfg.max_sessions_scanned)

    due: list[ScheduledTask] = []
    for t in all_tasks:
        nxt = parse_iso_utc(t.next_run_at)
        if nxt is not None and nxt <= now:
            due.append(t)
    due.sort(key=lambda x: parse_iso_utc(x.next_run_at) or now)
    processed = 0
    for task in due:
        if processed >= cfg.max_tasks_per_tick:
            break
        if task.kind == "session" and task.session_id:
            if not task.run_when_session_inactive and not svc.is_session_active(
                task.session_id
            ):
                _LOG.debug("skip task %s: inactive session policy", task.id[:8])
                retry_at = to_iso_utc(now + timedelta(seconds=60))
                task = task.model_copy(update={"next_run_at": retry_at})
                data = load_session_tasks(store, task.session_id)
                data = upsert_task_in_file(data, task)
                save_session_tasks(store, task.session_id, data)
                continue

        ok, err = execute_scheduled_task(task, svc, store)
        fired_at = utc_now()
        last = to_iso_utc(fired_at)
        if not ok:
            _LOG.warning("task %s failed: %s", task.id[:8], err)
            nxt_retry = to_iso_utc(fired_at + timedelta(minutes=2))
            task = task.model_copy(update={"last_run_at": last, "next_run_at": nxt_retry})
        else:
            nxt = advance_next_run(task, fired_at)
            task = task.model_copy(update={"last_run_at": last, "next_run_at": nxt})

        if task.kind == "global":
            data = load_global_tasks()
            data = upsert_task_in_file(data, task)
            save_global_tasks(data)
        else:
            assert task.session_id
            data = load_session_tasks(store, task.session_id)
            data = upsert_task_in_file(data, task)
            save_session_tasks(store, task.session_id, data)
        processed += 1


def _loop(svc: ConversationService) -> None:
    while True:
        cfg = svc._cfg.builtin_scheduler  # noqa: SLF001
        interval = max(5, int(cfg.tick_interval_sec))
        time.sleep(float(interval))
        cfg = svc._cfg.builtin_scheduler  # noqa: SLF001
        if not cfg.enabled:
            continue
        try:
            if not svc.is_idle_for_auto_memory():
                _LOG.debug("scheduler skip tick: not idle")
                continue
            process_due_tasks(svc, cfg)
            try:
                svc.try_idle_context_compress()
            except Exception:
                _LOG.debug("idle context compress skipped", exc_info=True)
        except Exception:
            _LOG.exception("scheduler tick failed")


def start_builtin_scheduler_worker(svc: ConversationService) -> None:
    t = threading.Thread(
        target=_loop, args=(svc,), name="builtin-scheduler", daemon=True
    )
    t.start()
