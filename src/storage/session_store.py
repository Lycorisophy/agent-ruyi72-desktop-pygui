"""按 sessionId 目录持久化会话元数据与消息。"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.agent.action_card import sanitize_card_from_storage
from src.agent.context_compression import ContextCheckpoint
from src.storage.memory_store import default_store

if TYPE_CHECKING:
    from src.config import RuyiConfig

Mode = Literal["chat", "react", "persona"]
SessionVariant = Literal["standard", "team", "knowledge"]
KbPreset = Literal["general", "ingest", "summarize", "qa"]
AvatarMode = Literal["off", "live2d", "pixel"]


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
    kb_preset: KbPreset | None = None
    avatar_mode: AvatarMode = "off"
    avatar_ref: str = Field(default="", max_length=512)

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()

    @model_validator(mode="after")
    def _normalize_team_fields(self) -> SessionMeta:
        if self.session_variant == "standard":
            object.__setattr__(self, "team_size", None)
            object.__setattr__(self, "kb_preset", None)
        elif self.session_variant == "knowledge":
            object.__setattr__(self, "team_size", None)
            if self.kb_preset is None:
                object.__setattr__(self, "kb_preset", "general")
        elif self.session_variant == "team":
            object.__setattr__(self, "kb_preset", None)
            if self.team_size is None:
                raise ValueError("session_variant=team 时会话必须包含 team_size（2～4）")
        return self


def _normalize_avatar_ref(ref: str) -> str:
    s = (ref or "").strip()[:512]
    if ".." in s or "\x00" in s:
        raise ValueError("avatar_ref 无效")
    if s and (s[0] in "/\\" or (len(s) > 1 and s[1] == ":")):
        raise ValueError("avatar_ref 不能使用绝对路径")
    return s


class SessionStore:
    def __init__(self, root: Path, ruyi_cfg: RuyiConfig | None = None) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._ruyi_cfg = ruyi_cfg

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

    def create_knowledge_session(
        self,
        *,
        kb_preset: KbPreset | str = "general",
        title: str | None = None,
        workspace: str | None = None,
        mode: Mode = "chat",
        react_max_steps: int = 8,
    ) -> SessionMeta:
        valid: tuple[str, ...] = ("general", "ingest", "summarize", "qa")
        kp: KbPreset = kb_preset if kb_preset in valid else "general"  # type: ignore[assignment]
        sid = uuid.uuid4().hex
        d = self._session_dir(sid)
        d.mkdir(parents=True, exist_ok=False)
        ws = (workspace or "").strip() or str(Path.cwd())
        t = (title or "知识库管理").strip() or "知识库管理"
        meta = SessionMeta(
            id=sid,
            title=t,
            workspace=ws,
            mode=mode,
            react_max_steps=react_max_steps,
            updated_at=_utc_now_iso(),
            session_variant="knowledge",
            team_size=None,
            kb_preset=kp,
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

    @staticmethod
    def _search_snippet(text: str, query_lower: str, margin: int = 48, max_len: int = 200) -> str:
        t = (text or "").replace("\n", " ").replace("\r", " ")
        if not t:
            return ""
        t_lower = t.lower()
        pos = t_lower.find(query_lower)
        if pos < 0:
            cut = t[:max_len]
            return cut + ("…" if len(t) > max_len else "")
        q_len = len(query_lower)
        start = max(0, pos - margin)
        end = min(len(t), pos + q_len + margin)
        chunk = t[start:end]
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(t) else ""
        return prefix + chunk.strip() + suffix

    def search_full_text(
        self,
        query: str,
        *,
        max_sessions: int = 200,
        max_hits_total: int = 80,
        snippets_per_session: int = 5,
    ) -> list[dict[str, Any]]:
        """
        按最近更新顺序扫描会话：匹配标题与各条消息的 content，以及 assistant card 的 title/body。
        返回 [{ session_id, title, hits: [{ message_index, role, snippet }] }]。
        """
        q = (query or "").strip()
        if not q:
            return []
        q_lower = q.lower()
        results: list[dict[str, Any]] = []
        hits_so_far = 0
        metas = self.list_sessions()[:max_sessions]
        for meta in metas:
            if hits_so_far >= max_hits_total:
                break
            session_hits: list[dict[str, Any]] = []
            title = (meta.title or "").strip() or meta.id
            if q_lower in title.lower() and len(session_hits) < snippets_per_session and hits_so_far < max_hits_total:
                session_hits.append(
                    {
                        "message_index": -1,
                        "role": "title",
                        "snippet": self._search_snippet(title, q_lower),
                    }
                )
                hits_so_far += 1
            try:
                _, messages = self.load(meta.id)
            except (OSError, FileNotFoundError, ValueError):
                continue
            for idx, msg in enumerate(messages):
                if hits_so_far >= max_hits_total or len(session_hits) >= snippets_per_session:
                    break
                role = str(msg.get("role") or "")
                content = msg.get("content") if isinstance(msg.get("content"), str) else ""
                combined = content
                card = msg.get("card")
                if isinstance(card, dict):
                    ct = str(card.get("title") or "")
                    cb = str(card.get("body") or "")
                    if ct or cb:
                        combined = f"{content}\n{ct}\n{cb}".strip()
                if q_lower not in combined.lower():
                    continue
                session_hits.append(
                    {
                        "message_index": idx,
                        "role": role,
                        "snippet": self._search_snippet(combined, q_lower),
                    }
                )
                hits_so_far += 1
            if session_hits:
                results.append(
                    {
                        "session_id": meta.id,
                        "title": title,
                        "hits": session_hits,
                    }
                )
        return results

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

    def save_dialogue_state(self, session_id: str, data: dict[str, Any]) -> None:
        """写入会话目录 `dialogue_state.json`（对话相位快照，与 meta 同级）。"""
        d = self._resolved_session_dir(session_id)
        (d / "dialogue_state.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_dialogue_state(self, session_id: str) -> dict[str, Any] | None:
        """读取 `dialogue_state.json`；不存在或损坏时返回 None。"""
        try:
            d = self._resolved_session_dir(session_id)
        except ValueError:
            return None
        p = d / "dialogue_state.json"
        if not p.is_file():
            return None
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def load_context_checkpoint(self, session_id: str) -> ContextCheckpoint | None:
        """读取 `context_checkpoint.json`；不存在或损坏时返回 None。"""
        try:
            d = self._resolved_session_dir(session_id)
        except ValueError:
            return None
        p = d / "context_checkpoint.json"
        if not p.is_file():
            return None
        try:
            return ContextCheckpoint.model_validate_json(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save_context_checkpoint(self, session_id: str, ck: ContextCheckpoint) -> None:
        """写入会话目录 `context_checkpoint.json`（与 meta.json 同级）。"""
        d = self._resolved_session_dir(session_id)
        if not d.is_dir():
            raise FileNotFoundError(session_id)
        (d / "context_checkpoint.json").write_text(
            ck.model_dump_json(ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
        self._maybe_reindex_messages_for_memory(session_id, messages)

    def _maybe_reindex_messages_for_memory(
        self, session_id: str, messages: list[dict[str, Any]]
    ) -> None:
        cfg = self._ruyi_cfg
        if cfg is None or not cfg.memory.messages_index_enabled:
            return
        if cfg.memory.backend not in ("dual", "sqlite"):
            return
        try:
            from src.storage.memory_sqlite import replace_session_messages_index

            replace_session_messages_index(
                cfg, default_store().root, session_id, messages
            )
        except Exception:
            pass

    def update_meta(
        self,
        session_id: str,
        *,
        title: str | None = None,
        workspace: str | None = None,
        mode: Mode | None = None,
        react_max_steps: int | None = None,
        avatar_mode: AvatarMode | None = None,
        avatar_ref: str | None = None,
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
        if avatar_mode is not None:
            if avatar_mode not in ("off", "live2d", "pixel"):
                raise ValueError("avatar_mode 须为 off、live2d 或 pixel")
            data["avatar_mode"] = avatar_mode
        if avatar_ref is not None:
            data["avatar_ref"] = _normalize_avatar_ref(avatar_ref)
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
