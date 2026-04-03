"""按 sessionId 目录持久化会话元数据与消息。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["chat", "react"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionMeta(BaseModel):
    id: str
    title: str = "新对话"
    workspace: str = ""
    mode: Mode = "chat"
    react_max_steps: int = Field(default=8, ge=1, le=200)
    updated_at: str = ""

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()


class SessionStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _session_dir(self, session_id: str) -> Path:
        return self._root / session_id

    def create_session(
        self,
        *,
        title: str | None = None,
        workspace: str | None = None,
        mode: Mode = "chat",
        react_max_steps: int = 8,
    ) -> SessionMeta:
        sid = uuid.uuid4().hex
        d = self._session_dir(sid)
        d.mkdir(parents=True, exist_ok=False)
        ws = (workspace or "").strip() or str(Path.cwd())
        meta = SessionMeta(
            id=sid,
            title=(title or "新对话").strip() or "新对话",
            workspace=ws,
            mode=mode,
            react_max_steps=react_max_steps,
            updated_at=_utc_now_iso(),
        )
        self._write_meta(d, meta)
        self._write_messages(d, [])
        return meta

    def list_sessions(self) -> list[SessionMeta]:
        out: list[SessionMeta] = []
        if not self._root.is_dir():
            return out
        for p in sorted(self._root.iterdir(), key=lambda x: x.name):
            if not p.is_dir():
                continue
            meta_path = p / "meta.json"
            if not meta_path.is_file():
                continue
            try:
                meta = SessionMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
                out.append(meta)
            except (OSError, ValueError):
                continue
        out.sort(key=lambda m: m.updated_at or "", reverse=True)
        return out

    def load(self, session_id: str) -> tuple[SessionMeta, list[dict[str, str]]]:
        d = self._session_dir(session_id)
        if not d.is_dir():
            raise FileNotFoundError(session_id)
        meta_path = d / "meta.json"
        if not meta_path.is_file():
            raise FileNotFoundError(session_id)
        meta = SessionMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
        msg_path = d / "messages.json"
        messages: list[dict[str, str]] = []
        if msg_path.is_file():
            raw = json.loads(msg_path.read_text(encoding="utf-8"))
            arr = raw.get("messages") if isinstance(raw, dict) else None
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict) and item.get("role") in ("user", "assistant", "system"):
                        c = item.get("content")
                        if isinstance(c, str):
                            messages.append({"role": item["role"], "content": c})
        return meta, messages

    def save_messages(self, session_id: str, messages: list[dict[str, str]]) -> None:
        d = self._session_dir(session_id)
        if not d.is_dir():
            raise FileNotFoundError(session_id)
        self._write_messages(d, messages)
        meta_path = d / "meta.json"
        if meta_path.is_file():
            meta = SessionMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
            meta.touch()
            self._write_meta(d, meta)

    def update_meta(
        self,
        session_id: str,
        *,
        title: str | None = None,
        workspace: str | None = None,
        mode: Mode | None = None,
        react_max_steps: int | None = None,
    ) -> SessionMeta:
        d = self._session_dir(session_id)
        meta_path = d / "meta.json"
        if not meta_path.is_file():
            raise FileNotFoundError(session_id)
        meta = SessionMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
        data = meta.model_dump()
        if title is not None:
            data["title"] = title.strip() or meta.title
        if workspace is not None:
            data["workspace"] = workspace.strip()
        if mode is not None:
            data["mode"] = mode
        if react_max_steps is not None:
            data["react_max_steps"] = react_max_steps
        meta = SessionMeta.model_validate(data)
        meta.touch()
        self._write_meta(d, meta)
        return meta

    def _write_meta(self, d: Path, meta: SessionMeta) -> None:
        (d / "meta.json").write_text(
            meta.model_dump_json(ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_messages(self, d: Path, messages: list[dict[str, str]]) -> None:
        payload = {"messages": messages}
        (d / "messages.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
