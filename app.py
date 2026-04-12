"""如意72 桌面应用入口：PyWebView + 多会话 + 本地持久化。"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import webview  # noqa: E402

from src.config import (  # noqa: E402
    LLMConfig,
    RuyiConfig,
    load_config,
    llm_provider_presets,
    save_llm_local_yaml,
)
from src.debug_log import set_debug_from_app  # noqa: E402
from src.llm.ollama import effective_trust_env, resolve_llm_api_key  # noqa: E402
from src.llm.ruyi72_identity_files import read_for_api, save_partial  # noqa: E402
from src.agent.memory_auto_extract import start_memory_auto_extract_worker  # noqa: E402
from src.scheduler import start_builtin_scheduler_worker  # noqa: E402
from src.scheduler import crud as scheduler_crud  # noqa: E402
from src.scheduler.runs_reader import list_task_run_entries  # noqa: E402
from src.agent.memory_extractor import extract_and_store_from_text  # noqa: E402
from src.agent.memory_tools import (  # noqa: E402
    browse_memory_formatted,
    get_recent_memory_for_api,
)
from src.service.conversation import ConversationService, resolve_sessions_root  # noqa: E402
from src.service import output_review as output_review_mod  # noqa: E402
from src.skills.loader import get_registry  # noqa: E402
from src.storage.memory_store import MemoryStore, default_store  # noqa: E402
from src.storage.memory_sqlite import maybe_migrate_jsonl  # noqa: E402
from src.storage.session_store import SessionStore  # noqa: E402

_LOG_EXTRACT_MEMORY = logging.getLogger("ruyi72.extract_memory")


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

        def emit_react(evt: dict) -> None:
            w = self._window
            if w is None:
                return
            try:
                inner = json.dumps(evt, ensure_ascii=False)
                js = (
                    "window.__ruyiReactEvent && window.__ruyiReactEvent("
                    + json.dumps(inner)
                    + ")"
                )
                w.evaluate_js(js)  # type: ignore[union-attr]
            except Exception:
                pass

        self._svc.set_react_stream_emit(emit_react)

    def persona_send(self, text: str) -> dict:
        return self._svc.persona_send(text or "")

    def persona_interrupt(self) -> dict:
        return self._svc.persona_interrupt()

    def persona_resume(self) -> dict:
        return self._svc.persona_resume()

    def persona_pause(self, reason: str | None = None) -> dict:
        return self._svc.persona_pause(reason or "")

    def send_message(self, text: str) -> dict:
        return self._svc.send_message(text or "")

    def interrupt_turn(self) -> dict:
        self._svc.interrupt_turn()
        return {"ok": True}

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
            "trust_env_config": llm.trust_env,
            "temperature": llm.temperature,
            "max_tokens": llm.max_tokens,
            "sessions_root": str(resolve_sessions_root(self._cfg)),
            "team_model_count": tm,
            "team_max_agents": team_max_agents,
            "persona_stream_think": per.stream_think,
            "persona_proactive_enabled": per.proactive_enabled,
            "persona_proactive_idle_seconds": per.proactive_idle_seconds,
            "persona_proactive_max_per_day": per.proactive_max_per_day,
            "output_review_enabled": self._cfg.output_review.enabled,
            "output_review_async_doubt": self._cfg.output_review.async_doubt_after_reply,
            "output_review_section_buttons": self._cfg.output_review.show_section_buttons,
        }

    def get_llm_defaults(self) -> dict:
        """各提供商默认 base_url / 示例 model，供设置表单初始化。"""
        return {"presets": llm_provider_presets()}

    def save_llm_settings(self, payload: object) -> dict:
        """校验并保存 llm 到 ~/.ruyi72/ruyi72.local.yaml，并更新进程内配置。"""
        if not isinstance(payload, dict):
            return {"ok": False, "error": "无效请求"}
        cur = self._cfg.llm
        merged: dict = cur.model_dump()
        try:
            for k in ("provider", "base_url", "model", "api_mode"):
                if k in payload and payload[k] is not None:
                    merged[k] = payload[k]
            if "temperature" in payload and payload["temperature"] is not None:
                merged["temperature"] = float(payload["temperature"])
            if "max_tokens" in payload and payload["max_tokens"] is not None:
                merged["max_tokens"] = int(payload["max_tokens"])
            if "trust_env" in payload:
                te = payload["trust_env"]
                if te is None or isinstance(te, bool):
                    merged["trust_env"] = te
            if "api_key" in payload:
                raw = payload["api_key"]
                if raw is None or (isinstance(raw, str) and not str(raw).strip()):
                    merged["api_key"] = None
                else:
                    merged["api_key"] = str(raw).strip()
            new_llm = LLMConfig.model_validate(merged)
            save_llm_local_yaml(new_llm)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        self._cfg = self._cfg.model_copy(update={"llm": new_llm})
        self._svc.update_llm_config(new_llm)
        return {"ok": True}

    def get_identity_prompt_files(self) -> dict:
        """~/.ruyi72 USER.md / SOUL.md / MEMORY.md 路径与内容（单文件最大约 256KB）。"""
        return read_for_api()

    def save_identity_prompt_files(self, payload: object) -> dict:
        """部分更新身份与记忆 Markdown；写入后使缓存失效。"""
        if not isinstance(payload, dict):
            return {"ok": False, "error": "无效请求"}
        try:
            save_partial(payload)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

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

    def get_dialogue_state(self) -> dict:
        """当前活动会话的对话相位；含 phase、last_turn_id、llm_busy_depth、last_error（与 dialogue_state.json 同步）。"""
        return {"ok": True, **self._svc.get_dialogue_phase_snapshot()}

    def update_session(self, payload: dict | None = None) -> dict:
        p = payload or {}
        return self._svc.update_session(
            title=p.get("title"),
            workspace=p.get("workspace"),
            mode=p.get("mode"),
            react_max_steps=p.get("react_max_steps"),
            avatar_mode=p.get("avatar_mode"),
            avatar_ref=p.get("avatar_ref"),
        )

    def get_session_avatar_meta(self) -> dict:
        """当前活动会话的形象字段（与 meta 子集一致）。"""
        g = self._svc.get_active()
        m = g.get("meta") or {}
        return {
            "session_id": m.get("id"),
            "avatar_mode": m.get("avatar_mode") or "off",
            "avatar_ref": m.get("avatar_ref") or "",
        }

    def set_session_avatar(self, payload: dict | None = None) -> dict:
        """仅更新当前会话的 avatar_mode / avatar_ref。"""
        p = payload or {}
        return self.update_session(
            {
                "avatar_mode": p.get("avatar_mode"),
                "avatar_ref": p.get("avatar_ref"),
            }
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

    def extract_memory(self, text: str, session_id: str | None = None) -> dict:
        """从前端提供的一段文本中抽取记忆单元并保存，返回数量统计。"""
        sid = (session_id or "").strip() or None
        raw = text or ""
        n_chars = len(raw)
        t_api = time.perf_counter()
        _LOG_EXTRACT_MEMORY.info(
            "extract_memory entry chars=%d session_id=%s extract_llm_timeout_sec=%d "
            "llm_provider=%s llm_model=%s base_url=%s",
            n_chars,
            sid or "(none)",
            int(self._cfg.memory.extract_llm_timeout_sec),
            self._cfg.llm.provider,
            self._cfg.llm.model,
            (self._cfg.llm.base_url or "")[:80] or "(empty)",
        )
        with self._svc.llm_busy():
            result = extract_and_store_from_text(
                self._cfg, raw, source_session_id=sid
            )
        api_ms = (time.perf_counter() - t_api) * 1000.0
        error = result.pop("error", None)
        ok = error is None
        stats = dict(result)
        _LOG_EXTRACT_MEMORY.info(
            "extract_memory done api_wall_ms=%.0f ok=%s stats=%s error=%s",
            api_ms,
            ok,
            stats,
            (error or "")[:300],
        )
        return {"ok": ok, "stats": stats, "error": error}

    def browse_memory(self, limit: int | None = None) -> dict:
        """浏览最近的记忆条目，返回格式化后的文本和原始结构。"""
        store: MemoryStore = default_store()
        n = int(limit or 10)
        facts, events, relations = get_recent_memory_for_api(n, store=store)
        text = browse_memory_formatted(n, store=store)
        return {
            "ok": True,
            "text": text,
            "facts": facts,
            "events": events,
            "relations": relations,
        }

    def list_pending_identity_merges(self, limit: int | None = None) -> dict:
        """列出永驻记忆待合并队列（pending_identity.jsonl）。"""
        store = default_store()
        lim = int(limit) if limit is not None else 100
        lim = max(1, min(500, lim))
        items = store.read_recent_pending_identity(lim)
        return {"ok": True, "items": items}

    def preview_pending_identity_merge(self, pending_id: str) -> dict:
        from src.storage.pending_identity_merge import preview_pending_identity_merge as _prev

        return _prev(default_store(), pending_id or "")

    def apply_pending_identity_merge(self, pending_id: str) -> dict:
        from src.storage.pending_identity_merge import apply_pending_identity_merge as _apply

        return _apply(default_store(), pending_id or "")

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

    def list_scheduled_tasks(self, payload: object = None) -> dict:
        """内置定时任务列表。payload: { kind: global|session, session_id?: str }"""
        p = payload if isinstance(payload, dict) else {}
        return scheduler_crud.list_tasks(self._svc, p)

    def save_scheduled_task(self, payload: object) -> dict:
        """创建或更新一条计划（完整 ScheduledTask 字段）。"""
        if not isinstance(payload, dict):
            return {"ok": False, "error": "无效请求"}
        return scheduler_crud.save_task(self._svc, payload)

    def delete_scheduled_task(self, payload: object) -> dict:
        """删除计划。payload: { kind, task_id, session_id? }"""
        if not isinstance(payload, dict):
            return {"ok": False, "error": "无效请求"}
        return scheduler_crud.delete_task(self._svc, payload)

    def list_scheduled_task_runs(self, payload: object = None) -> dict:
        """只读聚合全局 global_task_runs.log 与各会话 task_runs.log（尾部）。"""
        return list_task_run_entries(self._svc.store, self._cfg)

    def get_message_annotations(
        self, session_id: str | None = None, message_index: int = -1
    ) -> dict:
        """助手消息输出检查：引用、存疑、章节；持久化于会话目录 output_annotations.json。"""
        sid = (session_id or "").strip()
        if not sid:
            g = self._svc.get_active()
            m = g.get("meta") or {}
            sid = str(m.get("id") or "").strip()
        if not sid:
            return {"ok": False, "error": "无会话"}
        try:
            _, messages = self._svc.store.load(sid)
        except (OSError, FileNotFoundError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        session_dir = self._svc.session_path_for(sid)
        return output_review_mod.api_get_message_annotations(
            self._cfg, session_dir, messages, int(message_index)
        )

    def request_output_review(
        self,
        session_id: str | None = None,
        message_index: int = -1,
        user_context: str = "",
    ) -> dict:
        """异步触发存疑检查（需 async_doubt_after_reply）。"""
        sid = (session_id or "").strip()
        if not sid:
            g = self._svc.get_active()
            m = g.get("meta") or {}
            sid = str(m.get("id") or "").strip()
        if not sid:
            return {"ok": False, "error": "无会话"}
        try:
            _, messages = self._svc.store.load(sid)
        except (OSError, FileNotFoundError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        session_dir = self._svc.session_path_for(sid)
        return output_review_mod.api_request_output_review(
            self._cfg,
            session_dir,
            messages,
            int(message_index),
            user_context=user_context or "",
        )

    def review_message_section(
        self,
        session_id: str | None = None,
        message_index: int = -1,
        section_id: str = "",
    ) -> dict:
        """按小节调用检查模型。"""
        sid = (session_id or "").strip()
        if not sid:
            g = self._svc.get_active()
            m = g.get("meta") or {}
            sid = str(m.get("id") or "").strip()
        if not sid:
            return {"ok": False, "error": "无会话"}
        try:
            _, messages = self._svc.store.load(sid)
        except (OSError, FileNotFoundError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        session_dir = self._svc.session_path_for(sid)
        with self._svc.llm_busy():
            return output_review_mod.api_review_message_section(
                self._cfg,
                session_dir,
                messages,
                int(message_index),
                (section_id or "").strip(),
            )


def main() -> None:
    cfg = load_config()
    try:
        maybe_migrate_jsonl(cfg, default_store().root)
    except Exception:
        pass
    set_debug_from_app(cfg.app.debug)
    if cfg.app.debug or os.environ.get("RUYI72_DEBUG", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(levelname)s %(name)s: %(message)s",
            force=True,
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
            force=True,
        )
    store = SessionStore(resolve_sessions_root(cfg), ruyi_cfg=cfg)
    svc = ConversationService(
        cfg,
        store,
        react_default_steps=cfg.agent.react_max_steps_default,
    )
    start_memory_auto_extract_worker(svc)
    start_builtin_scheduler_worker(svc)
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
