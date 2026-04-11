"""记忆 SQLite：向量表、结构化表、FTS5、jsonl 迁移。"""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.config import RuyiConfig
    from src.storage.memory_store import Event, EventRelation, Fact

_JSONL_MIGRATED_KEY = "jsonl_migrated_v1"


def _db_path(memory_root: Path, cfg: RuyiConfig | None) -> Path:
    custom = (cfg.memory.sqlite_path if cfg else "") or ""
    if custom.strip():
        p = Path(custom).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    memory_root.mkdir(parents=True, exist_ok=True)
    return memory_root / "memory.db"


def connect_memory_db(memory_root: Path, cfg: RuyiConfig | None = None) -> sqlite3.Connection:
    p = _db_path(memory_root, cfg)
    conn = sqlite3.connect(str(p))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_embeddings (
          fact_id TEXT PRIMARY KEY,
          model TEXT NOT NULL,
          embed_text TEXT NOT NULL,
          embedding_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_facts (
          id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          source TEXT,
          key TEXT,
          value TEXT,
          summary TEXT,
          confidence REAL,
          tags_json TEXT,
          tier TEXT,
          identity_target TEXT,
          merge_hint TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_facts_fts USING fts5(
          fact_id UNINDEXED,
          body,
          tokenize='unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_events (
          id TEXT PRIMARY KEY,
          created_at TEXT,
          time TEXT,
          location TEXT,
          actors_json TEXT,
          action TEXT,
          result TEXT,
          metadata_json TEXT,
          source_session_id TEXT,
          subject_json TEXT,
          object_json TEXT,
          triggers_json TEXT,
          assertion TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_events_fts USING fts5(
          event_id UNINDEXED,
          body,
          tokenize='unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_relations (
          id TEXT PRIMARY KEY,
          created_at TEXT,
          event_a_id TEXT,
          event_b_id TEXT,
          relation_type INTEGER,
          explanation TEXT,
          relation_legacy TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_relations_fts USING fts5(
          rel_id UNINDEXED,
          body,
          tokenize='unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL,
          message_index INTEGER NOT NULL,
          role TEXT,
          content TEXT NOT NULL,
          created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_messages_fts USING fts5(
          msg_rowid UNINDEXED,
          session_id UNINDEXED,
          body,
          tokenize='unicode61'
        )
        """
    )
    conn.commit()
    _migrate_memory_events_v3_columns(conn)


def _migrate_memory_events_v3_columns(conn: sqlite3.Connection) -> None:
    """为 memory_events 追加 v3.0 列（world_kind / temporal_kind / planned_window_json），幂等。"""
    try:
        cur = conn.execute("PRAGMA table_info(memory_events)")
        cols = {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return
    alters: list[str] = []
    if "world_kind" not in cols:
        alters.append(
            "ALTER TABLE memory_events ADD COLUMN world_kind TEXT DEFAULT 'real'"
        )
    if "temporal_kind" not in cols:
        alters.append(
            "ALTER TABLE memory_events ADD COLUMN temporal_kind TEXT DEFAULT 'past'"
        )
    if "planned_window_json" not in cols:
        alters.append(
            "ALTER TABLE memory_events ADD COLUMN planned_window_json TEXT DEFAULT '{}'"
        )
    for sql in alters:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()


def upsert_fact_embedding(
    conn: sqlite3.Connection,
    *,
    fact_id: str,
    model: str,
    embed_text: str,
    vector: list[float],
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO fact_embeddings
          (fact_id, model, embed_text, embedding_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (fact_id, model, embed_text, json.dumps(vector), created_at),
    )
    conn.commit()


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def search_fact_embeddings(
    conn: sqlite3.Connection,
    query_vector: list[float],
    *,
    top_k: int = 8,
) -> list[tuple[str, float, str]]:
    cur = conn.execute(
        "SELECT fact_id, embedding_json, embed_text FROM fact_embeddings"
    )
    scored: list[tuple[str, float, str]] = []
    for fid, ej, etext in cur.fetchall():
        try:
            vec = json.loads(ej)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(vec, list) or len(vec) != len(query_vector):
            continue
        try:
            fv = [float(x) for x in vec]
        except (TypeError, ValueError):
            continue
        scored.append((str(fid), _cosine(query_vector, fv), str(etext or "")))
    scored.sort(key=lambda x: -x[1])
    return scored[: max(1, int(top_k))]


def _fts_match_expr(query: str) -> str | None:
    terms = [t for t in query.replace('"', " ").split() if t.strip()]
    if not terms:
        return None
    parts: list[str] = []
    for t in terms:
        safe = "".join(c for c in t if c.isalnum() or "\u4e00" <= c <= "\u9fff")
        if not safe:
            continue
        parts.append(f"{safe}*")
    if not parts:
        return None
    return " AND ".join(parts)


def insert_fact_row(conn: sqlite3.Connection, f: Fact) -> None:
    from src.storage.memory_store import Fact as FactCls

    if not isinstance(f, FactCls):
        return
    tags_json = json.dumps(f.tags, ensure_ascii=False)
    conn.execute(
        """
        INSERT OR REPLACE INTO memory_facts
          (id, created_at, source, key, value, summary, confidence, tags_json,
           tier, identity_target, merge_hint)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f.id,
            f.created_at,
            f.source,
            f.key,
            f.value,
            f.summary,
            f.confidence,
            tags_json,
            f.tier,
            f.identity_target,
            f.merge_hint,
        ),
    )
    conn.execute("DELETE FROM memory_facts_fts WHERE fact_id=?", (f.id,))
    body = f"{f.summary} {f.key} {f.value}"
    conn.execute(
        "INSERT INTO memory_facts_fts(fact_id, body) VALUES (?, ?)", (f.id, body)
    )
    conn.commit()


def insert_event_row(conn: sqlite3.Connection, e: Event) -> None:
    from src.storage.memory_store import Event as EventCls

    if not isinstance(e, EventCls):
        return
    pw_json = json.dumps(
        e.planned_window if isinstance(e.planned_window, dict) else {},
        ensure_ascii=False,
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO memory_events
          (id, created_at, time, location, actors_json, action, result, metadata_json,
           source_session_id, subject_json, object_json, triggers_json, assertion,
           world_kind, temporal_kind, planned_window_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            e.id,
            e.created_at,
            e.time,
            e.location,
            json.dumps(e.actors, ensure_ascii=False),
            e.action,
            e.result,
            json.dumps(e.metadata, ensure_ascii=False),
            e.source_session_id,
            json.dumps(e.subject_actors, ensure_ascii=False),
            json.dumps(e.object_actors, ensure_ascii=False),
            json.dumps(e.triggers, ensure_ascii=False),
            e.assertion,
            e.world_kind,
            e.temporal_kind,
            pw_json,
        ),
    )
    conn.execute("DELETE FROM memory_events_fts WHERE event_id=?", (e.id,))
    pw_text = ""
    if isinstance(e.planned_window, dict) and e.planned_window:
        try:
            pw_text = json.dumps(e.planned_window, ensure_ascii=False)
        except (TypeError, ValueError):
            pw_text = ""
    body = " ".join(
        [
            e.action,
            e.result,
            " ".join(e.triggers),
            " ".join(e.subject_actors),
            " ".join(e.object_actors),
            " ".join(e.actors),
            e.world_kind,
            e.temporal_kind,
            pw_text,
        ]
    )
    conn.execute(
        "INSERT INTO memory_events_fts(event_id, body) VALUES (?, ?)", (e.id, body)
    )
    conn.commit()


def insert_relation_row(conn: sqlite3.Connection, r: EventRelation) -> None:
    from src.storage.memory_store import EventRelation as ERCls

    if not isinstance(r, ERCls):
        return
    conn.execute(
        """
        INSERT OR REPLACE INTO memory_relations
          (id, created_at, event_a_id, event_b_id, relation_type, explanation, relation_legacy)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            r.id,
            r.created_at,
            r.event_a_id,
            r.event_b_id,
            r.relation_type,
            r.explanation,
            r.relation_legacy,
        ),
    )
    conn.execute("DELETE FROM memory_relations_fts WHERE rel_id=?", (r.id,))
    body = f"{r.explanation} {r.relation_legacy} {r.relation_type}"
    conn.execute(
        "INSERT INTO memory_relations_fts(rel_id, body) VALUES (?, ?)", (r.id, body)
    )
    conn.commit()


def sync_sqlite_append(
    cfg: RuyiConfig,
    memory_root: Path,
    *,
    facts: list[Fact],
    events: list[Event],
    relations: list[EventRelation],
) -> None:
    if cfg.memory.backend not in ("dual", "sqlite"):
        return
    if not facts and not events and not relations:
        return
    conn = connect_memory_db(memory_root, cfg)
    try:
        ensure_schema(conn)
        for f in facts:
            insert_fact_row(conn, f)
        for e in events:
            insert_event_row(conn, e)
        for r in relations:
            insert_relation_row(conn, r)
    finally:
        conn.close()


def _dict_to_fact(d: dict) -> Fact | None:
    from src.storage.memory_store import Fact

    try:
        key = str(d.get("key") or "").strip()
        value = str(d.get("value") or "").strip()
        if not key or not value:
            return None
        tags = d.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return Fact(
            id=str(d.get("id") or ""),
            created_at=str(d.get("created_at") or ""),
            source=str(d.get("source") or "jsonl_import"),
            key=key,
            value=value,
            summary=str(d.get("summary") or "") or value,
            confidence=float(d.get("confidence") or 0.8),
            tags=[str(t) for t in tags],
            tier=str(d.get("tier") or "important") or "important",
            identity_target=str(d.get("identity_target") or ""),
            merge_hint=str(d.get("merge_hint") or ""),
        )
    except (TypeError, ValueError):
        return None


def _dict_to_event(d: dict) -> Event | None:
    from src.storage.memory_store import (
        Event,
        normalize_event_temporal_kind,
        normalize_event_world_kind,
        normalize_planned_window_dict,
    )

    try:
        action = str(d.get("action") or "").strip()
        result = str(d.get("result") or "").strip()
        if not action and not result:
            return None
        actors = d.get("actors") or []
        if not isinstance(actors, list):
            actors = []
        md = d.get("metadata") or {}
        if not isinstance(md, dict):
            md = {}
        sub = d.get("subject_actors") or []
        if not isinstance(sub, list):
            sub = []
        obj = d.get("object_actors") or []
        if not isinstance(obj, list):
            obj = []
        tr = d.get("triggers") or []
        if not isinstance(tr, list):
            tr = []
        wk = normalize_event_world_kind(d.get("world_kind"))
        tk = normalize_event_temporal_kind(d.get("temporal_kind"))
        pw = normalize_planned_window_dict(d.get("planned_window"))
        return Event(
            id=str(d.get("id") or ""),
            created_at=str(d.get("created_at") or ""),
            time=str(d.get("time") or ""),
            location=str(d.get("location") or ""),
            actors=[str(a) for a in actors],
            action=action,
            result=result,
            metadata=dict(md),
            source_session_id=str(d.get("source_session_id") or ""),
            subject_actors=[str(a) for a in sub],
            object_actors=[str(a) for a in obj],
            triggers=[str(a) for a in tr],
            assertion=str(d.get("assertion") or "actual") or "actual",
            world_kind=wk,
            temporal_kind=tk,
            planned_window=pw,
        )
    except (TypeError, ValueError):
        return None


def _dict_to_relation(d: dict) -> EventRelation | None:
    from src.storage.memory_store import EventRelation

    try:
        ea = str(d.get("event_a_id") or "").strip()
        eb = str(d.get("event_b_id") or "").strip()
        if not ea or not eb:
            return None
        if "relation_type" in d and d["relation_type"] is not None:
            try:
                rt = int(d["relation_type"])
            except (TypeError, ValueError):
                rt = 11
        else:
            rt = 11
        leg = str(d.get("relation_legacy") or d.get("relation") or "")
        expl = str(d.get("explanation") or "")
        if rt == 11 and not expl:
            expl = leg or "其它关系"
        return EventRelation(
            id=str(d.get("id") or ""),
            created_at=str(d.get("created_at") or ""),
            event_a_id=ea,
            event_b_id=eb,
            relation_type=rt,
            explanation=expl,
            relation_legacy=leg,
        )
    except (TypeError, ValueError):
        return None


def migrate_jsonl_to_sqlite(memory_root: Path, conn: sqlite3.Connection) -> None:
    ensure_schema(conn)
    for name, kind in (
        ("facts.jsonl", "facts"),
        ("events.jsonl", "events"),
        ("relations.jsonl", "relations"),
    ):
        path = memory_root / name
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if kind == "facts":
                f = _dict_to_fact(obj)
                if f and f.id:
                    insert_fact_row(conn, f)
            elif kind == "events":
                e = _dict_to_event(obj)
                if e and e.id:
                    insert_event_row(conn, e)
            else:
                r = _dict_to_relation(obj)
                if r and r.id and r.event_a_id and r.event_b_id:
                    insert_relation_row(conn, r)


def maybe_migrate_jsonl(cfg: RuyiConfig, memory_root: Path) -> None:
    if cfg.memory.backend not in ("dual", "sqlite"):
        return
    conn = connect_memory_db(memory_root, cfg)
    try:
        ensure_schema(conn)
        cur = conn.execute(
            "SELECT value FROM schema_meta WHERE key=?", (_JSONL_MIGRATED_KEY,)
        )
        row = cur.fetchone()
        if row and row[0] == "1":
            return
        migrate_jsonl_to_sqlite(memory_root, conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
            (_JSONL_MIGRATED_KEY, "1"),
        )
        conn.commit()
    finally:
        conn.close()


def sqlite_row_count(conn: sqlite3.Connection) -> int:
    ensure_schema(conn)
    n = 0
    for t in ("memory_facts", "memory_events", "memory_relations"):
        try:
            n += int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
        except sqlite3.OperationalError:
            pass
    return n


def _row_to_fact_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    tj = d.pop("tags_json", "[]") or "[]"
    try:
        d["tags"] = json.loads(tj)
    except json.JSONDecodeError:
        d["tags"] = []
    return d


def _row_to_event_dict(row: sqlite3.Row) -> dict:
    from src.storage.memory_store import (
        normalize_event_temporal_kind,
        normalize_event_world_kind,
        normalize_planned_window_dict,
    )

    d = dict(row)
    for k, jk in (
        ("actors_json", "actors"),
        ("metadata_json", "metadata"),
        ("subject_json", "subject_actors"),
        ("object_json", "object_actors"),
        ("triggers_json", "triggers"),
    ):
        raw = d.pop(k, "[]") if k != "metadata_json" else d.pop(k, "{}")
        try:
            d[jk] = json.loads(raw or ("{}" if k == "metadata_json" else "[]"))
        except json.JSONDecodeError:
            d[jk] = {} if jk == "metadata" else []
    pw_raw = d.pop("planned_window_json", None)
    if pw_raw is not None and str(pw_raw).strip():
        try:
            parsed = json.loads(pw_raw) if isinstance(pw_raw, str) else pw_raw
            d["planned_window"] = normalize_planned_window_dict(parsed)
        except json.JSONDecodeError:
            d["planned_window"] = {}
    else:
        d["planned_window"] = {}
    d["world_kind"] = normalize_event_world_kind(d.get("world_kind"))
    d["temporal_kind"] = normalize_event_temporal_kind(d.get("temporal_kind"))
    return d


def _row_to_relation_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def sqlite_read_recent_facts(conn: sqlite3.Connection, limit: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM memory_facts ORDER BY created_at DESC LIMIT ?",
        (max(1, limit),),
    )
    return [_row_to_fact_dict(row) for row in cur.fetchall()]


def sqlite_read_recent_events(conn: sqlite3.Connection, limit: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM memory_events ORDER BY created_at DESC LIMIT ?",
        (max(1, limit),),
    )
    return [_row_to_event_dict(row) for row in cur.fetchall()]


def sqlite_read_recent_events_for_bootstrap(
    conn: sqlite3.Connection,
    limit: int,
    *,
    exclude_world_kinds: frozenset[str],
) -> list[dict]:
    """冷启动用：按时间倒序取事件，排除给定 world_kind（与 COALESCE(world_kind,'real') 比较）。"""
    if not exclude_world_kinds:
        return sqlite_read_recent_events(conn, limit)
    conn.row_factory = sqlite3.Row
    lim = max(1, limit)
    qs = ",".join("?" * len(exclude_world_kinds))
    sql = f"""
        SELECT * FROM memory_events
        WHERE COALESCE(world_kind, 'real') NOT IN ({qs})
        ORDER BY created_at DESC
        LIMIT ?
    """
    params = tuple(exclude_world_kinds) + (lim,)
    cur = conn.execute(sql, params)
    return [_row_to_event_dict(row) for row in cur.fetchall()]


def sqlite_read_recent_relations(conn: sqlite3.Connection, limit: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM memory_relations ORDER BY created_at DESC LIMIT ?",
        (max(1, limit),),
    )
    return [_row_to_relation_dict(row) for row in cur.fetchall()]


def fts_search_combined(
    conn: sqlite3.Connection,
    query: str,
    *,
    max_per_kind: int,
    event_world_kinds: list[str] | None = None,
    event_temporal_kinds: list[str] | None = None,
) -> list[tuple[str, str]]:
    """返回 (标签, json行) 列表。

    event_world_kinds / event_temporal_kinds：
    - 均为 None 时不对事件做类型过滤（与旧行为一致）；
    - 任一为长度 0 的列表时，不返回任何事件命中（调用方应在传入前跳过事件检索）；
    - 否则仅保留 world_kind / temporal_kind 落在给定集合内的事件（与 NULL 列比较时用 COALESCE 与默认一致）。
    """
    expr = _fts_match_expr(query)
    if not expr:
        return []
    conn.row_factory = sqlite3.Row
    out: list[tuple[str, str]] = []
    lim = max(1, max_per_kind)

    skip_events = False
    if event_world_kinds is not None and len(event_world_kinds) == 0:
        skip_events = True
    if event_temporal_kinds is not None and len(event_temporal_kinds) == 0:
        skip_events = True

    def add_fts(
        fts_sql: str, table: str, label: str, map_row: object
    ) -> None:
        try:
            cur = conn.execute(fts_sql, (expr, lim))
        except sqlite3.OperationalError:
            return
        for r in cur.fetchall():
            rid = r[0]
            if not rid:
                continue
            try:
                cur2 = conn.execute(f"SELECT * FROM {table} WHERE id=?", (rid,))
                row = cur2.fetchone()
            except sqlite3.OperationalError:
                continue
            if row:
                d = map_row(row)
                out.append((label, json.dumps(d, ensure_ascii=False)))

    def add_events_fts() -> None:
        if skip_events:
            return
        use_join = event_world_kinds is not None or event_temporal_kinds is not None
        try:
            if not use_join:
                cur = conn.execute(
                    "SELECT event_id FROM memory_events_fts WHERE memory_events_fts MATCH ? LIMIT ?",
                    (expr, lim),
                )
            else:
                wheres = ["f MATCH ?"]
                params: list[object] = [expr]
                if event_world_kinds is not None:
                    qs = ",".join("?" * len(event_world_kinds))
                    wheres.append(f"COALESCE(e.world_kind, 'real') IN ({qs})")
                    params.extend(event_world_kinds)
                if event_temporal_kinds is not None:
                    qs = ",".join("?" * len(event_temporal_kinds))
                    wheres.append(f"COALESCE(e.temporal_kind, 'past') IN ({qs})")
                    params.extend(event_temporal_kinds)
                params.append(lim)
                sql = f"""
                    SELECT f.event_id FROM memory_events_fts AS f
                    INNER JOIN memory_events AS e ON e.id = f.event_id
                    WHERE {' AND '.join(wheres)}
                    LIMIT ?
                """
                cur = conn.execute(sql, tuple(params))
        except sqlite3.OperationalError:
            return
        for r in cur.fetchall():
            rid = r[0]
            if not rid:
                continue
            try:
                cur2 = conn.execute("SELECT * FROM memory_events WHERE id=?", (rid,))
                row = cur2.fetchone()
            except sqlite3.OperationalError:
                continue
            if row:
                d = _row_to_event_dict(row)
                out.append(("【事件】FTS", json.dumps(d, ensure_ascii=False)))

    add_fts(
        "SELECT fact_id FROM memory_facts_fts WHERE memory_facts_fts MATCH ? LIMIT ?",
        "memory_facts",
        "【事实】FTS",
        _row_to_fact_dict,
    )
    add_events_fts()
    add_fts(
        "SELECT rel_id FROM memory_relations_fts WHERE memory_relations_fts MATCH ? LIMIT ?",
        "memory_relations",
        "【关系】FTS",
        _row_to_relation_dict,
    )
    return out


def insert_message_index_row(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    message_index: int,
    role: str,
    content: str,
    created_at: str,
) -> None:
    ensure_schema(conn)
    conn.execute(
        """
        INSERT INTO memory_messages (session_id, message_index, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, message_index, role, content, created_at),
    )
    rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("DELETE FROM memory_messages_fts WHERE msg_rowid=?", (rid,))
    conn.execute(
        "INSERT INTO memory_messages_fts(msg_rowid, session_id, body) VALUES (?, ?, ?)",
        (rid, session_id, content),
    )
    conn.commit()


def replace_session_messages_index(
    cfg: RuyiConfig,
    memory_root: Path,
    session_id: str,
    messages: list[dict[str, Any]],
) -> None:
    """用当前 messages 列表重建该 session 在 memory_messages / FTS 中的行。"""
    conn = connect_memory_db(memory_root, cfg)
    try:
        ensure_schema(conn)
        conn.execute("DELETE FROM memory_messages_fts WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM memory_messages WHERE session_id=?", (session_id,))
        for i, m in enumerate(messages):
            role = str(m.get("role") or "")
            content = str(m.get("content") or "")
            created_at = str(m.get("created_at") or "")
            if not created_at:
                created_at = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO memory_messages (session_id, message_index, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, i, role, content, created_at),
            )
            rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO memory_messages_fts(msg_rowid, session_id, body) VALUES (?, ?, ?)",
                (rid, session_id, content),
            )
        conn.commit()
    finally:
        conn.close()


def fts_search_messages(
    conn: sqlite3.Connection, query: str, session_id: str | None, limit: int
) -> list[str]:
    expr = _fts_match_expr(query)
    if not expr:
        return []
    conn.row_factory = sqlite3.Row
    lim = max(1, limit)
    try:
        if session_id:
            cur = conn.execute(
                """
                SELECT m.session_id, m.message_index, m.role, m.content
                FROM memory_messages_fts AS f
                JOIN memory_messages AS m ON m.rowid = f.msg_rowid
                WHERE f.body MATCH ? AND f.session_id = ?
                LIMIT ?
                """,
                (expr, session_id, lim),
            )
        else:
            cur = conn.execute(
                """
                SELECT m.session_id, m.message_index, m.role, m.content
                FROM memory_messages_fts AS f
                JOIN memory_messages AS m ON m.rowid = f.msg_rowid
                WHERE f.body MATCH ?
                LIMIT ?
                """,
                (expr, lim),
            )
    except sqlite3.OperationalError:
        return []
    lines = []
    for r in cur.fetchall():
        lines.append(
            json.dumps(
                {
                    "session_id": r[0],
                    "message_index": r[1],
                    "role": r[2],
                    "content": (r[3] or "")[:500],
                },
                ensure_ascii=False,
            )
        )
    return lines
