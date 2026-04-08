"""聚合只读：全局与会话 task_runs.log（JSONL）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import RuyiConfig
from src.scheduler.persistence import global_task_runs_path
from src.storage.session_store import SessionStore

_MAX_GLOBAL_BYTES = 524_288
_MAX_GLOBAL_LINES = 2000
_MAX_SESSION_TAIL_LINES = 500
_MAX_TOTAL_ENTRIES = 1000


def _read_tail_text_lines(path: Path, max_lines: int, max_bytes: int) -> list[str]:
    if not path.is_file():
        return []
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size == 0:
        return []
    try:
        with path.open("rb") as f:
            if size <= max_bytes:
                data = f.read().decode("utf-8", errors="replace")
            else:
                f.seek(max(0, size - max_bytes))
                data = f.read().decode("utf-8", errors="replace")
                nl = data.find("\n")
                if nl >= 0:
                    data = data[nl + 1 :]
    except OSError:
        return []
    lines = [ln for ln in data.split("\n") if ln.strip()]
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return lines


def _parse_jsonl_lines(lines: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            raw = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(raw, dict):
            out.append(raw)
    return out


def list_task_run_entries(store: SessionStore, cfg: RuyiConfig) -> dict[str, Any]:
    """返回 { ok, entries }，entries 按 ts 降序，条数有上限。"""
    max_sess = max(1, int(cfg.builtin_scheduler.max_sessions_scanned))
    entries: list[dict[str, Any]] = []

    gpath = global_task_runs_path()
    for rec in _parse_jsonl_lines(
        _read_tail_text_lines(gpath, _MAX_GLOBAL_LINES, _MAX_GLOBAL_BYTES)
    ):
        e = dict(rec)
        e["scope"] = "global"
        e.setdefault("session_id", None)
        e.setdefault("session_title", None)
        entries.append(e)

    metas = store.list_sessions()[:max_sess]
    for meta in metas:
        sid = meta.id
        title = (meta.title or "").strip() or sid
        slog = store.root / sid / "task_runs.log"
        for rec in _parse_jsonl_lines(
            _read_tail_text_lines(slog, _MAX_SESSION_TAIL_LINES, _MAX_GLOBAL_BYTES // 4)
        ):
            e = dict(rec)
            e["scope"] = "session"
            e["session_id"] = sid
            e["session_title"] = title
            entries.append(e)

    def sort_key(x: dict[str, Any]) -> str:
        return str(x.get("ts") or "")

    entries.sort(key=sort_key, reverse=True)
    if len(entries) > _MAX_TOTAL_ENTRIES:
        entries = entries[:_MAX_TOTAL_ENTRIES]

    return {"ok": True, "entries": entries}
