"""跨会话记忆：格式化、browse、关键词检索（供 API 与 ReAct 工具复用）。"""

from __future__ import annotations

import json
from pathlib import Path

from src.storage.memory_store import (
    RELATION_TYPE_LABELS,
    RELATION_TYPE_MAX,
    RELATION_TYPE_MIN,
    MemoryKind,
    MemoryStore,
    default_store,
)


def load_recent_memory_split(
    store: MemoryStore,
    facts_limit: int,
    events_limit: int,
    relations_limit: int,
) -> tuple[list[dict], list[dict], list[dict]]:
    """读路径：backend 为 dual/sqlite 且库内已有记忆行时从 SQLite 读，否则 JSONL。"""
    from src.config import load_config
    from src.storage.memory_sqlite import (
        connect_memory_db,
        ensure_schema,
        sqlite_read_recent_facts,
        sqlite_read_recent_events,
        sqlite_read_recent_relations,
        sqlite_row_count,
    )

    cfg = load_config()
    fl = max(1, int(facts_limit))
    el = max(1, int(events_limit))
    rl = max(1, int(relations_limit))
    if cfg.memory.backend in ("dual", "sqlite"):
        conn = connect_memory_db(store.root, cfg)
        try:
            ensure_schema(conn)
            if sqlite_row_count(conn) > 0:
                return (
                    sqlite_read_recent_facts(conn, fl),
                    sqlite_read_recent_events(conn, el),
                    sqlite_read_recent_relations(conn, rl),
                )
        finally:
            conn.close()
    return (
        store.read_recent("facts", fl),
        store.read_recent("events", el),
        store.read_recent("relations", rl),
    )


def _format_relation_line(r: dict) -> str:
    ea = r.get("event_a_id") or ""
    eb = r.get("event_b_id") or ""
    expl = (r.get("explanation") or "").strip()
    rt_raw = r.get("relation_type")
    if rt_raw is not None and rt_raw != "":
        try:
            code = int(rt_raw)
        except (TypeError, ValueError):
            code = None
        if code is not None and RELATION_TYPE_MIN <= code <= RELATION_TYPE_MAX:
            label = RELATION_TYPE_LABELS.get(code, str(code))
            leg = (r.get("relation_legacy") or "").strip() or (r.get("relation") or "").strip()
            body = expl if expl else label
            if leg and leg not in body:
                body = f"{body}；原标签:{leg}" if body else f"原标签:{leg}"
            return f"- {ea} -> {eb}：{label}（{body}）"
    rel = r.get("relation") or ""
    return f"- {ea} -> {eb}：{rel}（{expl}）"


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
            tier = (f.get("tier") or "").strip()
            tier_note = f" [tier={tier}]" if tier and tier != "important" else ""
            lines.append(f"- {tag_str}{summary} ({key} = {value}){tier_note}")
        lines.append("")
    if events:
        lines.append("【事件】")
        for e in events:
            t = e.get("time") or ""
            loc = e.get("location") or ""
            actors = ", ".join(e.get("actors") or [])
            subj = ", ".join(e.get("subject_actors") or [])
            obj = ", ".join(e.get("object_actors") or [])
            trig = ", ".join(e.get("triggers") or [])
            assertion = (e.get("assertion") or "").strip()
            sess = (e.get("source_session_id") or "").strip()
            action = e.get("action") or ""
            result = e.get("result") or ""
            extra_parts: list[str] = []
            if subj or obj:
                extra_parts.append(f"主{subj or '-'}→客{obj or '-'}")
            if trig:
                extra_parts.append(f"触发:{trig}")
            if assertion and assertion != "actual":
                extra_parts.append(f"断言:{assertion}")
            if sess:
                extra_parts.append(f"会话:{sess[:12]}…" if len(sess) > 12 else f"会话:{sess}")
            extra = f" [{' | '.join(extra_parts)}]" if extra_parts else ""
            who = actors if actors else (f"{subj}/{obj}" if (subj or obj) else "")
            lines.append(f"- [{t} @ {loc}] ({who})：{action} -> {result}{extra}")
        lines.append("")
    if relations:
        lines.append("【事件关系】")
        for r in relations:
            lines.append(_format_relation_line(r))

    return "\n".join(lines).strip() or empty_hint


def browse_memory_formatted(limit: int = 10, store: MemoryStore | None = None) -> str:
    """列出各类最近若干条记忆（与前端「浏览记忆」同结构）。"""
    st = store or default_store()
    n = max(1, int(limit))
    facts, events, relations = load_recent_memory_split(st, n, n, n)
    return format_memory_entries(facts, events, relations)


