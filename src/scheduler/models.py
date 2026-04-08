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


class CallLlmOnceAction(BaseModel):
    """单次调用当前配置的 LLM，不读会话历史；结果写入运行记录（及可选会话消息）。"""

    type: Literal["call_llm_once"] = "call_llm_once"
    system_prompt: str = Field(default="", max_length=4000)
    user_prompt: str = Field(min_length=1, max_length=12000)
    ask_only: bool = Field(
        default=False,
        description="安全模式：仅允许 SAFE 级工具（只读工作区/记忆/技能加载等，无 shell）",
    )

    @field_validator("system_prompt", "user_prompt")
    @classmethod
    def _strip_prompts(cls, v: str) -> str:
        return (v or "").strip()


class ScheduledTask(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    kind: TaskKind
    session_id: str | None = None
    label: str = Field(
        default="",
        max_length=200,
        description="人类可读名称，便于列表与运行记录识别（与动作正文无关）",
    )
    enabled: bool = True
    trigger: Annotated[
        Union[IntervalTrigger, DailyAtTrigger],
        Field(discriminator="type"),
    ]
    action: Annotated[
        Union[NoopAction, AppendSystemMessageAction, CallLlmOnceAction],
        Field(discriminator="type"),
    ]
    next_run_at: str | None = None
    last_run_at: str | None = None
    run_when_session_inactive: bool = True
    persist_output_to: PersistOutputTo = "messages"
    missed_run_after_wake: MissedRunPolicy = "skip"
    schema_version: int = 1

    def requires_llm(self) -> bool:
        return isinstance(self.action, CallLlmOnceAction)

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        s = (v or "").strip()
        return s[:200]

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
