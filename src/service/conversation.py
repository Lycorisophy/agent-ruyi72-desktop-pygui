"""多会话编排：对话 / ReAct、本地持久化。"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agent.tools import ToolError, safe_child
from src.agent.action_card import (
    split_reply_action_card,
    strip_action_card_markers,
    supersede_pending_cards,
    utc_now_iso,
)
from src.agent.memory_tools import build_memory_bootstrap_block
from src.agent.chat_stream_runtime import SafeChatStreamRuntime
from src.agent.context_compression import (
    ContextCheckpoint,
    apply_checkpoint_to_flat,
    estimate_tokens_messages,
    phase_a_trim_long_messages,
    raw_flat_from_stored_messages,
    run_compression_round,
)
from src.agent.persona_runtime import CHECKPOINT_NAME, PersonaRuntime
from src.agent.react import run_react
from src.agent.react_lc import run_scheduler_safe_agent
from src.agent.team_turn import run_team_turn
from src.config import LLMConfig, PersonaConfig, RuyiConfig
from src.debug_log import log_send_message_context
from src.llm.ollama import OllamaClient, OllamaClientError
from src.llm.knowledge_prompts import knowledge_base_system_hint
from src.llm.prompts import (
    SCHEDULED_TASK_REPLY_RULES,
    action_card_system_hint,
    build_system_block,
)
from src.skills.loader import build_safe_skills_prompt, get_registry
from src.service.dialogue_phase import DialoguePhase
from src.storage.session_store import AvatarMode, Mode, SessionMeta, SessionStore


def resolve_sessions_root(cfg: RuyiConfig) -> Path:
    s = (cfg.storage.sessions_root or "").strip()
    if s:
        return Path(s).expanduser().resolve()
    return (Path.home() / ".ruyi72" / "sessions").resolve()


class ConversationService:
    """磁盘上的「进行中」相位在进程崩溃后视为陈旧，见 `_reconcile_dialogue_state_after_load`。"""

    _DIALOGUE_STALE_PHASES: frozenset[str] = frozenset(
        {"streaming", "react_running", "team_running", "followup_pending"}
    )

    def __init__(self, cfg: RuyiConfig, store: SessionStore, *, react_default_steps: int) -> None:
        self._cfg = cfg
        self._llm = cfg.llm
        self._store = store
        self._react_default = react_default_steps
        self._active_id: str | None = None
        self._messages: list[dict[str, Any]] = []
        self._meta: SessionMeta | None = None
        self._memory_bootstrap_pending = False
        self._persona_emit: Any = None
        self._react_stream_emit: Any = None
        self._persona_rt: PersonaRuntime | None = None
        self._chat_rt: SafeChatStreamRuntime | None = None
        self._react_cancel = threading.Event()
        self._react_thread: threading.Thread | None = None
        self._llm_busy_depth = 0
        self._llm_busy_lock = threading.Lock()
        self._dialogue_phase: DialoguePhase = "idle"
        self._dialogue_last_turn_id: int = 0
        self._dialogue_last_error: str | None = None
        self._dialogue_state_extension: dict[str, Any] = {}
        self._dialogue_lock = threading.Lock()
        self._context_checkpoint = ContextCheckpoint()
        self._context_compress_lock = threading.Lock()
        self._last_idle_compress_mono: float = 0.0

    def set_dialogue_phase(
        self,
        phase: DialoguePhase,
        *,
        last_turn_id: int | None = None,
        emit_event: bool = True,
    ) -> None:
        """更新当前会话的对话相位；可选向前端推送 state.changed；并写入 dialogue_state.json（P1）。"""
        with self._dialogue_lock:
            self._dialogue_phase = phase
            if last_turn_id is not None:
                self._dialogue_last_turn_id = int(last_turn_id)
            if phase != "idle":
                self._dialogue_last_error = None
            else:
                self._dialogue_state_extension.pop("team", None)
                self._dialogue_state_extension.pop("react", None)
            snap = {
                "phase": self._dialogue_phase,
                "last_turn_id": self._dialogue_last_turn_id,
                "state_extension": dict(self._dialogue_state_extension),
            }
        if emit_event and self._persona_emit:
            evt = {"type": "state.changed", **snap}
            try:
                self._persona_emit(evt)
            except Exception:
                pass
        self._persist_dialogue_state()

    def merge_dialogue_state_extension(
        self,
        patch: dict[str, Any],
        *,
        emit_event: bool = False,
    ) -> None:
        """合并 P2 细粒度字段（如 team.current_slot、react.step_index）；默认不落 state.changed 以免 ReAct 流刷屏。"""
        with self._dialogue_lock:
            for k, v in patch.items():
                if v is None:
                    self._dialogue_state_extension.pop(k, None)
                else:
                    self._dialogue_state_extension[k] = v
            snap = {
                "phase": self._dialogue_phase,
                "last_turn_id": self._dialogue_last_turn_id,
                "state_extension": dict(self._dialogue_state_extension),
            }
        if emit_event and self._persona_emit:
            try:
                self._persona_emit({"type": "state.changed", **snap})
            except Exception:
                pass
        self._persist_dialogue_state()

    def _on_team_slot_progress(self, slot: int, n_total: int) -> None:
        """团队链当前槽位（每槽调用一次，带 emit 便于前端刷新）。"""
        self.merge_dialogue_state_extension(
            {"team": {"current_slot": int(slot), "team_size": int(n_total)}},
            emit_event=True,
        )

    def _on_react_step_index(self, idx: int) -> None:
        """ReAct 与 react.progress 同步的步序（状态签名变化时递增）。"""
        self.merge_dialogue_state_extension(
            {"react": {"step_index": int(idx)}},
            emit_event=False,
        )

    def _dialogue_state_payload(self) -> dict[str, Any]:
        with self._dialogue_lock:
            return {
                "schema_version": 1,
                "session_id": self._active_id or "",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "phase": self._dialogue_phase,
                "last_turn_id": self._dialogue_last_turn_id,
                "last_error": self._dialogue_last_error,
                "state_extension": dict(self._dialogue_state_extension),
            }

    def _persist_dialogue_state(self) -> None:
        sid = self._active_id
        if not sid:
            return
        try:
            self._store.save_dialogue_state(sid, self._dialogue_state_payload())
        except Exception:
            pass

    def _reconcile_dialogue_state_after_load(self) -> None:
        """打开会话时读取 dialogue_state.json；若上次为非 idle 则降级为 idle 并提示。"""
        assert self._active_id is not None
        sid = self._active_id
        raw = self._store.load_dialogue_state(sid)
        recovered = False
        recovered_msg = ""
        tid = 0

        if not raw or raw.get("schema_version") != 1:
            with self._dialogue_lock:
                self._dialogue_phase = "idle"
                self._dialogue_last_turn_id = 0
                self._dialogue_last_error = None
                self._dialogue_state_extension = {}
            self._persist_dialogue_state()
            return

        p = str(raw.get("phase") or "idle")
        tid = int(raw.get("last_turn_id") or 0)
        le_raw = raw.get("last_error")
        le = le_raw.strip() if isinstance(le_raw, str) else None

        if p in self._DIALOGUE_STALE_PHASES:
            recovered = True
            recovered_msg = (
                "上次会话可能未正常结束（程序关闭或崩溃时已处于生成中），状态已重置为空闲。"
            )
            with self._dialogue_lock:
                self._dialogue_phase = "idle"
                self._dialogue_last_turn_id = tid
                self._dialogue_last_error = recovered_msg
                self._dialogue_state_extension = {}
            self._persist_dialogue_state()
        else:
            valid = {
                "idle",
                "streaming",
                "react_running",
                "team_running",
                "followup_pending",
            }
            np: DialoguePhase = p if p in valid else "idle"  # type: ignore[assignment]
            ext_raw = raw.get("state_extension")
            ext_merged: dict[str, Any] = (
                dict(ext_raw) if isinstance(ext_raw, dict) else {}
            )
            with self._dialogue_lock:
                self._dialogue_phase = np
                self._dialogue_last_turn_id = tid
                self._dialogue_last_error = le if le else None
                self._dialogue_state_extension = ext_merged
            self._persist_dialogue_state()

        if recovered and self._persona_emit:
            try:
                self._persona_emit(
                    {
                        "type": "state.changed",
                        "phase": "idle",
                        "last_turn_id": tid,
                        "recovered": True,
                        "message": recovered_msg,
                        "state_extension": {},
                    }
                )
            except Exception:
                pass

    def get_dialogue_phase_snapshot(self) -> dict[str, Any]:
        """供调试或 Api；与 llm_busy 独立。"""
        with self._dialogue_lock:
            phase = self._dialogue_phase
            tid = self._dialogue_last_turn_id
            err = self._dialogue_last_error
            ext = dict(self._dialogue_state_extension)
        with self._llm_busy_lock:
            busy = self._llm_busy_depth
        return {
            "phase": phase,
            "last_turn_id": tid,
            "llm_busy_depth": busy,
            "last_error": err,
            "state_extension": ext,
        }

    @contextmanager
    def llm_busy(self):
        """标记本进程正占用 LLM（对话 / ReAct / 记忆抽取等），供闲时记忆任务避让。"""
        with self._llm_busy_lock:
            self._llm_busy_depth += 1
        try:
            yield
        finally:
            with self._llm_busy_lock:
                self._llm_busy_depth -= 1

    def is_idle_for_auto_memory(self) -> bool:
        with self._llm_busy_lock:
            if self._llm_busy_depth > 0:
                return False
        pr = self._persona_rt
        if pr is not None and pr.is_streaming():
            return False
        cr = self._chat_rt
        if cr is not None and cr.is_streaming():
            return False
        rt = self._react_thread
        if rt is not None and rt.is_alive():
            return False
        return True

    def is_idle_for_context_compress(self) -> bool:
        """与闲时压缩：需无流式/ReAct、llm_busy 为 0，且对话相位为 idle。"""
        if not self.is_idle_for_auto_memory():
            return False
        with self._dialogue_lock:
            return self._dialogue_phase == "idle"

    @staticmethod
    def _normalize_checkpoint(ck: ContextCheckpoint, n_messages: int) -> ContextCheckpoint:
        if ck.anchor_message_index > n_messages:
            return ck.model_copy(update={"anchor_message_index": n_messages})
        return ck

    def _persist_context_checkpoint(self) -> None:
        sid = self._active_id
        if not sid:
            return
        try:
            self._store.save_context_checkpoint(sid, self._context_checkpoint)
        except Exception:
            pass

    def _maybe_compress_until_under_budget(
        self, rebuild: Callable[[], list[dict[str, str]]]
    ) -> None:
        """在发主 LLM 前：整包 token 超阈值则多轮压缩检查点。"""
        cc = self._cfg.context_compression
        if not cc.enabled or not self._active_id:
            return
        budget = max(4096, int(cc.context_token_budget))
        thresh = float(cc.pre_send_threshold)
        with self._context_compress_lock:
            for _ in range(8):
                if estimate_tokens_messages(rebuild()) <= budget * thresh:
                    return
                raw_flat = raw_flat_from_stored_messages(self._messages)
                with self.llm_busy():
                    self._context_checkpoint = run_compression_round(
                        self._cfg, raw_flat, self._context_checkpoint
                    )
                self._persist_context_checkpoint()

    def _maybe_compress_history_until_budget(self) -> None:
        """仅按 messages_for_llm() 估算（ReAct/闲时/发后等，不含主 system）。"""
        cc = self._cfg.context_compression
        if not cc.enabled or not self._active_id:
            return
        budget = max(4096, int(cc.context_token_budget))
        thresh = float(cc.pre_send_threshold)

        def hist() -> list[dict[str, str]]:
            return list(self.messages_for_llm())

        with self._context_compress_lock:
            for _ in range(8):
                if estimate_tokens_messages(hist()) <= budget * thresh:
                    return
                raw_flat = raw_flat_from_stored_messages(self._messages)
                with self.llm_busy():
                    self._context_checkpoint = run_compression_round(
                        self._cfg, raw_flat, self._context_checkpoint
                    )
                self._persist_context_checkpoint()

    def try_idle_context_compress(self) -> None:
        """供内置调度线程：空闲且达间隔时若历史仍偏大则压一轮。"""
        cc = self._cfg.context_compression
        if not cc.enabled or cc.idle_compress_interval_sec <= 0:
            return
        if not self.is_idle_for_context_compress():
            return
        now = time.monotonic()
        if now - self._last_idle_compress_mono < float(cc.idle_compress_interval_sec):
            return
        budget = max(4096, int(cc.context_token_budget))
        if estimate_tokens_messages(self.messages_for_llm()) <= budget * float(
            cc.pre_send_threshold
        ):
            return
        with self._context_compress_lock:
            raw_flat = raw_flat_from_stored_messages(self._messages)
            with self.llm_busy():
                self._context_checkpoint = run_compression_round(
                    self._cfg, raw_flat, self._context_checkpoint
                )
            self._persist_context_checkpoint()
        self._last_idle_compress_mono = time.monotonic()

    def maybe_compress_post_reply_if_needed(self) -> None:
        """可选：回复落盘后若历史仍超阈值则压一轮（需 post_reply_compress）。"""
        cc = self._cfg.context_compression
        if not cc.enabled or not cc.post_reply_compress or not self._active_id:
            return
        if not self.is_idle_for_context_compress():
            return
        self._maybe_compress_history_until_budget()

    def build_persona_turn_call_messages(
        self, system_block: str, user_text: str
    ) -> list[dict[str, str]]:
        """拟人模式一轮：与 build_safe_chat_call_messages 一致走发前压缩。"""

        def rebuild() -> list[dict[str, str]]:
            cm = [{"role": "system", "content": system_block}]
            cm.extend(self.messages_for_llm())
            cm.append({"role": "user", "content": user_text})
            return cm

        self._maybe_compress_until_under_budget(rebuild)
        return rebuild()

    def set_persona_emit(self, fn: Any) -> None:
        """由 app.Api 注入：把拟人事件推到前端（如 pywebview evaluate_js）。"""
        self._persona_emit = fn

    def set_react_stream_emit(self, fn: Any) -> None:
        """由 app.Api 注入：ReAct 执行过程中推送步骤摘要（react.start / progress / done）。"""
        self._react_stream_emit = fn

    def _stop_chat_stream(self) -> None:
        if self._chat_rt:
            self._chat_rt.shutdown()
            self._chat_rt = None

    def _stop_react_worker(self) -> None:
        self._react_cancel.set()
        t = self._react_thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
        self._react_thread = None
        self._react_cancel.clear()

    def _ensure_chat_stream(self) -> SafeChatStreamRuntime:
        if self._chat_rt is None:

            def emit(evt: dict) -> None:
                if self._persona_emit:
                    self._persona_emit(evt)

            self._chat_rt = SafeChatStreamRuntime(self, emit=emit)
        return self._chat_rt

    def _sync_chat_stream_runtime(self) -> None:
        self._stop_chat_stream()
        if (
            self._meta is not None
            and self._meta.mode == "chat"
            and self._meta.session_variant == "standard"
        ):
            self._ensure_chat_stream().start()

    def _chat_system_block_with_extras(self, memory_extra: str = "") -> str:
        skills_prompt = build_safe_skills_prompt()
        extras = [action_card_system_hint()]
        if skills_prompt:
            extras.insert(0, skills_prompt)
        kb = self._kb_system_extra()
        if kb:
            extras.append(kb)
        system_block = build_system_block(extra_system="\n\n".join(extras))
        if memory_extra:
            system_block = system_block + "\n\n" + memory_extra
        return system_block

    def _assemble_safe_chat_call_messages(
        self, user_text: str, *, memory_extra: str = ""
    ) -> list[dict[str, str]]:
        system_block = self._chat_system_block_with_extras(memory_extra)
        call_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_block}
        ]
        call_messages.extend(self.messages_for_llm())
        call_messages.append({"role": "user", "content": user_text})
        return call_messages

    def _assemble_followup_card_chat_messages(self, memory_extra: str) -> list[dict[str, str]]:
        """卡片跟进：与对话模式相同 system，仅历史 messages_for_llm（无额外 user 行）。"""
        system_block = self._chat_system_block_with_extras(memory_extra)
        return [
            {"role": "system", "content": system_block},
            *self.messages_for_llm(),
        ]

    def build_safe_chat_call_messages(
        self, user_text: str, *, memory_extra: str = ""
    ) -> list[dict[str, str]]:
        def rebuild() -> list[dict[str, str]]:
            return self._assemble_safe_chat_call_messages(
                user_text, memory_extra=memory_extra
            )

        self._maybe_compress_until_under_budget(rebuild)
        return rebuild()

    def supersede_pending_cards_and_append_assistant(
        self, content: str, *, card: dict[str, Any]
    ) -> None:
        assert self._active_id is not None
        supersede_pending_cards(self._messages)
        self._messages.append(
            {"role": "assistant", "content": content, "card": card}
        )
        self._store.save_messages(self._active_id, self._messages)
        self._meta, self._messages = self._store.load(self._active_id)

    def interrupt_turn(self) -> None:
        """打断拟人 / 安全模式流式回复或 ReAct 智能体循环。"""
        if self._persona_rt:
            self._persona_rt.interrupt()
        if self._chat_rt:
            self._chat_rt.interrupt()
        self._react_cancel.set()

    @property
    def store(self) -> SessionStore:
        return self._store

    def llm_config(self) -> LLMConfig:
        return self._llm

    def update_llm_config(self, llm: LLMConfig) -> None:
        """界面保存后更新内存中的 LLM 配置（与 ruyi72.local.yaml 一致）。"""
        self._cfg = self._cfg.model_copy(update={"llm": llm})
        self._llm = llm

    def persona_config(self) -> PersonaConfig:
        return self._cfg.persona

    def active_session_id(self) -> str | None:
        return self._active_id

    def is_session_active(self, session_id: str) -> bool:
        """当前前台活动会话是否为给定 id（用于定时任务 run_when_session_inactive==False）。"""
        return (self._active_id or "") == (session_id or "").strip()

    def session_path_for(self, session_id: str) -> Path:
        return self._store.root / session_id

    def messages_snapshot(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def messages_for_llm(self) -> list[dict[str, str]]:
        """传给 LLM：role+content，并应用 context_checkpoint（摘要 + anchor 尾部）；可选阶段 A 截断。"""
        raw = raw_flat_from_stored_messages(self._messages)
        tail = apply_checkpoint_to_flat(raw, self._context_checkpoint)
        if self._cfg.context_compression.enabled:
            tail = phase_a_trim_long_messages(
                tail,
                max_chars=int(self._cfg.context_compression.max_message_chars_phase_a),
            )
        return tail

    def consume_memory_bootstrap_for_persona(self) -> str:
        if self._memory_bootstrap_pending:
            self._memory_bootstrap_pending = False
            return build_memory_bootstrap_block()
        return ""

    def build_proactive_nudge_message(self) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "你是贴心助手。用户一段时间没有发消息。请生成一句简短、自然、"
                    "不过分打扰的承接或关心，不超过 50 字；不要罗列多个问题。"
                ),
            },
            {"role": "user", "content": "只输出这一句话。"},
        ]

    def _try_skill_load(self, text: str) -> tuple[bool, str, bool]:
        skill_name = text.split(":", 1)[1].strip()
        if not skill_name:
            return False, "技能名称为空，例如：加载技能: deep-research", True
        reg = get_registry()
        sm = reg.get_by_name(skill_name)
        if sm is None:
            return (
                False,
                f"未找到名为 {skill_name!r} 的技能，请确认 name 是否与 SKILL.md 头部一致。",
                True,
            )
        doc = reg.read_full(sm)
        if sm.level >= 2:
            prefix = (
                f"技能 {sm.name} 属于 warn_act(2) 高危技能：可能涉及磁盘/进程/服务/云盘/数据库/剪贴板等敏感操作。\n"
                f"在据此执行真实操作前，请你先向用户解释风险，并等待用户在对话中明确确认，例如：「我确认使用 {sm.name} 技能 执行 XXX」。\n\n"
            )
            return True, prefix + doc, False
        return True, doc, False

    def _stop_persona(self) -> None:
        if self._persona_rt:
            self._persona_rt.shutdown()
            self._persona_rt = None

    def _ensure_persona(self) -> PersonaRuntime:
        if self._persona_rt is None:

            def emit(evt: dict) -> None:
                if self._persona_emit:
                    self._persona_emit(evt)

            self._persona_rt = PersonaRuntime(self, emit=emit)
        return self._persona_rt

    def _sync_persona_runtime(self) -> None:
        self._stop_persona()
        if (
            self._meta is not None
            and self._meta.mode == "persona"
            and self._meta.session_variant == "standard"
        ):
            self._ensure_persona().start()

    def persona_prepare_turn(self, text: str) -> bool:
        assert self._active_id is not None and self._meta is not None
        ws = (self._meta.workspace or "").strip()
        if not ws:
            return False
        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return False
        self._messages.append({"role": "user", "content": text})
        self._store.save_messages(self._active_id, self._messages)
        return True

    def persona_append_assistant(self, content: str) -> None:
        assert self._active_id is not None
        self._messages.append({"role": "assistant", "content": content})
        self._store.save_messages(self._active_id, self._messages)
        self._meta, _ = self._store.load(self._active_id)

    def persona_send(self, text: str) -> dict:
        self.ensure_session()
        assert self._active_id is not None and self._meta is not None
        t = (text or "").strip()
        if not t:
            return {"ok": False, "error": "请输入内容。", "sync": True}
        if self._meta.session_variant == "team":
            return {"ok": False, "error": "团队会话不支持拟人模式。", "sync": True}
        if self._meta.mode != "persona":
            return {"ok": False, "error": "当前会话不是拟人模式。", "sync": True}
        if t.startswith("加载技能:"):
            ok, msg, ae = self._try_skill_load(t)
            return {"ok": ok, "sync": True, "message": msg, "append_error": ae}
        ws = (self._meta.workspace or "").strip()
        if not ws:
            return {
                "ok": False,
                "sync": True,
                "message": "请先在侧栏或上方设置「工作区」为有效文件夹路径。",
                "append_error": True,
            }
        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return {
                "ok": False,
                "sync": True,
                "message": f"工作区不存在或不是目录: {root}",
                "append_error": True,
            }
        self._ensure_persona().start()
        self._persona_rt.notify_user_activity()
        tid = self._persona_rt.enqueue_user_text(t)
        return {"ok": True, "async": True, "turn_id": tid}

    def persona_interrupt(self) -> dict:
        if self._persona_rt:
            self._persona_rt.interrupt()
        return {"ok": True}

    def persona_resume(self) -> dict:
        self.ensure_session()
        assert self._active_id is not None
        if self._persona_rt:
            self._persona_rt.clear_pause()
        else:
            p = self.session_path_for(self._active_id) / CHECKPOINT_NAME
            if p.is_file():
                import json as _json

                try:
                    data = _json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        data["paused"] = False
                        data["pause_reason"] = ""
                        p.write_text(
                            _json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                except (OSError, _json.JSONDecodeError):
                    pass
        return {"ok": True}

    def persona_pause(self, reason: str = "") -> dict:
        self.ensure_session()
        if self._persona_rt:
            self._persona_rt.set_pause(reason)
        elif self._active_id:
            p = self.session_path_for(self._active_id) / CHECKPOINT_NAME
            import json as _json

            try:
                data: dict = {"paused": True, "pause_reason": reason}
                if p.is_file():
                    cur = _json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(cur, dict):
                        cur.update(data)
                        data = cur
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
        return {"ok": True}

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
            self._memory_bootstrap_pending = True
            self._context_checkpoint = ContextCheckpoint()
            self._last_idle_compress_mono = 0.0

    def list_sessions(self) -> list[dict]:
        return [m.model_dump() for m in self._store.list_sessions()]

    def search_sessions_text(self, query: str) -> list[dict[str, Any]]:
        return self._store.search_full_text(query or "")

    def create_session(self, title: str | None = None) -> dict:
        m = self._store.create_session(title=title, react_max_steps=self._react_default)
        return self.open_session(m.id)

    def create_team_session(self, team_size: int, title: str | None = None) -> dict:
        m_count = len(self._cfg.team.models)
        if m_count < 2:
            raise ValueError("请先在 ruyi72.yaml 中配置至少 2 条 team.models。")
        cap = min(4, m_count)
        if not (2 <= team_size <= cap):
            raise ValueError(f"团队人数须在 2～{cap} 之间（当前已配置 {m_count} 个模型）。")
        m = self._store.create_team_session(
            team_size,
            title=title,
            react_max_steps=self._react_default,
        )
        return self.open_session(m.id)

    def create_knowledge_session(
        self, kb_preset: str | None = None, title: str | None = None
    ) -> dict:
        m = self._store.create_knowledge_session(
            kb_preset=kb_preset or "general",
            title=title,
            react_max_steps=self._react_default,
        )
        return self.open_session(m.id)

    def open_session(self, session_id: str) -> dict:
        self._stop_persona()
        self._stop_chat_stream()
        self._stop_react_worker()
        meta, messages = self._store.load(session_id)
        self._active_id = session_id
        self._meta = meta
        self._messages = messages
        self._memory_bootstrap_pending = True
        ck = self._store.load_context_checkpoint(session_id)
        self._context_checkpoint = self._normalize_checkpoint(
            ck if ck is not None else ContextCheckpoint(),
            len(self._messages),
        )
        self._last_idle_compress_mono = 0.0
        self._sync_persona_runtime()
        self._sync_chat_stream_runtime()
        self._reconcile_dialogue_state_after_load()
        return {"meta": self._meta.model_dump(), "messages": list(self._messages)}

    def get_active(self) -> dict:
        self.ensure_session()
        assert self._meta is not None and self._active_id is not None
        return {"meta": self._meta.model_dump(), "messages": list(self._messages)}

    def append_message_from_scheduler(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
    ) -> None:
        """内置定时任务写入消息（写盘；若该会话为当前活动会话则同步内存）。"""
        sid = (session_id or "").strip()
        if not sid:
            raise ValueError("session_id 为空")
        if role not in ("user", "assistant", "system"):
            raise ValueError("role 须为 user / assistant / system")
        _, messages = self._store.load(sid)
        messages.append({"role": role, "content": content})
        self._store.save_messages(sid, messages)
        if self._active_id == sid:
            self._meta, self._messages = self._store.load(sid)

    def _resolve_scheduler_workspace(self, *, kind: str, session_id: str | None) -> str:
        """全局任务使用 ~/.ruyi72；会话任务优先使用会话工作区（否则回退 ~/.ruyi72）。"""
        home_ruyi = str((Path.home() / ".ruyi72").resolve())
        if kind != "session":
            return home_ruyi
        sid = (session_id or "").strip()
        if not sid:
            return home_ruyi
        try:
            meta, _ = self._store.load(sid)
        except Exception:
            return home_ruyi
        ws = (meta.workspace or "").strip()
        if not ws:
            return home_ruyi
        p = Path(ws).expanduser().resolve()
        return str(p) if p.is_dir() else home_ruyi

    def run_scheduler_llm_once(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        ask_only: bool = False,
        task_kind: str = "global",
        session_id: str | None = None,
    ) -> str:
        """内置定时任务单次调用当前 LLM 配置；不计入会话历史。安全模式走仅 SAFE 工具的 Agent。"""
        user_t = (user_prompt or "").strip()
        if not user_t:
            raise ValueError("user_prompt 为空")
        raw_sys = (system_prompt or "").strip()

        user_sched = f"[定时任务]\n\n{user_t}"

        if ask_only:
            ws = self._resolve_scheduler_workspace(kind=task_kind, session_id=session_id)
            ms = max(4, min(24, self._react_default))
            ok, text = run_scheduler_safe_agent(
                self._llm,
                workspace=ws,
                user_prompt=user_sched,
                extra_system=raw_sys,
                max_steps=ms,
            )
            if not ok:
                raise OllamaClientError(text)
            return strip_action_card_markers(text)

        base = raw_sys if raw_sys else "你是智能助手。请根据用户说明直接作答，简洁准确。"
        sys_t = base + "\n\n" + SCHEDULED_TASK_REPLY_RULES
        messages: list[dict[str, str]] = [
            {"role": "system", "content": sys_t},
            {"role": "user", "content": user_sched},
        ]
        with self.llm_busy():
            reply = OllamaClient(self._llm).chat(
                messages,
                caller="ConversationService.run_scheduler_llm_once",
            )
        visible, _card = split_reply_action_card(reply)
        out = (visible or "").strip() if (visible or "").strip() else (reply or "").strip()
        return strip_action_card_markers(out)

    def _kb_system_extra(self) -> str | None:
        if self._meta is None or self._meta.session_variant != "knowledge":
            return None
        return knowledge_base_system_hint(self._meta.kb_preset)

    def preview_workspace_file(
        self, rel_path: str, *, max_chars: int = 120_000
    ) -> dict[str, Any]:
        """供 UI 分屏预览：路径相对当前会话工作区，约束同 ReAct read_file。"""
        self.ensure_session()
        assert self._meta is not None
        ws = (self._meta.workspace or "").strip()
        if not ws:
            return {"ok": False, "error": "工作区未设置。"}
        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return {"ok": False, "error": f"工作区不存在或不是目录: {root}"}
        try:
            target = safe_child(root, rel_path)
        except ToolError as e:
            return {"ok": False, "error": str(e)}
        if not target.is_file():
            return {"ok": False, "error": f"不是文件或不存在: {rel_path}"}
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"ok": False, "error": f"读取失败: {e!s}"}
        if len(text) > max_chars:
            text = text[:max_chars] + "\n…(已截断)"
        return {"ok": True, "content": text}

    def list_workspace_preview(
        self, rel_path: str = ".", *, max_entries: int = 500
    ) -> dict[str, Any]:
        """分屏目录预览：列出工作区内某相对目录的条目信息（名称/类型/大小/mtime），不读取文件内容。"""
        self.ensure_session()
        assert self._meta is not None
        ws = (self._meta.workspace or "").strip()
        if not ws:
            return {"ok": False, "error": "工作区未设置。"}
        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return {"ok": False, "error": f"工作区不存在或不是目录: {root}"}
        rel = (rel_path or ".").strip().replace("\\", "/") or "."
        try:
            target = safe_child(root, rel)
        except ToolError as e:
            return {"ok": False, "error": str(e)}
        if not target.is_dir():
            return {"ok": False, "error": f"不是目录或不存在: {rel}"}
        try:
            path_key = str(target.relative_to(root)).replace("\\", "/")
        except ValueError:
            path_key = ""
        if path_key == ".":
            path_key = ""
        if not path_key:
            parent_key: str | None = None
        else:
            parent = Path(path_key).parent
            ps = str(parent).replace("\\", "/")
            parent_key = "" if ps == "." else ps

        entries: list[dict[str, Any]] = []
        truncated = False
        try:
            children = sorted(target.iterdir(), key=lambda p: p.name.lower())
        except OSError as e:
            return {"ok": False, "error": f"列出失败: {e!s}"}
        for c in children:
            if len(entries) >= max_entries:
                truncated = True
                break
            try:
                st = c.stat()
            except OSError:
                continue
            is_dir = c.is_dir()
            mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
            entries.append(
                {
                    "name": c.name,
                    "kind": "dir" if is_dir else "file",
                    "size": None if is_dir else int(st.st_size),
                    "mtime": mtime,
                }
            )
        return {
            "ok": True,
            "path": path_key,
            "parent": parent_key,
            "entries": entries,
            "truncated": truncated,
        }

    def update_session(
        self,
        *,
        title: str | None = None,
        workspace: str | None = None,
        mode: str | None = None,
        react_max_steps: int | float | None = None,
        avatar_mode: str | None = None,
        avatar_ref: str | None = None,
    ) -> dict:
        self.ensure_session()
        assert self._active_id is not None
        mode_t: Mode | None = None
        if mode is not None:
            if mode not in ("chat", "react", "persona"):
                raise ValueError("mode 必须是 chat、react 或 persona")
            if self._meta.session_variant == "team" and mode == "react":
                raise ValueError("团队会话不能使用 ReAct 模式。")
            if self._meta.session_variant == "team" and mode == "persona":
                raise ValueError("团队会话不能使用拟人模式。")
            if self._meta.session_variant == "knowledge" and mode == "persona":
                raise ValueError("知识库会话不能使用拟人模式。")
            mode_t = mode  # type: ignore[assignment]
        steps: int | None = None
        if react_max_steps is not None:
            steps = int(react_max_steps)
        am: AvatarMode | None = None
        if avatar_mode is not None:
            if avatar_mode not in ("off", "live2d", "pixel"):
                raise ValueError("avatar_mode 须为 off、live2d 或 pixel")
            am = avatar_mode  # type: ignore[assignment]
        ar: str | None = None
        if avatar_ref is not None:
            ar = str(avatar_ref)
        meta = self._store.update_meta(
            self._active_id,
            title=title,
            workspace=workspace,
            mode=mode_t,
            react_max_steps=steps,
            avatar_mode=am,
            avatar_ref=ar,
        )
        self._meta = meta
        self._sync_persona_runtime()
        self._sync_chat_stream_runtime()
        return {"meta": meta.model_dump()}

    def rename_session(self, session_id: str, title: str) -> dict:
        """按 id 更新标题（可为非当前会话）。"""
        self.ensure_session()
        t = (title or "").strip() or "新对话"
        try:
            meta = self._store.update_meta(session_id, title=t)
        except FileNotFoundError:
            return {"ok": False, "error": "会话不存在。"}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if self._active_id == session_id:
            self._meta = meta
            self._sync_persona_runtime()
            self._sync_chat_stream_runtime()
        return {"ok": True, "meta": meta.model_dump()}

    def delete_session(self, session_id: str) -> dict:
        self.ensure_session()
        assert self._active_id is not None
        if session_id == self._active_id:
            self._stop_persona()
            self._stop_chat_stream()
            self._stop_react_worker()
        try:
            self._store.delete_session(session_id)
        except FileNotFoundError:
            return {"ok": False, "error": "会话不存在或已删除。"}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if session_id == self._active_id:
            sessions = self._store.list_sessions()
            if sessions:
                return self.open_session(sessions[0].id)
            m = self._store.create_session(react_max_steps=self._react_default)
            return self.open_session(m.id)
        return {"ok": True}

    def _chat_style_followup_after_card(self, memory_extra: str) -> str | None:
        """在已有历史（含卡片确认 user 行）上走一轮与对话模式相同的 Chat，追加 assistant。"""
        assert self._meta is not None
        ws = (self._meta.workspace or "").strip()
        if not ws:
            return "请先在侧栏或上方设置「工作区」为有效文件夹路径。"
        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return f"工作区不存在或不是目录: {root}"
        def rebuild_fu() -> list[dict[str, str]]:
            return self._assemble_followup_card_chat_messages(memory_extra)

        self._maybe_compress_until_under_budget(rebuild_fu)
        call_messages = rebuild_fu()
        try:
            with self.llm_busy():
                reply = OllamaClient(self._llm).chat(
                    call_messages,
                    caller="ConversationService._chat_style_followup_after_card",
                )
        except OllamaClientError as e:
            return str(e)
        visible, card = split_reply_action_card(reply)
        content = visible.strip() if visible else ""
        if card is not None:
            if not content:
                content = str(card.get("title") or "").strip() or "请确认下列设置。"
            supersede_pending_cards(self._messages)
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": content,
                "card": card,
            }
        else:
            assistant_msg = {"role": "assistant", "content": content or reply}
        self._messages.append(assistant_msg)
        return None

    def _followup_llm_after_action_card(self) -> str | None:
        """
        仅由「确认」或「超时自动确认」路径调用：user 摘要已写入历史后，自动请求模型下一条回复。
        「拒绝」不得调用本方法，以免再次触发模型输出卡片。
        拟人模式：使用与对话相同的一次 Chat（不走路径异步拟人管道），避免无回复。
        """
        self.ensure_session()
        assert self._active_id is not None and self._meta is not None
        if not self._messages or self._messages[-1].get("role") != "user":
            return None
        user_text = str(self._messages[-1].get("content") or "").strip()
        if not user_text.startswith("（卡片确认）"):
            return None

        memory_extra = ""
        if self._memory_bootstrap_pending:
            memory_extra = build_memory_bootstrap_block()
            self._memory_bootstrap_pending = False

        try:
            if self._meta.session_variant == "team":
                ts = self._meta.team_size
                m_count = len(self._cfg.team.models)
                if ts is None or not (2 <= ts <= 4):
                    return "团队会话元数据无效。"
                if ts > m_count:
                    return f"team.models 仅 {m_count} 条，无法继续团队编排。"
                self._maybe_compress_history_until_budget()
                self.set_dialogue_phase("team_running")
                try:
                    try:
                        with self.llm_busy():
                            reply = run_team_turn(
                                self._cfg,
                                team_size=ts,
                                prior_messages=list(self.messages_for_llm()[:-1]),
                                user_text=user_text,
                                memory_extra=memory_extra or None,
                                slot_progress=self._on_team_slot_progress,
                            )
                    except ValueError as e:
                        self._messages.append({"role": "assistant", "content": str(e)})
                    except OllamaClientError as e:
                        self._messages.append({"role": "assistant", "content": str(e)})
                    else:
                        self._messages.append({"role": "assistant", "content": reply})
                finally:
                    self.set_dialogue_phase("idle")
            elif self._meta.mode == "react":
                ws = (self._meta.workspace or "").strip()
                if not ws:
                    return "请先在侧栏或上方设置「工作区」为有效文件夹路径。"
                root = Path(ws).expanduser().resolve()
                if not root.is_dir():
                    return f"工作区不存在或不是目录: {root}"
                sched_ctx = (
                    (self, self._active_id) if self._active_id else None
                )
                self.set_dialogue_phase("react_running")
                try:
                    self._maybe_compress_history_until_budget()
                    work = list(self.messages_for_llm())
                    with self.llm_busy():
                        ok, _out = run_react(
                            self._llm,
                            work,
                            workspace=str(root),
                            max_steps=self._meta.react_max_steps,
                            memory_bootstrap=memory_extra or None,
                            extra_system=self._kb_system_extra(),
                            scheduler_context=sched_ctx,
                            stream_emit=self._react_stream_emit,
                            step_progress=self._on_react_step_index,
                        )
                    if ok or (isinstance(_out, str) and "已中断" in _out):
                        self._messages.clear()
                        self._messages.extend(work)
                        if ok:
                            self._parse_action_card_on_last_assistant(self._messages)
                finally:
                    self.set_dialogue_phase("idle")
            else:
                self.set_dialogue_phase("followup_pending")
                try:
                    err = self._chat_style_followup_after_card(memory_extra)
                finally:
                    self.set_dialogue_phase("idle")
                if err:
                    return err

            self._store.save_messages(self._active_id, self._messages)
            self._meta, self._messages = self._store.load(self._active_id)
        except OllamaClientError as e:
            return str(e)
        except ValueError as e:
            return str(e)
        return None

    def submit_action_card(
        self,
        card_id: str,
        action: str,
        selected_ids: list[Any] | None = None,
        *,
        from_timeout: bool = False,
    ) -> dict[str, Any]:
        """处理确认卡片：更新 assistant 消息中的 card，并追加一条 user 摘要。"""
        self.ensure_session()
        assert self._active_id is not None
        cid = (card_id or "").strip()
        act = (action or "").strip().lower()
        if act not in ("confirm", "reject"):
            return {"ok": False, "error": "action 须为 confirm 或 reject。"}
        if not cid:
            return {"ok": False, "error": "缺少 card_id。"}
        raw_ids = selected_ids if isinstance(selected_ids, list) else []
        picked = [str(x).strip()[:64] for x in raw_ids if x is not None and str(x).strip()]

        card_ref: dict[str, Any] | None = None
        option_list: list[Any] = []
        for m in self._messages:
            if m.get("role") != "assistant":
                continue
            c = m.get("card")
            if not isinstance(c, dict):
                continue
            if str(c.get("id")) != cid:
                continue
            if c.get("status") != "pending":
                return {"ok": False, "error": "卡片已处理。"}
            card_ref = c
            option_list = c.get("options") if isinstance(c.get("options"), list) else []
            break

        if card_ref is None:
            return {"ok": False, "error": "卡片不存在或已处理。"}

        valid = {
            str(o.get("id"))
            for o in option_list
            if isinstance(o, dict) and o.get("id") is not None
        }
        picked = [x for x in picked if x in valid]
        label_by_id = {
            str(o.get("id")): str(o.get("label") or o.get("id"))
            for o in option_list
            if isinstance(o, dict) and o.get("id") is not None
        }
        labels = [label_by_id.get(i, i) for i in picked]
        joined = ", ".join(labels) if labels else "（无）"

        if act == "reject":
            card_ref["status"] = "rejected"
            card_ref["selected_ids"] = []
            card_ref["resolved_at"] = utc_now_iso()
            card_ref.pop("via", None)
            summary = "（卡片确认）已拒绝。"
        else:
            if from_timeout:
                card_ref["status"] = "expired"
                card_ref["via"] = "timeout"
            else:
                card_ref["status"] = "confirmed"
                card_ref.pop("via", None)
            card_ref["selected_ids"] = picked
            card_ref["resolved_at"] = utc_now_iso()
            if from_timeout:
                summary = f"（卡片确认）已超时自动确认，选用：{joined}。"
            else:
                summary = f"（卡片确认）已确认，选用：{joined}。"

        self._messages.append({"role": "user", "content": summary})
        self._store.save_messages(self._active_id, self._messages)
        self._meta, self._messages = self._store.load(self._active_id)

        followup_error = (
            None
            if act == "reject"
            else self._followup_llm_after_action_card()
        )
        return {
            "ok": True,
            "meta": self._meta.model_dump(),
            "messages": list(self._messages),
            "followup_error": followup_error,
        }

    def _parse_action_card_on_last_assistant(self, messages: list[dict[str, Any]]) -> None:
        """从最近一条 assistant 正文中提取 ```action_card```，写入 card 并 supersede 旧 pending。"""
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if m.get("role") != "assistant":
                continue
            c = m.get("content")
            if not isinstance(c, str):
                return
            visible, card = split_reply_action_card(c)
            if card is None:
                return
            content = visible.strip() if visible else ""
            if not content:
                content = str(card.get("title") or "").strip() or "请确认下列设置。"
            supersede_pending_cards(messages)
            messages[i] = {"role": "assistant", "content": content, "card": card}
            return

    def send_message(self, text: str) -> dict[str, Any]:
        """
        返回 dict：ok, message, append_error, async（是否仅后台流式完成）, sync（同步错误时 True）。
        """
        self.ensure_session()
        assert self._active_id is not None and self._meta is not None

        text = (text or "").strip()
        if not text:
            return {
                "ok": False,
                "message": "请输入内容。",
                "append_error": True,
                "sync": True,
                "async": False,
            }

        sv = getattr(self._meta, "session_variant", None)
        log_send_message_context(
            "ConversationService.send_message",
            mode=str(self._meta.mode),
            session_variant=str(sv) if sv else "",
            workspace_set=bool((self._meta.workspace or "").strip()),
        )

        if self._meta.mode == "persona" and self._meta.session_variant == "standard":
            r = self.persona_send(text)
            if r.get("sync"):
                return {
                    "ok": r["ok"],
                    "message": r.get("message", ""),
                    "append_error": r.get("append_error", False),
                    "sync": True,
                    "async": False,
                }
            return {
                "ok": bool(r.get("ok")),
                "message": "",
                "append_error": False,
                "async": True,
            }

        # 特殊命令：加载技能文档（Ask 模式下的渐进披露）
        if text.startswith("加载技能:"):
            ok, msg, ae = self._try_skill_load(text)
            return {
                "ok": ok,
                "message": msg,
                "append_error": ae,
                "sync": True,
                "async": False,
            }

        ws = (self._meta.workspace or "").strip()
        if not ws:
            return {
                "ok": False,
                "message": "请先在侧栏或上方设置「工作区」为有效文件夹路径。",
                "append_error": True,
                "sync": True,
                "async": False,
            }

        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return {
                "ok": False,
                "message": f"工作区不存在或不是目录: {root}",
                "append_error": True,
                "sync": True,
                "async": False,
            }

        memory_extra = ""
        if self._memory_bootstrap_pending:
            memory_extra = build_memory_bootstrap_block()
            self._memory_bootstrap_pending = False

        if self._meta.session_variant == "team":
            ts = self._meta.team_size
            m_count = len(self._cfg.team.models)
            if ts is None or not (2 <= ts <= 4):
                return {
                    "ok": False,
                    "message": "团队会话元数据无效（缺少 team_size）。",
                    "append_error": True,
                    "sync": True,
                    "async": False,
                }
            if ts > m_count:
                return {
                    "ok": False,
                    "message": (
                        f"当前配置的 team.models 仅 {m_count} 条，小于本会话的 team_size={ts}。"
                        "请补充配置或改用标准会话。"
                    ),
                    "append_error": True,
                    "sync": True,
                    "async": False,
                }
            self._messages.append({"role": "user", "content": text})
            self._maybe_compress_history_until_budget()
            self.set_dialogue_phase("team_running")
            try:
                try:
                    with self.llm_busy():
                        reply = run_team_turn(
                            self._cfg,
                            team_size=ts,
                            prior_messages=list(self.messages_for_llm()[:-1]),
                            user_text=text,
                            memory_extra=memory_extra or None,
                            slot_progress=self._on_team_slot_progress,
                        )
                except ValueError as e:
                    self._messages.pop()
                    return {
                        "ok": False,
                        "message": str(e),
                        "append_error": True,
                        "sync": True,
                        "async": False,
                    }
                except OllamaClientError as e:
                    self._messages.pop()
                    return {
                        "ok": False,
                        "message": str(e),
                        "append_error": True,
                        "sync": True,
                        "async": False,
                    }
                self._messages.append({"role": "assistant", "content": reply})
                self._store.save_messages(self._active_id, self._messages)
                self._meta, _ = self._store.load(self._active_id)
                return {
                    "ok": True,
                    "message": reply,
                    "append_error": False,
                    "async": False,
                }
            finally:
                self.set_dialogue_phase("idle")

        if self._meta.mode == "chat":
            self._ensure_chat_stream().start()
            self._ensure_chat_stream().enqueue_user_text(text, memory_extra=memory_extra)
            return {
                "ok": True,
                "message": "",
                "append_error": False,
                "async": True,
            }

        # ReAct（普通）：后台线程执行，支持打断
        self._messages.append({"role": "user", "content": text})
        self._store.save_messages(self._active_id, self._messages)
        sid = self._active_id
        sched_ctx = (self, sid) if sid else None
        llm_cfg = self._llm
        root_s = str(root)
        r_steps = self._meta.react_max_steps
        mem_b = memory_extra
        kb_ex = self._kb_system_extra()
        r_emit = self._react_stream_emit
        self._stop_react_worker()

        def _react_worker() -> None:
            try:
                self.set_dialogue_phase("react_running")
                try:
                    self._maybe_compress_history_until_budget()
                    work = list(self.messages_for_llm())
                    with self.llm_busy():
                        ok, _out = run_react(
                            llm_cfg,
                            work,
                            workspace=root_s,
                            max_steps=r_steps,
                            memory_bootstrap=mem_b,
                            extra_system=kb_ex,
                            scheduler_context=sched_ctx,
                            stream_emit=r_emit,
                            cancel_check=lambda: self._react_cancel.is_set(),
                            step_progress=self._on_react_step_index,
                        )
                    if ok or (isinstance(_out, str) and "已中断" in _out):
                        self._messages.clear()
                        self._messages.extend(work)
                        if ok:
                            self._parse_action_card_on_last_assistant(self._messages)
                    self._store.save_messages(self._active_id, self._messages)
                    self._meta, _ = self._store.load(self._active_id)
                except Exception:
                    pass
                finally:
                    self.set_dialogue_phase("idle")
            finally:
                if self._persona_emit:
                    self._persona_emit({"type": "turn.finished", "turn_id": -1})
                self._react_thread = None

        self._react_thread = threading.Thread(
            target=_react_worker, name="react-worker", daemon=True
        )
        self._react_thread.start()
        return {
            "ok": True,
            "message": "",
            "append_error": False,
            "async": True,
        }
