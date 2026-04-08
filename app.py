"""如意72 桌面应用入口：PyWebView + 多会话 + 本地持久化。"""

from __future__ import annotations

import json
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
from src.skills.loader import get_registry  # noqa: E402
from src.storage.memory_store import MemoryStore, default_store  # noqa: E402
from src.storage.session_store import SessionStore  # noqa: E402


class Api:
    def __init__(self, svc: ConversationService, cfg: RuyiConfig) -> None:
        self._svc = svc
        self._cfg = cfg
        self._window: object | None = None

    def set_window(self, window: object | None) -> None:
        """注入主窗口，用于拟人模式 evaluate_js 推送事件。"""
        self._window = window

        def emit(evt: dict) -> None:
            w = self._window
            if w is None:
                return
            try:
                inner = json.dumps(evt, ensure_ascii=False)
                js = (
                    "window.__ruyiPersonaEvent && window.__ruyiPersonaEvent("
                    + json.dumps(inner)
                    + ")"
                )
                w.evaluate_js(js)  # type: ignore[union-attr]
            except Exception:
                pass

        self._svc.set_persona_emit(emit)

    def persona_send(self, text: str) -> dict:
        return self._svc.persona_send(text or "")

    def persona_interrupt(self) -> dict:
        return self._svc.persona_interrupt()

    def persona_resume(self) -> dict:
        return self._svc.persona_resume()

    def persona_pause(self, reason: str | None = None) -> dict:
        return self._svc.persona_pause(reason or "")

    def send_message(self, text: str) -> dict:
        ok, message, append_error = self._svc.send_message(text)
        return {"ok": ok, "message": message, "append_error": append_error}

    def get_settings_snapshot(self) -> dict:
        llm = self._cfg.llm
        has_key = resolve_llm_api_key(llm) is not None
        tm = len(self._cfg.team.models)
        # 至少 2 个槽位才允许团队会话；M=1 时 team_max_agents 须为 0，避免前端误判
        team_max_agents = min(4, tm) if tm >= 2 else 0
        per = self._cfg.persona
        return {
            "title": self._cfg.app.title,
            "model": llm.model,
            "base_url": llm.base_url,
            "provider": llm.provider,
            "api_key_configured": has_key,
            "api_mode": llm.api_mode,
            "trust_env": effective_trust_env(llm),
            "sessions_root": str(resolve_sessions_root(self._cfg)),
            "team_model_count": tm,
            "team_max_agents": team_max_agents,
            "persona_stream_think": per.stream_think,
            "persona_proactive_enabled": per.proactive_enabled,
            "persona_proactive_idle_seconds": per.proactive_idle_seconds,
            "persona_proactive_max_per_day": per.proactive_max_per_day,
        }

    def list_sessions(self) -> list:
        return self._svc.list_sessions()

    def search_sessions_text(self, query: str) -> list:
        return self._svc.search_sessions_text(query or "")

    def create_session(self, title: str | None = None) -> dict:
        return self._svc.create_session(title=title)

    def create_team_session(self, team_size: int, title: str | None = None) -> dict:
        try:
            data = self._svc.create_team_session(int(team_size), title=title)
            return {"ok": True, **data}
        except ValueError as e:
            return {"ok": False, "error": str(e), "meta": None, "messages": []}

    def create_knowledge_session(
        self, kb_preset: str | None = None, title: str | None = None
    ) -> dict:
        data = self._svc.create_knowledge_session(
            kb_preset=kb_preset or "general",
            title=title,
        )
        return {"ok": True, **data}

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

    def rename_session(self, session_id: str, title: str) -> dict:
        return self._svc.rename_session(session_id or "", title or "")

    def delete_session(self, session_id: str) -> dict:
        return self._svc.delete_session(session_id or "")

    def submit_action_card(
        self,
        card_id: str,
        action: str,
        selected_ids: list | None = None,
        from_timeout: bool = False,
    ) -> dict:
        return self._svc.submit_action_card(
            card_id or "",
            action or "",
            selected_ids,
            from_timeout=bool(from_timeout),
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

    def list_skills_compact(self) -> list[dict]:
        reg = get_registry()
        out: list[dict] = []
        for s in reg.skills:
            desc = (s.description or "").strip()
            if len(desc) > 300:
                desc = desc[:297] + "..."
            out.append(
                {
                    "name": s.name,
                    "description": desc,
                    "level": s.level,
                    "id": s.id,
                }
            )
        return out

    def preview_workspace_file(self, rel_path: str | None = None) -> dict:
        return self._svc.preview_workspace_file(rel_path or "")

    def list_workspace_preview(self, rel_path: str | None = None) -> dict:
        p = ("" if rel_path is None else str(rel_path)).strip().replace("\\", "/")
        if not p:
            p = "."
        return self._svc.list_workspace_preview(p)


def main() -> None:
    cfg = load_config()
    store = SessionStore(resolve_sessions_root(cfg))
    svc = ConversationService(
        cfg,
        store,
        react_default_steps=cfg.agent.react_max_steps_default,
    )
    api = Api(svc, cfg)
    index = ROOT / "web" / "index.html"
    url = index.resolve().as_uri()
    win = webview.create_window(
        cfg.app.title,
        url,
        width=cfg.app.width,
        height=cfg.app.height,
        js_api=api,
    )
    api.set_window(win)
    webview.start()


if __name__ == "__main__":
    main()
