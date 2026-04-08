"""内置定时任务：数据模型（会话级 + 全局）。"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator


TaskKind = Literal["session", "global"]
PersistOutputTo = Literal["messages", "task_runs_log", "both"]
MissedRunPolicy = Literal["catch_up_once", "skip"]


class IntervalTrigger(BaseModel):
    type: Literal["interval_sec"] = "interval_sec"
    value: int = Field(ge=30, le=86400 * 7)


class DailyAtTrigger(BaseModel):
    type: Literal["daily_at"] = "daily_at"
    value: str = Field(description="HH:MM 24h，本地时间")

    @field_validator("value")
    @classmethod
    def normalize_hhmm(cls, v: str) -> str:
        s = str(v).strip()
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError("daily_at 应为 HH:MM")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("时间无效")
        return f"{h:02d}:{m:02d}"


class NoopAction(BaseModel):
    type: Literal["noop"] = "noop"


class AppendSystemMessageAction(BaseModel):
    type: Literal["append_system_message"] = "append_system_message"
    text: str = Field(min_length=1, max_length=8000)


class ScheduledTask(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    kind: TaskKind
    session_id: str | None = None
    enabled: bool = True
    trigger: Annotated[
        Union[IntervalTrigger, DailyAtTrigger],
        Field(discriminator="type"),
    ]
    action: Annotated[
        Union[NoopAction, AppendSystemMessageAction],
        Field(discriminator="type"),
    ]
    next_run_at: str | None = None
    last_run_at: str | None = None
    run_when_session_inactive: bool = True
    persist_output_to: PersistOutputTo = "messages"
    missed_run_after_wake: MissedRunPolicy = "skip"
    schema_version: int = 1

    def requires_llm(self) -> bool:
        return False

    @model_validator(mode="after")
    def _session_id_for_kind(self) -> ScheduledTask:
        if self.kind == "session":
            sid = (self.session_id or "").strip()
            if not sid:
                raise ValueError("会话级任务需要非空 session_id")
            object.__setattr__(self, "session_id", sid)
        else:
            object.__setattr__(self, "session_id", None)
        return self


class ScheduledTasksFile(BaseModel):
    version: int = 1
    tasks: list[ScheduledTask] = Field(default_factory=list)
