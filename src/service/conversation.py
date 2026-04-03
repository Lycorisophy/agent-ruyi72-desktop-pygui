"""多会话编排：对话 / ReAct、本地持久化。"""

from __future__ import annotations

from pathlib import Path

from src.agent.react import run_react
from src.config import LLMConfig, RuyiConfig
from src.llm.ollama import OllamaClient, OllamaClientError
from src.storage.session_store import Mode, SessionMeta, SessionStore


def resolve_sessions_root(cfg: RuyiConfig) -> Path:
    s = (cfg.storage.sessions_root or "").strip()
    if s:
        return Path(s).expanduser().resolve()
    return (Path.home() / ".ruyi72" / "sessions").resolve()


class ConversationService:
    def __init__(self, llm_cfg: LLMConfig, store: SessionStore, *, react_default_steps: int) -> None:
        self._llm = llm_cfg
        self._store = store
        self._react_default = react_default_steps
        self._active_id: str | None = None
        self._messages: list[dict[str, str]] = []
        self._meta: SessionMeta | None = None

    def ensure_session(self) -> None:
        if self._active_id:
            return
        sessions = self._store.list_sessions()
        if sessions:
            self.open_session(sessions[0].id)
        else:
            m = self._store.create_session(react_max_steps=self._react_default)
            self._active_id = m.id
            self._meta = m
            self._messages = []

    def list_sessions(self) -> list[dict]:
        return [m.model_dump() for m in self._store.list_sessions()]

    def create_session(self, title: str | None = None) -> dict:
        m = self._store.create_session(title=title, react_max_steps=self._react_default)
        return self.open_session(m.id)

    def open_session(self, session_id: str) -> dict:
        meta, messages = self._store.load(session_id)
        self._active_id = session_id
        self._meta = meta
        self._messages = messages
        return {"meta": self._meta.model_dump(), "messages": list(self._messages)}

    def get_active(self) -> dict:
        self.ensure_session()
        assert self._meta is not None and self._active_id is not None
        return {"meta": self._meta.model_dump(), "messages": list(self._messages)}

    def update_session(
        self,
        *,
        title: str | None = None,
        workspace: str | None = None,
        mode: str | None = None,
        react_max_steps: int | float | None = None,
    ) -> dict:
        self.ensure_session()
        assert self._active_id is not None
        mode_t: Mode | None = None
        if mode is not None:
            if mode not in ("chat", "react"):
                raise ValueError("mode 必须是 chat 或 react")
            mode_t = mode  # type: ignore[assignment]
        steps: int | None = None
        if react_max_steps is not None:
            steps = int(react_max_steps)
        meta = self._store.update_meta(
            self._active_id,
            title=title,
            workspace=workspace,
            mode=mode_t,
            react_max_steps=steps,
        )
        self._meta = meta
        return {"meta": meta.model_dump()}

    def send_message(self, text: str) -> tuple[bool, str, bool]:
        """
        返回 (ok, message, append_error)。
        append_error=True 时前端在刷新后额外展示一条错误气泡（仅对话模式 LLM 失败等未写入历史的情况）。
        """
        self.ensure_session()
        assert self._active_id is not None and self._meta is not None

        text = (text or "").strip()
        if not text:
            return False, "请输入内容。", True

        ws = (self._meta.workspace or "").strip()
        if not ws:
            return False, "请先在侧栏或上方设置「工作区」为有效文件夹路径。", True

        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return False, f"工作区不存在或不是目录: {root}", True

        self._messages.append({"role": "user", "content": text})

        if self._meta.mode == "chat":
            try:
                reply = OllamaClient(self._llm).chat(self._messages)
            except OllamaClientError as e:
                self._messages.pop()
                return False, str(e), True
            self._messages.append({"role": "assistant", "content": reply})
            self._store.save_messages(self._active_id, self._messages)
            self._meta, _ = self._store.load(self._active_id)
            return True, reply, False

        ok, out = run_react(
            self._llm,
            self._messages,
            workspace=str(root),
            max_steps=self._meta.react_max_steps,
        )
        self._store.save_messages(self._active_id, self._messages)
        self._meta, _ = self._store.load(self._active_id)
        return ok, out, False
