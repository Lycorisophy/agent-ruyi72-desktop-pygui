"""会话级对话相位（P0：仅内存，供 UI / 调试与后续持久化）。"""

from __future__ import annotations

from typing import Literal

DialoguePhase = Literal[
    "idle",
    "streaming",
    "react_running",
    "team_running",
    "followup_pending",
]
