"""跨会话记忆：格式化、browse、关键词检索（供 API 与 ReAct 工具复用）。"""

from __future__ import annotations

import json
from pathlib import Path

from src.storage.memory_store import MemoryKind, MemoryStore, default_store


def format_memory_entries(
    facts: list[dict],
    events: list[dict],
    relations: list[dict],
    *,
    empty_hint: str = "当前还没有记忆条目。",
) -> str:
    lines: list[str] = []
    if facts:
        lines.append("【事实】")
        for f in facts:
            summary = f.get("summary") or ""
            key = f.get("key") or ""
            value = f.get("value") or ""
            tags = f.get("tags") or []
            tag_str = f"[{', '.join(tags)}] " if tags else ""
            lines.append(f"- {tag_str}{summary} ({key} = {value})")
        lines.append("")
    if events:
        lines.append("【事件】")
        for e in events:
            t = e.get("time") or ""
            loc = e.get("location") or ""
            actors = ", ".join(e.get("actors") or [])
            action = e.get("action") or ""
            result = e.get("result") or ""
            lines.append(f"- [{t} @ {loc}] ({actors})：{action} -> {result}")
        lines.append("")
    if relations:
        lines.append("【事件关系】")
        for r in relations:
            ea = r.get("event_a_id") or ""
            eb = r.get("event_b_id") or ""
            rel = r.get("relation") or ""
            expl = r.get("explanation") or ""
            lines.append(f"- {ea} -> {eb}：{rel}（{expl}）")

    return "\n".join(lines).strip() or empty_hint


def browse_memory_formatted(limit: int = 10, store: MemoryStore | None = None) -> str:
    """列出各类最近若干条记忆（与前端「浏览记忆」同结构）。"""
    st = store or default_store()
    n = max(1, int(limit))
    facts = st.read_recent("facts", n)
    events = st.read_recent("events", n)
    relations = st.read_recent("relations", n)
    return format_memory_entries(facts, events, relations)


def build_memory_bootstrap_block(
    *,
    facts_limit: int = 8,
    events_limit: int = 5,
    relations_limit: int = 5,
    max_chars: int = 6000,
    store: MemoryStore | None = None,
) -> str:
    """
    会话冷启动：拼一段可注入 system 的「已知长期记忆」。
    若无任何条目则返回空串（调用方可不追加）。
    """
    st = store or default_store()
    facts = st.read_recent("facts", facts_limit)
    events = st.read_recent("events", events_limit)
    relations = st.read_recent("relations", relations_limit)
    if not facts and not events and not relations:
        return ""

    body = format_memory_entries(facts, events, relations, empty_hint="")
    if not body.strip():
        return ""

    header = (
        "## 已保存的长期记忆（跨会话）\n"
        "以下为最近提取的若干条摘要，供你参考；若与当前问题无关可忽略。\n\n"
    )
    text = header + body
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n…（已截断）"
    return text


def _lines_matching(path: Path, query_lower: str) -> list[str]:
    if not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if query_lower in s.lower():
            out.append(s)
    return out


def search_memory_keyword(
    query: str,
    *,
    max_per_kind: int = 15,
    store: MemoryStore | None = None,
) -> str:
    """在 facts/events/relations 的 JSONL 中做子串匹配（不建向量索引，成本低）。"""
    q = (query or "").strip()
    if not q:
        return "请提供非空的检索关键词或短语。"
    q_lower = q.lower()
    st = store or default_store()
    root = st.root
    labels: dict[MemoryKind, str] = {
        "facts": "【事实】匹配行",
        "events": "【事件】匹配行",
        "relations": "【关系】匹配行",
    }
    parts: list[str] = []
    for kind in ("facts", "events", "relations"):
        path = root / f"{kind}.jsonl"
        matches = _lines_matching(path, q_lower)
        take = matches[-max_per_kind:] if len(matches) > max_per_kind else matches
        if not take:
            continue
        parts.append(labels[kind])
        for line in take:
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    parts.append(json.dumps(obj, ensure_ascii=False))
                else:
                    parts.append(line)
            except json.JSONDecodeError:
                parts.append(line)
        parts.append("")
    if not parts:
        return f"未在记忆库中找到包含 {q!r} 的条目。"
    return "\n".join(parts).strip()
