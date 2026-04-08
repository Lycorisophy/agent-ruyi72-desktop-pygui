"""内置定时任务：next_run_at 计算（UTC ISO 存储）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from datetime import time as dt_time


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_utc(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    t = str(s).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def next_fire_interval_sec(interval_sec: int, after_utc: datetime) -> datetime:
    return after_utc + timedelta(seconds=interval_sec)


def next_fire_daily_at_local(hhmm: str, after_utc: datetime) -> datetime:
    """下一个本地日历日 HH:MM 对应的 UTC 时刻（严格晚于 after_utc 的本地等价点）。"""
    local = after_utc.astimezone()
    h, m = map(int, hhmm.split(":"))
    tz = local.tzinfo
    today = local.date()
    cand = datetime.combine(today, dt_time(h, m), tzinfo=tz)
    if cand <= local:
        cand = cand + timedelta(days=1)
    return cand.astimezone(timezone.utc)
