from __future__ import annotations

"""记忆抽取器：从一段文本中提取事实 / 事件 / 事件关系并写入 MemoryStore。"""

import json
import logging
import time

from src.config import RuyiConfig, embedding_http_llm_cfg
from src.debug_log import is_debug
from src.llm.ollama import OllamaClient, OllamaClientError, ollama_embed_one
from src.storage.memory_store import (
    normalize_event_temporal_kind,
    normalize_event_world_kind,
    normalize_planned_window_dict,
    RELATION_TYPE_LABELS,
    RELATION_TYPE_MAX,
    RELATION_TYPE_MIN,
    Event,
    EventRelation,
    Fact,
    PendingIdentityMerge,
    default_store,
    new_event_id,
    new_fact_id,
    new_pending_identity_id,
    new_relation_id,
    _now_iso,
)

_LOG = logging.getLogger("ruyi72.memory")


def _index_important_facts_vector(cfg: RuyiConfig, facts: list[Fact]) -> None:
    if not cfg.memory.vector_enabled or cfg.llm.provider != "ollama" or not facts:
        return
    from src.storage.memory_sqlite import (
        connect_memory_db,
        ensure_schema,
        upsert_fact_embedding,
    )

    llm_e = embedding_http_llm_cfg(cfg)
    model = cfg.embedding.model.strip()
    store = default_store()
    conn = connect_memory_db(store.root, cfg)
    try:
        ensure_schema(conn)
        for f in facts:
            if f.tier != "important":
                continue
            embed_text = f"{f.summary}\n{f.key}={f.value}"
            try:
                vec = ollama_embed_one(llm_e, model, embed_text)
            except OllamaClientError:
                continue
            except Exception:
                continue
            upsert_fact_embedding(
                conn,
                fact_id=f.id,
                model=model,
                embed_text=embed_text,
                vector=vec,
                created_at=f.created_at,
            )
    finally:
        conn.close()


def _index_events_vector(cfg: RuyiConfig, events: list[Event]) -> None:
    if not cfg.memory.vector_enabled or cfg.llm.provider != "ollama" or not events:
        return
    from src.storage.memory_sqlite import (
        connect_memory_db,
        delete_event_embedding,
        ensure_schema,
        event_embedding_text_from_event,
        upsert_event_embedding,
    )

    llm_e = embedding_http_llm_cfg(cfg)
    model = cfg.embedding.model.strip()
    store = default_store()
    conn = connect_memory_db(store.root, cfg)
    index_fic = cfg.memory.vector_index_fictional_events
    try:
        ensure_schema(conn)
        for e in events:
            wk = normalize_event_world_kind(e.world_kind)
            if wk == "fictional" and not index_fic:
                try:
                    delete_event_embedding(conn, e.id)
                except Exception:
                    pass
                continue
            embed_text = event_embedding_text_from_event(e)
            if not embed_text:
                continue
            try:
                vec = ollama_embed_one(llm_e, model, embed_text)
            except OllamaClientError:
                continue
            except Exception:
                continue
            upsert_event_embedding(
                conn,
                event_id=e.id,
                model=model,
                embed_text=embed_text,
                vector=vec,
                created_at=e.created_at,
                world_kind=wk,
            )
    finally:
        conn.close()


