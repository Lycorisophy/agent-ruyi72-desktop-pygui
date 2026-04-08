"""按 sessionId 目录持久化会话元数据与消息。"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.agent.action_card import sanitize_card_from_storage

Mode = Literal["chat", "react", "persona"]
SessionVariant = Literal["standard", "team"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionMeta(BaseModel):
    id: str
    title: str = "新对话"
    workspace: str = ""
    mode: Mode = "chat"
    react_max_steps: int = Field(default=8, ge=1, le=200)
    updated_at: str = ""
    session_variant: SessionVariant = "standard"
    team_size: int | None = Field(default=None, ge=2, le=4)

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()

    @model_validator(mode="after")
    def _normalize_team_fields(self) -> SessionMeta:
        if self.session_variant == "standard":
            object.__setattr__(self, "team_size", None)
        elif self.team_size is None:
            raise ValueError("session_variant=team 时会话必须包含 team_size（2～4）")
        return self


class SessionStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _session_dir(self, session_id: str) -> Path:
        return self._root / session_id

    def _resolved_session_dir(self, session_id: str) -> Path:
        sid = (session_id or "").strip()
        if not sid or Path(sid).name != sid:
            raise ValueError("无效的会话 id")
        root = self._root.resolve()
        d = (self._root / sid).resolve()
        try:
            d.relative_to(root)
        except ValueError:
            raise ValueError("无效的会话 id") from None
        return d

    def delete_session(self, session_id: str) -> None:
        d = self._resolved_session_dir(session_id)
        if not d.is_dir():
            raise FileNotFoundError(session_id)
        shutil.rmtree(d)

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
            session_variant="standard",
            team_size=None,
        )
        self._write_meta(d, meta)
        self._write_messages(d, [])
        return meta

    def create_team_session(
        self,
        team_size: int,
        *,
        title: str | None = None,
        workspace: str | None = None,
        react_max_steps: int = 8,
    ) -> SessionMeta:
        if not (2 <= team_size <= 4):
            raise ValueError("team_size 必须在 2～4 之间")
        sid = uuid.uuid4().hex
        d = self._session_dir(sid)
        d.mkdir(parents=True, exist_ok=False)
        ws = (workspace or "").strip() or str(Path.cwd())
        t = (title or f"团队·{team_size}").strip() or f"团队·{team_size}"
        meta = SessionMeta(
            id=sid,
            title=t,
            workspace=ws,
            mode="chat",
            react_max_steps=react_max_steps,
            updated_at=_utc_now_iso(),
            session_variant="team",
            team_size=team_size,
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

    def _normalize_stored_message(self, item: dict[str, Any]) -> dict[str, Any] | None:
        role = item.get("role")
        if role not in ("user", "assistant", "system"):
            return None
        c = item.get("content")
        if not isinstance(c, str):
            return None
        msg: dict[str, Any] = {"role": role, "content": c}
        if role == "assistant" and "card" in item:
            card = sanitize_card_from_storage(item.get("card"))
            if card is not None:
                msg["card"] = card
        return msg

    def load(self, session_id: str) -> tuple[SessionMeta, list[dict[str, Any]]]:
        d = self._session_dir(session_id)
        if not d.is_dir():
            raise FileNotFoundError(session_id)
        meta_path = d / "meta.json"
        if not meta_path.is_file():
            raise FileNotFoundError(session_id)
        meta = SessionMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
        msg_path = d / "messages.json"
        messages: list[dict[str, Any]] = []
        if msg_path.is_file():
            raw = json.loads(msg_path.read_text(encoding="utf-8"))
            arr = raw.get("messages") if isinstance(raw, dict) else None
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict):
                        norm = self._normalize_stored_message(item)
                        if norm is not None:
                            messages.append(norm)
        return meta, messages

    def save_messages(self, session_id: str, messages: list[dict[str, Any]]) -> None:
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
        d = self._resolved_session_dir(session_id)
        meta_path = d / "meta.json"
        if not meta_path.is_file():
            raise FileNotFoundError(session_id)
        meta = SessionMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
        data = meta.model_dump()
        if title is not None:
            data["title"] = title.strip() or meta.title
        if workspace is not None:
            ws = workspace.strip()
            if len(ws) >= 2 and ws[0] == ws[-1] and ws[0] in "\"'":
                ws = ws[1:-1].strip()
            data["workspace"] = ws
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

    def _write_messages(self, d: Path, messages: list[dict[str, Any]]) -> None:
        payload = {"messages": messages}
        (d / "messages.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