def get_recent_memory_for_api(limit: int = 10, store: MemoryStore | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    st = store or default_store()
    n = max(1, int(limit))
    return load_recent_memory_split(st, n, n, n)


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
    facts, events, relations = load_recent_memory_split(
        st, facts_limit, events_limit, relations_limit
    )
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
    """关键词检索：dual/sqlite 且库内有数据时用 FTS5，否则 JSONL 子串扫描。"""
    from src.config import load_config
    from src.storage.memory_sqlite import (
        connect_memory_db,
        ensure_schema,
        fts_search_combined,
        sqlite_row_count,
    )

    q = (query or "").strip()
    if not q:
        return "请提供非空的检索关键词或短语。"
    q_lower = q.lower()
    st = store or default_store()
    cfg = load_config()
    if cfg.memory.backend in ("dual", "sqlite"):
        conn = connect_memory_db(st.root, cfg)
        try:
            ensure_schema(conn)
            if sqlite_row_count(conn) > 0:
                hits = fts_search_combined(conn, q, max_per_kind=max_per_kind)
                if hits:
                    parts: list[str] = []
                    for label, line in hits:
                        parts.append(label)
                        parts.append(line)
                    parts.append("")
                    return "\n".join(parts).strip()
        finally:
            conn.close()
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


def search_memory_semantic(
    query: str,
    *,
    top_k: int = 8,
    store: MemoryStore | None = None,
) -> str:
    """对重要事实的向量索引做语义检索（Ollama embedding + memory.db）。"""
    from src.config import embedding_http_llm_cfg, load_config
    from src.llm.ollama import ollama_embed_one
    from src.storage.memory_sqlite import (
        connect_memory_db,
        ensure_schema,
        search_fact_embeddings,
    )

    cfg = load_config()
    q = (query or "").strip()
    if not q:
        return "请提供非空的检索 query。"
    if not cfg.memory.vector_enabled:
        return (
            "语义检索未启用。请在 ruyi72.yaml 中设置 memory.vector_enabled: true，"
            "并确保 llm.provider 为 ollama 且已拉取 embedding 模型（如 qwen3-embedding:8b）。"
        )
    if cfg.llm.provider != "ollama":
        return "语义检索当前仅支持 Ollama（llm.provider=ollama）。"
    st = store or default_store()
    conn = connect_memory_db(st.root, cfg)
    try:
        ensure_schema(conn)
        llm_e = embedding_http_llm_cfg(cfg)
        model = cfg.embedding.model.strip()
        qv = ollama_embed_one(llm_e, model, q)
        hits = search_fact_embeddings(conn, qv, top_k=top_k)
    finally:
        conn.close()
    if not hits:
        return (
            "向量库中暂无事实条目或未命中。请先抽取 tier=important 的事实，"
            "并确认 memory.vector_enabled 已开启且 embedding 调用成功。"
        )
    lines = ["【事实·语义相近】"]
    for fid, score, et in hits:
        snippet = et if len(et) <= 240 else et[:237] + "…"
        lines.append(f"- score={score:.4f} id={fid} {snippet}")
    return "\n".join(lines)


def search_history(
    query: str,
    *,
    session_id: str = "",
    limit: int = 15,
    store: MemoryStore | None = None,
) -> str:
    """对已索引的会话消息做 FTS（需 memory.messages_index_enabled 且 backend 为 dual/sqlite）。"""
    from src.config import load_config
    from src.storage.memory_sqlite import (
        connect_memory_db,
        ensure_schema,
        fts_search_messages,
    )

    cfg = load_config()
    if not cfg.memory.messages_index_enabled:
        return (
            "对话历史检索未启用。请在配置中设置 memory.messages_index_enabled: true，"
            "并确保 memory.backend 为 dual 或 sqlite；保存消息时会重建本会话的索引。"
        )
    if cfg.memory.backend not in ("dual", "sqlite"):
        return "对话历史 FTS 需要 memory.backend 为 dual 或 sqlite。"
    q = (query or "").strip()
    if not q:
        return "请提供非空的检索关键词或短语。"
    st = store or default_store()
    sid = (session_id or "").strip() or None
    conn = connect_memory_db(st.root, cfg)
    try:
        ensure_schema(conn)
        lim = max(1, int(limit))
        rows = fts_search_messages(conn, q, sid, lim)
    finally:
        conn.close()
    if not rows:
        return f"未在已索引的对话历史中找到与 {q!r} 相关的片段。"
    return "【对话历史】\n" + "\n".join(rows)
