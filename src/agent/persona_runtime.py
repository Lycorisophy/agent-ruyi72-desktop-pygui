"""拟人模式：事件驱动队列 + 可取消流式 LLM + 可选主动发言与轻量 checkpoint。"""

from __future__ import annotations

import json
import queue
import threading
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from src.agent.memory_tools import build_memory_bootstrap_block
from src.llm.ollama import OllamaClient, OllamaClientError
from src.llm.ollama_stream import stream_chat
from src.llm.prompts import build_system_block
from src.skills.loader import build_safe_skills_prompt

if TYPE_CHECKING:
    from src.service.conversation import ConversationService


FLUSH_INTERVAL_SEC = 0.05
PROACTIVE_TICK_SEC = 10.0
CHECKPOINT_NAME = "persona_checkpoint.json"


def _today_utc() -> str:
    return date.today().isoformat()


class PersonaRuntime:
    def __init__(
        self,
        svc: ConversationService,
        *,
        emit: Callable[[dict[str, Any]], None],
    ) -> None:
        self._svc = svc
        self._emit = emit
        self._q: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._cancel = threading.Event()
        self._turn_id = 0
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._streaming = False
        self._last_user_mono = time.monotonic()
        self._proactive_timer: threading.Timer | None = None
        self._flush_buf: list[tuple[str, str]] = []
        self._flush_deadline: float | None = None
        self._last_user_mono = time.monotonic()

    def start(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop.clear()
            self._worker = threading.Thread(target=self._run_worker, name="persona-runtime", daemon=True)
            self._worker.start()
        self._schedule_proactive()

    def shutdown(self) -> None:
        self._stop.set()
        self._cancel.set()
        if self._proactive_timer:
            self._proactive_timer.cancel()
            self._proactive_timer = None
        try:
            self._q.put_nowait(("STOP", None))
        except queue.Full:
            pass
        w = self._worker
        if w and w.is_alive():
            w.join(timeout=2.0)
        self._worker = None

    def enqueue_user_text(self, text: str) -> int:
        self._last_user_mono = time.monotonic()
        self._schedule_proactive()
        with self._lock:
            self._turn_id += 1
            tid = self._turn_id
        self._q.put(("send", (tid, text)))
        return tid

    def interrupt(self) -> None:
        self._cancel.set()
        self._q.put(("interrupt", None))

    def notify_user_activity(self) -> None:
        self._last_user_mono = time.monotonic()
        self._schedule_proactive()

    def is_streaming(self) -> bool:
        """是否处于拟人主对话流式生成中（用于闲时记忆任务避让）。"""
        return self._streaming

    def _checkpoint_path(self) -> Path | None:
        sid = self._svc.active_session_id()
        if not sid:
            return None
        return self._svc.session_path_for(sid) / CHECKPOINT_NAME

    def _read_checkpoint(self) -> dict[str, Any]:
        p = self._checkpoint_path()
        if not p or not p.is_file():
            return {
                "paused": False,
                "pause_reason": "",
                "proactive_date": "",
                "proactive_count": 0,
            }
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_checkpoint(self, data: dict[str, Any]) -> None:
        p = self._checkpoint_path()
        if not p:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def clear_pause(self) -> None:
        cp = self._read_checkpoint()
        cp["paused"] = False
        cp["pause_reason"] = ""
        self._write_checkpoint(cp)

    def set_pause(self, reason: str = "") -> None:
        cp = self._read_checkpoint()
        cp["paused"] = True
        cp["pause_reason"] = reason
        self._write_checkpoint(cp)

    def _schedule_proactive(self) -> None:
        if self._proactive_timer:
            self._proactive_timer.cancel()
            self._proactive_timer = None
        pc = self._svc.persona_config()
        if not pc.proactive_enabled:
            return

        def tick() -> None:
            if self._stop.is_set():
                return
            self._maybe_proactive()
            self._schedule_proactive()

        self._proactive_timer = threading.Timer(PROACTIVE_TICK_SEC, tick)
        self._proactive_timer.daemon = True
        self._proactive_timer.start()

    def _maybe_proactive(self) -> None:
        if self._stop.is_set() or self._streaming:
            return
        pc = self._svc.persona_config()
        if not pc.proactive_enabled:
            return
        cp = self._read_checkpoint()
        if cp.get("paused"):
            return
        idle = time.monotonic() - self._last_user_mono
        if idle < pc.proactive_idle_seconds:
            return
        today = _today_utc()
        cnt = int(cp.get("proactive_count") or 0)
        d = str(cp.get("proactive_date") or "")
        if d != today:
            cnt = 0
        if cnt >= pc.proactive_max_per_day:
            return
        try:
            msg = self._svc.build_proactive_nudge_message()
            with self._svc.llm_busy():
                reply = OllamaClient(self._svc.llm_config()).chat(
                    msg,
                    caller="persona_runtime.proactive_nudge",
                )
            line = (reply or "").strip()
            if not line:
                return
            self._svc.persona_append_assistant(line)
            self._emit_safe({"type": "agent.proactive", "text": line})
        except OllamaClientError:
            return
        cp = self._read_checkpoint()
        d_old = str(cp.get("proactive_date") or "")
        cnt = int(cp.get("proactive_count") or 0)
        if d_old != today:
            cnt = 1
        else:
            cnt = cnt + 1
        cp["proactive_date"] = today
        cp["proactive_count"] = cnt
        self._write_checkpoint(cp)
        self._last_user_mono = time.monotonic()

    def _emit_safe(self, evt: dict[str, Any]) -> None:
        try:
            self._emit(evt)
        except Exception:
            pass

    def _flush_deltas(self, force: bool = False) -> None:
        now = time.monotonic()
        if not self._flush_buf:
            self._flush_deadline = None
            return
        if not force and self._flush_deadline is not None and now < self._flush_deadline:
            return
        merged: dict[str, list[str]] = {"content": [], "thinking": []}
        for ch, t in self._flush_buf:
            merged.setdefault(ch, []).append(t)
        self._flush_buf.clear()
        self._flush_deadline = None
        for channel in ("thinking", "content"):
            parts = merged.get(channel)
            if parts:
                self._emit_safe(
                    {"type": "token.delta", "channel": channel, "text": "".join(parts)}
                )

    def _buffer_delta(self, channel: str, text: str) -> None:
        if not text:
            return
        self._flush_buf.append((channel, text))
        now = time.monotonic()
        if self._flush_deadline is None:
            self._flush_deadline = now + FLUSH_INTERVAL_SEC
        if now >= self._flush_deadline:
            self._flush_deltas(force=True)
        elif len(self._flush_buf) >= 24:
            self._flush_deltas(force=True)

    def _run_worker(self) -> None:
        while not self._stop.is_set():
            try:
                kind, payload = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "STOP":
                break
            if kind == "interrupt":
                self._cancel.set()
                continue
            if kind == "send":
                self._cancel.clear()
                pair = payload
                if isinstance(pair, tuple) and len(pair) == 2:
                    tid, raw = pair
                    self._run_turn(int(tid), str(raw or "").strip())
                else:
                    self._run_turn(self._turn_id, str(payload or "").strip())

    def _run_turn(self, tid: int, text: str) -> None:
        if not text:
            return
        self._streaming = True
        started_stream = False
        try:
            if not self._svc.persona_prepare_turn(text):
                self._emit_safe(
                    {"type": "error", "message": "工作区无效或无法保存用户消息。"}
                )
                return
            self._emit_safe({"type": "turn.started", "turn_id": tid, "user_text": text})
            self._svc.set_dialogue_phase("streaming", last_turn_id=tid)
            started_stream = True

            skills_prompt = build_safe_skills_prompt()
            system_block = build_system_block(extra_system=skills_prompt or None)
            mem = self._svc.consume_memory_bootstrap_for_persona()
            if mem:
                system_block = system_block + "\n\n" + mem

            call_messages = self._svc.build_persona_turn_call_messages(system_block, text)

            think = self._svc.persona_config().stream_think and self._svc.llm_config().api_mode == "native"

            def on_delta(ch: str, t: str) -> None:
                self._buffer_delta(ch, t)

            try:
                content, thinking = stream_chat(
                    self._svc.llm_config(),
                    call_messages,
                    on_delta=on_delta,
                    cancel_check=lambda: self._cancel.is_set(),
                    think=think,
                    caller="persona_runtime._run_turn",
                )
            except OllamaClientError as e:
                self._flush_deltas(force=True)
                self._emit_safe({"type": "error", "message": str(e)})
                return

            self._flush_deltas(force=True)

            if self._cancel.is_set():
                partial = content.strip()
                final_assistant = (
                    f"【已中断】{partial}" if partial else "【已中断】"
                )
                self._svc.persona_append_assistant(final_assistant)
                self._emit_safe({"type": "turn.cancelled", "turn_id": tid})
                self._emit_safe(
                    {
                        "type": "message.final",
                        "role": "assistant",
                        "content": final_assistant,
                        "thinking": thinking,
                    }
                )
            else:
                self._svc.persona_append_assistant(content)
                self._emit_safe({"type": "turn.completed", "turn_id": tid})
                self._emit_safe(
                    {
                        "type": "message.final",
                        "role": "assistant",
                        "content": content,
                        "thinking": thinking,
                    }
                )
        finally:
            self._streaming = False
            if started_stream:
                self._svc.set_dialogue_phase("idle")
            self._emit_safe({"type": "turn.finished", "turn_id": tid})