EXTRACT_SYSTEM_PROMPT = """
你是一个记忆抽取助手。现在给你一段中文或英文文本，请你从中提取三类结构化记忆：

1. facts：事实（主要关于用户本身的稳定特征 / 偏好 / 约定）
   每条事实可增加字段：
   - tier：字符串，取值 trivial（不重要、不落库）| important（重要、长期记忆）| permanent（永驻、需写入身份档案，先进入待合并队列）
   - identity_target：当 tier 为 permanent 时建议填写 user | soul | memory（对应 USER.md / SOUL.md / MEMORY.md）
   - merge_hint：可选，合并到 Markdown 时的提示
   若省略 tier，视为 important。
2. events：事件；可增加 source_session_id（若未知可省略）、subject_actors（主体）、object_actors（客体）、
   triggers（触发词数组）、assertion：actual | negative | possible | not_occurred（默认 actual）。
   仍可使用 actors 表示参与者（兼容旧格式）。
   v3.0 可选字段（缺省则后端默认 world_kind=real、temporal_kind=past、planned_window 为空对象）：
   - world_kind：real（真实世界）| fictional（虚构/角色扮演）| hypothetical（假设/思想实验）| unknown（无法区分）
   - temporal_kind：past | present | future_planned | future_uncertain | atemporal
   - planned_window：对象，可与 future_planned 配合，例如 {"text": "下周", "resolution": "fuzzy"} 或含 start/end 的 ISO 时间
3. relations：事件之间的关系，用整数 relation_type 表示类型（见下表）

请严格按照下面的 JSON 结构输出（不要添加注释、不要输出 JSON 以外的任何文字）：

relation_type 取值：
- 0：无关系（不要输出该条）
- 1 因果：event_a 导致 event_b（因→果）
- 2 果因：event_a 为果、event_b 为因
- 3 前后时序：event_a 早于 event_b
- 4 后前时序：event_a 晚于 event_b
- 5 条件：event_a 是 event_b 成立的前提（条件→结果）
- 6 逆条件：event_a 为结果侧、event_b 为条件侧
- 7 目的：event_a 为达成 event_b（手段→目标）
- 8 逆目的：event_a 为目标、event_b 为手段
- 9 子事件：event_a 是 event_b 的子事件（子→父）
- 10 父事件：event_a 是 event_b 的父事件（父→子）
- 11 其它关系：必须在 explanation 中说明

{
  "facts": [
    {
      "key": "user.home_province",
      "value": "安徽",
      "summary": "用户说自己是安徽人",
      "confidence": 0.9,
      "tags": ["profile"],
      "tier": "important"
    }
  ],
  "events": [
    {
      "id": "e_1",
      "time": "2026-04-03 10:30",
      "location": "本地电脑",
      "actors": ["用户", "如意72"],
      "subject_actors": ["如意72"],
      "object_actors": ["用户"],
      "triggers": ["整理"],
      "assertion": "actual",
      "world_kind": "real",
      "temporal_kind": "past",
      "planned_window": {},
      "action": "如意72 帮用户整理了桌面上的文件和项目目录",
      "result": "用户对整理结果很满意",
      "metadata": {"skill": "file-organizer"}
    }
  ],
  "relations": [
    {
      "event_a_id": "e_1",
      "event_b_id": "e_2",
      "relation_type": 1,
      "explanation": "前一事为后一事的原因"
    }
  ]
}

兼容：若只能给出旧字段，可仅用字符串 "relation"（如「因果」）代替 relation_type，后端会推断。

注意：
- 没有可以提取的内容时，对应数组用 []。
- relation_type 为 0 时不要输出该关系项。
- tier 为 trivial 的事实不要输出（或输出后后端也会丢弃）。
"""


