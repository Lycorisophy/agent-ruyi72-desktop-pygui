"""内置定时任务：next_run 计算（供 worker 与 crud 共用）。"""

from __future__ import annotations

from datetime import timedelta

from src.scheduler.models import DailyAtTrigger, IntervalTrigger, ScheduledTask
from src.scheduler.timeutil import (
    next_fire_daily_at_local,
    next_fire_interval_sec,
    to_iso_utc,
    utc_now,
)


def ensure_next_run(task: ScheduledTask) -> tuple[ScheduledTask, bool]:
    """若缺少 next_run_at 则补全；返回 (task, changed)。"""
    if task.next_run_at:
        return task, False
    now = utc_now()
    tr = task.trigger
    if isinstance(tr, IntervalTrigger):
        nxt = to_iso_utc(next_fire_interval_sec(tr.value, now))
    elif isinstance(tr, DailyAtTrigger):
        nxt = to_iso_utc(next_fire_daily_at_local(tr.value, now))
    else:
        nxt = to_iso_utc(now)
    return task.model_copy(update={"next_run_at": nxt}), True


def advance_next_run(task: ScheduledTask, fired_at) -> str:
    tr = task.trigger
    if isinstance(tr, IntervalTrigger):
        return to_iso_utc(next_fire_interval_sec(tr.value, fired_at))
    if isinstance(tr, DailyAtTrigger):
        after = fired_at + timedelta(seconds=1)
        return to_iso_utc(next_fire_daily_at_local(tr.value, after))
    raise ValueError("未知 trigger")
