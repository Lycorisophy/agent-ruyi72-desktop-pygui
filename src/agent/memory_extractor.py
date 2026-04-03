from __future__ import annotations

"""记忆抽取器：从一段文本中提取事实 / 事件 / 事件关系并写入 MemoryStore。"""

import json
from typing import Any

from src.config import LLMConfig
from src.llm.ollama import OllamaClient, OllamaClientError
from src.storage.memory_store import (
    Event,
    EventRelation,
    Fact,
    default_store,
    new_event_id,
    new_fact_id,
    new_relation_id,
    _now_iso,
)


EXTRACT_SYSTEM_PROMPT = """
你是一个记忆抽取助手。现在给你一段中文或英文文本，请你从中提取三类结构化记忆：

1. facts：事实（主要关于用户本身的稳定特征 / 偏好 / 约定）
2. events：事件（在某个时间、地点，由若干人物参与，发生的事情）
3. relations：事件之间的关系（如因果、前后、类似、对比等）

请严格按照下面的 JSON 结构输出（不要添加多余文字）：

{
  "facts": [
    {
      "key": "user.home_province",
      "value": "安徽",
      "summary": "用户说自己是安徽人",
      "confidence": 0.9,
      "tags": ["profile"]
    }
  ],
  "events": [
    {
      "id": "e_1",  // 如不确定可随意给一个简短 id，后端会重写
      "time": "2026-04-03 10:30",
      "location": "本地电脑",
      "actors": ["用户", "如意72"],
      "action": "如意72 帮用户整理了桌面上的文件和项目目录",
      "result": "用户对整理结果很满意",
      "metadata": {"skill": "file-organizer"}
    }
  ],
  "relations": [
    {
      "event_a_id": "e_1",
      "event_b_id": "e_2",
      "relation": "因果",
      "explanation": "简要说明为什么存在这种关系"
    }
  ]
}

注意：
- 没有可以提取的内容时，对应数组用 []。
- 不要输出 JSON 以外的任何文字。
"""


def extract_and_store_from_text(llm_cfg: LLMConfig, text: str) -> dict[str, int]:
    """调用本地 LLM，从给定文本中抽取三类记忆并写入 MemoryStore。返回各类数量。"""
    text = (text or "").strip()
    if not text:
        return {"facts": 0, "events": 0, "relations": 0}

    client = OllamaClient(llm_cfg)
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM_PROMPT.strip()},
        {"role": "user", "content": text},
    ]

    try:
        reply = client.chat(messages)
    except OllamaClientError as e:
        # 记忆抽取失败时，不抛异常到前端，只计为 0 并在消息中展示错误由上层处理。
        return {"facts": 0, "events": 0, "relations": 0, "error": str(e)}

    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        # 简单容错：尝试截取首尾大括号
        start = reply.find("{")
        end = reply.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(reply[start : end + 1])
            except json.JSONDecodeError:
                return {"facts": 0, "events": 0, "relations": 0, "error": "JSON 解析失败"}
        else:
            return {"facts": 0, "events": 0, "relations": 0, "error": "JSON 解析失败"}

    if not isinstance(data, dict):
        return {"facts": 0, "events": 0, "relations": 0, "error": "JSON 根节点不是对象"}

    store = default_store()
    now = _now_iso()

    # 解析 facts
    raw_facts = data.get("facts") or []
    fact_objs: list[Fact] = []
    for item in raw_facts:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        value = str(item.get("value") or "").strip()
        summary = str(item.get("summary") or "").strip() or value or key
        if not key or not value:
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
        fact_objs.append(
            Fact(
                id=new_fact_id(),
                created_at=now,
                source="manual_text",
                key=key,
                value=value,
                summary=summary,
                confidence=conf,
                tags=tags,
            )
        )

    # 解析 events
    raw_events = data.get("events") or []
    event_objs: list[Event] = []
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        time = str(item.get("time") or "").strip()
        location = str(item.get("location") or "").strip()
        actors = item.get("actors") or []
        if not isinstance(actors, list):
            actors = []
        actors = [str(a) for a in actors]
        action = str(item.get("action") or "").strip()
        result = str(item.get("result") or "").strip()
        if not action and not result:
            continue
        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        event_objs.append(
            Event(
                id=new_event_id(),
                created_at=now,
                time=time,
                location=location,
                actors=actors,
                action=action,
                result=result,
                metadata=metadata,
            )
        )

    # 解析 relations
    raw_rels = data.get("relations") or []
    rel_objs: list[EventRelation] = []
    for item in raw_rels:
        if not isinstance(item, dict):
            continue
        ea = str(item.get("event_a_id") or "").strip()
        eb = str(item.get("event_b_id") or "").strip()
        rel = str(item.get("relation") or "").strip()
        expl = str(item.get("explanation") or "").strip()
        if not ea or not eb or not rel:
            continue
        rel_objs.append(
            EventRelation(
                id=new_relation_id(),
                created_at=now,
                event_a_id=ea,
                event_b_id=eb,
                relation=rel,
                explanation=expl,
            )
        )

    n_facts = store.append_facts(fact_objs) if fact_objs else 0
    n_events = store.append_events(event_objs) if event_objs else 0
    n_rels = store.append_relations(rel_objs) if rel_objs else 0

    return {"facts": n_facts, "events": n_events, "relations": n_rels}

