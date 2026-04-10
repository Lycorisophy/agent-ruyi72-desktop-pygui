"""闲时从会话历史自动抽取记忆：游标去重 + 后台线程。"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from src.agent.memory_extractor import extract_and_store_from_text
from src.config import MemoryAutoExtractConfig
from src.service.conversation import ConversationService
from src.storage.session_store import SessionStore

_LOG = logging.getLogger("ruyi72.memory_auto")

_STATE_NAME = "memory_auto_extract_state.json"
_STATE_VERSION = 1

_state_lock = threading.Lock()


def _state_path() -> Path:
    return Path.home() / ".ruyi72" / _STATE_NAME


def _load_state_raw() -> dict[str, Any]:
    p = _state_path()
    if not p.is_file():
        return {"version": _STATE_VERSION, "sessions": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": _STATE_VERSION, "sessions": {}}
    if not isinstance(data, dict):
        return {"version": _STATE_VERSION, "sessions": {}}
    sess = data.get("sessions")
    if not isinstance(sess, dict):
        data["sessions"] = {}
    return data


def _save_state_raw(data: dict[str, Any]) -> None:
    home = Path.home() / ".ruyi72"
    home.mkdir(parents=True, exist_ok=True)
    p = _state_path()
    tmp = p.with_suffix(".tmp")
    text = json.dumps(data, ensure_ascii=False, indent=2)
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


def get_processed_count(session_id: str) -> int:
    with _state_lock:
        st = _load_state_raw()
        sess = st.get("sessions") or {}
        if not isinstance(sess, dict):
            return 0
        ent = sess.get(session_id)
        if not isinstance(ent, dict):
            return 0
        n = ent.get("processed_message_count")
        return int(n) if isinstance(n, int) else 0


def set_processed_count(session_id: str, count: int) -> None:
    with _state_lock:
        st = _load_state_raw()
        sess = st.setdefault("sessions", {})
        if not isinstance(sess, dict):
            st["sessions"] = {}
            sess = st["sessions"]
        sess[session_id] = {"processed_message_count": max(0, int(count))}
        st["version"] = _STATE_VERSION
        _save_state_raw(st)


def build_dialogue_text(
    messages: list[dict[str, Any]],
    *,
    start_index: int,
    max_chars: int,
) -> str:
    """从 start_index 起拼接 user/assistant；超长则保留尾部。"""
    parts: list[str] = []
    for m in messages[start_index:]:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        c = m.get("content")
        if not isinstance(c, str):
            continue
        t = c.strip()
        if not t:
            continue
        parts.append(f"【{role}】\n{t}")
    text = "\n\n".join(parts).strip()
    if len(text) > max_chars:
        text = text[-max_chars:].strip()
    return text


def _one_tick(svc: ConversationService, store: SessionStore, mcfg: MemoryAutoExtractConfig) -> None:
    if not svc.is_idle_for_auto_memory():
        _LOG.debug("skip tick: not idle")
        return

    metas = store.list_sessions()[: mcfg.max_sessions_scanned]
    for meta in metas:
        sid = meta.id
        try:
            _, messages = store.load(sid)
        except (OSError, FileNotFoundError, ValueError):
            continue

        n = len(messages)
        cur = get_processed_count(sid)
        if n < cur:
            set_processed_count(sid, 0)
            cur = 0
        if cur >= n:
            continue

        text = build_dialogue_text(
            messages,
            start_index=cur,
            max_chars=mcfg.max_chars_per_batch,
        )
        stripped = text.strip()
        if len(stripped) < mcfg.min_chars_to_extract:
            set_processed_count(sid, n)
            _LOG.info(
                "auto memory skip session=%s: short batch (%s chars), cursor advanced",
                sid[:8],
                len(stripped),
            )
            return

        if not svc.is_idle_for_auto_memory():
            _LOG.debug("aborted before extract: busy")
            return

        _LOG.debug("auto memory extract session=%s chars=%s", sid[:8], len(stripped))
        with svc.llm_busy():
            result = extract_and_store_from_text(
                svc._cfg, text, source_session_id=sid
            )

        if result.get("error"):
            _LOG.warning(
                "auto memory failed session=%s: %s",
                sid[:8],
                result.get("error"),
            )
            return

        set_processed_count(sid, n)
        _LOG.info(
            "auto memory ok session=%s facts=%s pending_id=%s events=%s relations=%s",
            sid[:8],
            result.get("facts", 0),
            result.get("pending_identity", 0),
            result.get("events", 0),
            result.get("relations", 0),
        )
        return

    _LOG.debug("no session with pending messages for auto memory")


def _loop(svc: ConversationService) -> None:
    store = svc._store  # noqa: SLF001
    while True:
        mcfg = svc._cfg.memory_auto_extract  # noqa: SLF001
        interval = max(30, int(mcfg.interval_sec))
        time.sleep(float(interval))
        mcfg = svc._cfg.memory_auto_extract  # noqa: SLF001
        if not mcfg.enabled:
            continue
        try:
            _one_tick(svc, store, mcfg)
        except Exception:
            _LOG.exception("auto memory tick error")


def start_memory_auto_extract_worker(svc: ConversationService) -> None:
    """启动守护线程；仅当配置 enabled 时实际运行逻辑。"""
    t = threading.Thread(target=_loop, args=(svc,), name="memory-auto-extract", daemon=True)
    t.start()