def _normalize_tier(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if s in ("trivial", "important", "permanent"):
        return s
    return "important"


def _normalize_identity_target(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if s in ("user", "soul", "memory"):
        return s
    return "memory"


def _normalize_assertion(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if s in ("actual", "negative", "possible", "not_occurred"):
        return s
    return "actual"


def _infer_relation_type_from_legacy_label(text: str) -> int:
    """根据 v1 风格自然语言标签推断整型（更具体的词优先）。"""
    t = text.strip()
    if not t:
        return 11
    ordered: list[tuple[int, tuple[str, ...]]] = [
        (6, ("逆条件",)),
        (8, ("逆目的",)),
        (5, ("条件", "前提")),
        (7, ("目的", "为了")),
        (2, ("果因",)),
        (1, ("因果",)),
        (4, ("后前", "晚于", "之后")),
        (3, ("前后", "早于", "之前", "前置")),
        (10, ("父事件",)),
        (9, ("子事件",)),
    ]
    for code, keys in ordered:
        if any(k in t for k in keys):
            return code
    return 11


def _parse_relation_item(item: dict, now: str) -> EventRelation | None:
    ea = str(item.get("event_a_id") or "").strip()
    eb = str(item.get("event_b_id") or "").strip()
    if not ea or not eb:
        return None

    expl = str(item.get("explanation") or "").strip()
    rel_str = str(item.get("relation") or "").strip()
    leg_in = str(item.get("relation_legacy") or "").strip()
    rt_raw = item.get("relation_type")

    if rt_raw is not None and rt_raw != "":
        try:
            rt = int(rt_raw)
        except (TypeError, ValueError):
            rt = None
        if rt is not None and rt == 0:
            return None
        if rt is not None and RELATION_TYPE_MIN <= rt <= RELATION_TYPE_MAX:
            legacy = leg_in or rel_str
            if rt == 11 and not expl:
                expl = legacy or "其它关系"
            elif not expl:
                expl = rel_str or RELATION_TYPE_LABELS.get(rt, "")
            return EventRelation(
                id=new_relation_id(),
                created_at=now,
                event_a_id=ea,
                event_b_id=eb,
                relation_type=rt,
                explanation=expl,
                relation_legacy=legacy,
            )

    if rel_str:
        rt = _infer_relation_type_from_legacy_label(rel_str)
        final_expl = expl or rel_str
        return EventRelation(
            id=new_relation_id(),
            created_at=now,
            event_a_id=ea,
            event_b_id=eb,
            relation_type=rt,
            explanation=final_expl,
            relation_legacy=rel_str,
        )
    return None


def extract_and_store_from_text(
    cfg: RuyiConfig,
    text: str,
    *,
    source_session_id: str | None = None,
) -> dict[str, int]:
    """调用本地 LLM，从给定文本中抽取三类记忆并写入 MemoryStore。返回各类数量。"""
    text = (text or "").strip()
    if not text:
        return {"facts": 0, "events": 0, "relations": 0, "pending_identity": 0}

    sid = (source_session_id or "").strip()
    timeout_sec = float(cfg.memory.extract_llm_timeout_sec)
    n_chars = len(text)
    max_in = int(cfg.memory.extract_max_input_chars)
    if n_chars > max_in:
        _LOG.warning("memory_extract input_too_long chars=%d max=%d", n_chars, max_in)
        return {
            "facts": 0,
            "events": 0,
            "relations": 0,
            "pending_identity": 0,
            "error": (
                f"粘贴内容过长（{n_chars} 字符），超过上限 {max_in}。"
                "请删减后重试、分段多次提取，或在 ruyi72.yaml 中增大 memory.extract_max_input_chars。"
            ),
        }

    extract_cap = int(cfg.memory.extract_max_tokens)
    _LOG.info(
        "memory_extract start chars=%d session_id=%s model=%s timeout_sec=%.0f "
        "extract_max_tokens=%d provider=%s",
        n_chars,
        sid or "(none)",
        cfg.llm.model,
        timeout_sec,
        extract_cap,
        cfg.llm.provider,
    )

    client = OllamaClient(cfg.llm)
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM_PROMPT.strip()},
        {"role": "user", "content": text},
    ]

    t_llm0 = time.perf_counter()
    _LOG.info(
        "memory_extract ollama_request_start read_timeout_sec=%.0f (httpx 读超时上限)",
        timeout_sec,
    )
    try:
        reply = client.chat(
            messages,
            caller="memory_extractor.extract_and_store_from_text",
            read_timeout_sec=timeout_sec,
            max_tokens_override=extract_cap,
        )
    except OllamaClientError as e:
        llm_ms = (time.perf_counter() - t_llm0) * 1000.0
        _LOG.warning(
            "memory_extract llm_error after_ms=%.0f chars=%d err=%s",
            llm_ms,
            n_chars,
            str(e)[:500],
        )
        return {
            "facts": 0,
            "events": 0,
            "relations": 0,
            "pending_identity": 0,
            "error": str(e),
        }

    llm_ms = (time.perf_counter() - t_llm0) * 1000.0
    reply_len = len(reply or "")
    _LOG.info(
        "memory_extract llm_ok ms=%.0f reply_chars=%d chars_in=%d",
        llm_ms,
        reply_len,
        n_chars,
    )
    if is_debug() and reply:
        _LOG.debug("memory_extract reply_head=%r", (reply[:500] + "…") if reply_len > 500 else reply)

    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        start = reply.find("{")
        end = reply.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(reply[start : end + 1])
            except json.JSONDecodeError:
                _LOG.warning(
                    "memory_extract json_parse_failed reply_chars=%d (brace_slice also failed)",
                    reply_len,
                )
                return {
                    "facts": 0,
                    "events": 0,
                    "relations": 0,
                    "pending_identity": 0,
                    "error": "JSON 解析失败",
                }
        else:
            _LOG.warning(
                "memory_extract json_parse_failed reply_chars=%d (no brace span)",
                reply_len,
            )
            return {
                "facts": 0,
                "events": 0,
                "relations": 0,
                "pending_identity": 0,
                "error": "JSON 解析失败",
            }

    if not isinstance(data, dict):
        _LOG.warning("memory_extract invalid_json_root type=%s", type(data).__name__)
        return {
            "facts": 0,
            "events": 0,
            "relations": 0,
            "pending_identity": 0,
            "error": "JSON 根节点不是对象",
        }

    store = default_store()
    now = _now_iso()

    raw_facts = data.get("facts") or []
    fact_objs: list[Fact] = []
    pending_objs: list[PendingIdentityMerge] = []
    for item in raw_facts:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        value = str(item.get("value") or "").strip()
        summary = str(item.get("summary") or "").strip() or value or key
        if not key or not value:
            continue
        tier = _normalize_tier(item.get("tier"))
        if tier == "trivial":
            continue
        conf = float(item.get("confidence") or 0.8)
        try:
            conf = max(0.0, min(1.0, conf))
        except Exception:
            conf = 0.8
        tags = item.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        tags = [str(t) for t in tags]
        merge_hint = str(item.get("merge_hint") or "").strip()
        id_target = _normalize_identity_target(item.get("identity_target"))

        if tier == "permanent":
            pending_objs.append(
                PendingIdentityMerge(
                    id=new_pending_identity_id(),
                    created_at=now,
                    identity_target=id_target,
                    key=key,
                    value=value,
                    summary=summary,
                    merge_hint=merge_hint,
                    confidence=conf,
                    tags=tags,
                    source_session_id=sid,
                )
            )
            continue

        fact = Fact(
            id=new_fact_id(),
            created_at=now,
            source="manual_text",
            key=key,
            value=value,
            summary=summary,
            confidence=conf,
            tags=tags,
            tier=tier,
            identity_target="",
            merge_hint=merge_hint,
        )
        fact_objs.append(fact)

    raw_events = data.get("events") or []
    event_objs: list[Event] = []
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        event_time = str(item.get("time") or "").strip()
        location = str(item.get("location") or "").strip()
        actors = item.get("actors") or []
        if not isinstance(actors, list):
            actors = []
        actors = [str(a) for a in actors]
        subj = item.get("subject_actors") or []
        if not isinstance(subj, list):
            subj = []
        subj = [str(a) for a in subj]
        obj = item.get("object_actors") or []
        if not isinstance(obj, list):
            obj = []
        obj = [str(a) for a in obj]
        trig = item.get("triggers") or []
        if not isinstance(trig, list):
            trig = []
        trig = [str(a) for a in trig]
        action = str(item.get("action") or "").strip()
        result = str(item.get("result") or "").strip()
        if not action and not result:
            continue
        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        ev_sid = str(item.get("source_session_id") or "").strip() or sid
        assertion = _normalize_assertion(item.get("assertion"))
        world_kind = normalize_event_world_kind(item.get("world_kind"))
        temporal_kind = normalize_event_temporal_kind(item.get("temporal_kind"))
        planned_window = normalize_planned_window_dict(item.get("planned_window"))
        event_objs.append(
            Event(
                id=new_event_id(),
                created_at=now,
                time=event_time,
                location=location,
                actors=actors,
                action=action,
                result=result,
                metadata=metadata,
                source_session_id=ev_sid,
                subject_actors=subj,
                object_actors=obj,
                triggers=trig,
                assertion=assertion,
                world_kind=world_kind,
                temporal_kind=temporal_kind,
                planned_window=planned_window,
            )
        )

    raw_rels = data.get("relations") or []
    rel_objs: list[EventRelation] = []
    for item in raw_rels:
        if not isinstance(item, dict):
            continue
        parsed = _parse_relation_item(item, now)
        if parsed is not None:
            rel_objs.append(parsed)

    n_facts = store.append_facts(fact_objs) if fact_objs else 0
    n_pending = store.append_pending_identity(pending_objs) if pending_objs else 0
    n_events = store.append_events(event_objs) if event_objs else 0
    n_rels = store.append_relations(rel_objs) if rel_objs else 0

    if fact_objs:
        _index_important_facts_vector(cfg, fact_objs)

    try:
        from src.storage.memory_sqlite import sync_sqlite_append

        sync_sqlite_append(cfg, store.root, facts=fact_objs, events=event_objs, relations=rel_objs)
    except Exception as e:
        _LOG.debug("memory_extract sync_sqlite_append skipped: %s", e)

    if event_objs:
        _index_events_vector(cfg, event_objs)

    _LOG.info(
        "memory_extract stored llm_ms=%.0f facts=%d pending_identity=%d events=%d relations=%d",
        llm_ms,
        n_facts,
        n_pending,
        n_events,
        n_rels,
    )
    return {
        "facts": n_facts,
        "pending_identity": n_pending,
        "events": n_events,
        "relations": n_rels,
    }
