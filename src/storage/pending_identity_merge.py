"""永驻记忆待合并队列：预览与追加到身份 Markdown（USER/SOUL/MEMORY）。"""

from __future__ import annotations

from pathlib import Path

from src.llm.ruyi72_identity_files import MEMORY_FILE, SOUL_FILE, USER_FILE, invalidate_identity_cache
from src.storage.memory_store import MemoryStore


def identity_path_for_target(identity_target: str) -> Path:
    t = (identity_target or "memory").strip().lower()
    m = {"user": USER_FILE, "soul": SOUL_FILE, "memory": MEMORY_FILE}
    return m.get(t, MEMORY_FILE)


def format_pending_append_block(entry: dict) -> str:
    pid = str(entry.get("id") or "")
    summary = str(entry.get("summary") or "")
    key = str(entry.get("key") or "")
    value = str(entry.get("value") or "")
    hint = str(entry.get("merge_hint") or "").strip()
    lines = [
        "",
        f"<!-- ruyi72-pending {pid} -->",
        f"* {summary}: `{key}` = {value}",
    ]
    if hint:
        lines.append(f"  <!-- merge_hint: {hint} -->")
    lines.append("")
    return "\n".join(lines)


def preview_pending_identity_merge(store: MemoryStore, pending_id: str) -> dict:
    entry = store.find_pending_identity(pending_id)
    if entry is None:
        return {"ok": False, "error": "未找到该待合并条目"}
    path = identity_path_for_target(str(entry.get("identity_target") or ""))
    current = ""
    if path.is_file():
        try:
            current = path.read_text(encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": f"读取身份文件失败: {e}"}
    proposed = format_pending_append_block(entry)
    tail = current[-1200:] if len(current) > 1200 else current
    return {
        "ok": True,
        "entry": entry,
        "target_file": str(path),
        "current_tail": tail,
        "proposed_append": proposed,
    }


def apply_pending_identity_merge(store: MemoryStore, pending_id: str) -> dict:
    entry = store.find_pending_identity(pending_id)
    if entry is None:
        return {"ok": False, "error": "未找到该待合并条目"}
    path = identity_path_for_target(str(entry.get("identity_target") or ""))
    block = format_pending_append_block(entry)
    old = ""
    if path.is_file():
        try:
            old = path.read_text(encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": f"读取身份文件失败: {e}"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(old + block, encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": f"写入身份文件失败: {e}"}
    store.remove_pending_identity_if_exists(pending_id)
    invalidate_identity_cache()
    return {"ok": True, "applied_to": str(path)}
