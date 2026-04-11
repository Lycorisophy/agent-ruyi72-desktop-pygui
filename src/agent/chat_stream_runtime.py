"""安全模式（chat）：流式 LLM + 可打断；事件协议与拟人一致（turn.started / token.delta / turn.finished）。"""

from __future__ import annotations

import queue
import threading
import time
from typing import TYPE_CHECKING, Any, Callable

from src.agent.action_card import split_reply_action_card
from src.llm.ollama import OllamaClientError
from src.llm.ollama_stream import stream_chat
from src.llm.prompts import action_card_system_hint, build_system_block
from src.skills.loader import build_safe_skills_prompt

if TYPE_CHECKING:
    from src.service.conversation import ConversationService

FLUSH_INTERVAL_SEC = 0.05


class SafeChatStreamRuntime:
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
        self._flush_buf: list[tuple[str, str]] = []
        self._flush_deadline: float | None = None

    def start(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop.clear()
            self._worker = threading.Thread(
                target=self._run_worker, name="safe-chat-stream", daemon=True
            )
            self._worker.start()

    def shutdown(self) -> None:
        self._stop.set()
        self._cancel.set()
        try:
            self._q.put_nowait(("STOP", None))
        except queue.Full:
            pass
        w = self._worker
        if w and w.is_alive():
            w.join(timeout=2.0)
        self._worker = None

    def enqueue_user_text(self, text: str, memory_extra: str = "") -> int:
        with self._lock:
            self._turn_id += 1
            tid = self._turn_id
        self._q.put(("send", (tid, text, memory_extra)))
        return tid

    def interrupt(self) -> None:
        self._cancel.set()
        self._q.put(("interrupt", None))

    def is_streaming(self) -> bool:
        return self._streaming

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
                pair = payload
                if isinstance(pair, tuple) and len(pair) >= 2:
                    tid = int(pair[0])
                    raw = str(pair[1] or "").strip()
                    mem = str(pair[2] or "") if len(pair) > 2 else ""
                    self._run_turn(tid, raw, mem)

    def _run_turn(self, tid: int, text: str, memory_extra: str = "") -> None:
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

            call_messages = self._svc.build_safe_chat_call_messages(
                text, memory_extra=memory_extra
            )

            def on_delta(ch: str, t: str) -> None:
                self._buffer_delta(ch, t)

            thinking = ""
            try:
                content, thinking = stream_chat(
                    self._svc.llm_config(),
                    call_messages,
                    on_delta=on_delta,
                    cancel_check=lambda: self._cancel.is_set(),
                    think=False,
                    caller="safe_chat_stream._run_turn",
                )
            except OllamaClientError as e:
                self._flush_deltas(force=True)
                self._emit_safe({"type": "error", "message": str(e)})
                return

            self._flush_deltas(force=True)

            if self._cancel.is_set():
                partial = (content or "").strip()
                final_assistant = f"【已中断】{partial}" if partial else "【已中断】"
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
                visible, card = split_reply_action_card(content)
                content_out = visible.strip() if visible else ""
                if card is not None:
                    if not content_out:
                        content_out = (
                            str(card.get("title") or "").strip() or "请确认下列设置。"
                        )
                    self._svc.supersede_pending_cards_and_append_assistant(
                        content_out, card=card
                    )
                else:
                    self._svc.persona_append_assistant(content_out or content)
                self._emit_safe({"type": "turn.completed", "turn_id": tid})
                self._emit_safe(
                    {
                        "type": "message.final",
                        "role": "assistant",
                        "content": content_out or content,
                        "thinking": thinking,
                    }
                )
        finally:
            self._streaming = False
            if started_stream:
                self._svc.set_dialogue_phase("idle")
            self._emit_safe({"type": "turn.finished", "turn_id": tid})
