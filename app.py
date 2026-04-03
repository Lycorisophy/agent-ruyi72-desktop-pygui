"""如意72 桌面应用入口：PyWebView + 多会话 + 本地持久化。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import webview  # noqa: E402

from src.config import RuyiConfig, load_config  # noqa: E402
from src.llm.ollama import effective_trust_env, resolve_llm_api_key  # noqa: E402
from src.agent.memory_extractor import extract_and_store_from_text  # noqa: E402
from src.agent.memory_tools import browse_memory_formatted  # noqa: E402
from src.service.conversation import ConversationService, resolve_sessions_root  # noqa: E402
from src.storage.memory_store import MemoryStore, default_store  # noqa: E402
from src.storage.session_store import SessionStore  # noqa: E402


class Api:
    def __init__(self, svc: ConversationService, cfg: RuyiConfig) -> None:
        self._svc = svc
        self._cfg = cfg

    def send_message(self, text: str) -> dict:
        ok, message, append_error = self._svc.send_message(text)
        return {"ok": ok, "message": message, "append_error": append_error}

    def get_settings_snapshot(self) -> dict:
        llm = self._cfg.llm
        has_key = resolve_llm_api_key(llm) is not None
        return {
            "title": self._cfg.app.title,
            "model": llm.model,
            "base_url": llm.base_url,
            "provider": llm.provider,
            "api_key_configured": has_key,
            "api_mode": llm.api_mode,
            "trust_env": effective_trust_env(llm),
            "sessions_root": str(resolve_sessions_root(self._cfg)),
        }

    def list_sessions(self) -> list:
        return self._svc.list_sessions()

    def create_session(self, title: str | None = None) -> dict:
        return self._svc.create_session(title=title)

    def open_session(self, session_id: str) -> dict:
        return self._svc.open_session(session_id)

    def get_active_session(self) -> dict:
        return self._svc.get_active()

    def update_session(self, payload: dict | None = None) -> dict:
        p = payload or {}
        return self._svc.update_session(
            title=p.get("title"),
            workspace=p.get("workspace"),
            mode=p.get("mode"),
            react_max_steps=p.get("react_max_steps"),
        )

    def extract_memory(self, text: str) -> dict:
        """从前端提供的一段文本中抽取记忆单元并保存，返回数量统计。"""
        result = extract_and_store_from_text(self._cfg.llm, text or "")
        ok = True
        error = result.pop("error", None)
        if error:
            ok = False
        return {"ok": ok, "stats": result, "error": error}

    def browse_memory(self, limit: int | None = None) -> dict:
        """浏览最近的记忆条目，返回格式化后的文本和原始结构。"""
        store: MemoryStore = default_store()
        n = int(limit or 10)
        facts = store.read_recent("facts", n)
        events = store.read_recent("events", n)
        relations = store.read_recent("relations", n)
        text = browse_memory_formatted(n, store=store)
        return {
            "ok": True,
            "text": text,
            "facts": facts,
            "events": events,
            "relations": relations,
        }


def main() -> None:
    cfg = load_config()
    store = SessionStore(resolve_sessions_root(cfg))
    svc = ConversationService(
        cfg.llm,
        store,
        react_default_steps=cfg.agent.react_max_steps_default,
    )
    api = Api(svc, cfg)
    index = ROOT / "web" / "index.html"
    url = index.resolve().as_uri()
    webview.create_window(
        cfg.app.title,
        url,
        width=cfg.app.width,
        height=cfg.app.height,
        js_api=api,
    )
    webview.start()


if __name__ == "__main__":
    main()
