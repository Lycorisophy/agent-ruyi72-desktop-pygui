"""对话模式：从模型回复中解析 action_card，与会话内确认卡片协议。"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

ACTION_CARD_FENCE = re.compile(
    r"```\s*action_card\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)

_CARD_STATUSES = frozenset(
    {"pending", "confirmed", "rejected", "expired", "superseded"}
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_pending_card_from_llm_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    """由模型 JSON 生成待确认卡片（补 id、status、countdown）。"""
    title = str(data.get("title") or "").strip()[:500]
    if not title:
        return None
    body = str(data.get("body") or "").strip()[:8000] or ""
    raw_cs = data.get("countdown_sec", 60)
    try:
        cs = int(raw_cs)
    except (TypeError, ValueError):
        cs = 60
    cs = max(10, min(600, cs))
    options_raw = data.get("options")
    if not isinstance(options_raw, list) or not options_raw:
        return None
    options: list[dict[str, Any]] = []
    for o in options_raw[:24]:
        if not isinstance(o, dict):
            continue
        oid = str(o.get("id") or "").strip()[:64]
        label = str(o.get("label") or "").strip()[:300]
        if not oid or not label:
            continue
        options.append({"id": oid, "label": label, "default": bool(o.get("default"))})
    if not options:
        return None
    return {
        "v": 1,
        "id": uuid.uuid4().hex,
        "title": title,
        "body": body,
        "options": options,
        "countdown_sec": cs,
        "status": "pending",
    }


def split_reply_action_card(raw: str) -> tuple[str, dict[str, Any] | None]:
    """
    从 assistant 原文中移除 ```action_card``` 块，并解析 JSON。
    返回 (可见正文, 卡片或 None)。
    """
    m = ACTION_CARD_FENCE.search(raw)
    if not m:
        return raw.strip(), None
    inner = m.group(1).strip()
    try:
        data = json.loads(inner)
    except json.JSONDecodeError:
        return raw.strip(), None
    if not isinstance(data, dict):
        return raw.strip(), None
    ver = data.get("v", 1)
    if ver != 1:
        return raw.strip(), None
    card = build_pending_card_from_llm_payload(data)
    visible = ACTION_CARD_FENCE.sub("", raw).strip()
    return visible, card


def sanitize_card_from_storage(card: Any) -> dict[str, Any] | None:
    """从磁盘读出时校验，防止畸形或过大对象。"""
    if not isinstance(card, dict):
        return None
    cid = str(card.get("id") or "").strip()[:64]
    if not cid:
        return None
    title = str(card.get("title") or "").strip()[:500]
    if not title:
        return None
    body = str(card.get("body") or "").strip()[:8000]
    status = str(card.get("status") or "pending")
    if status not in _CARD_STATUSES:
        status = "pending"
    try:
        cs = int(card.get("countdown_sec", 60))
    except (TypeError, ValueError):
        cs = 60
    cs = max(10, min(600, cs))
    options_raw = card.get("options")
    if not isinstance(options_raw, list):
        return None
    options: list[dict[str, Any]] = []
    for o in options_raw[:24]:
        if not isinstance(o, dict):
            continue
        oid = str(o.get("id") or "").strip()[:64]
        label = str(o.get("label") or "").strip()[:300]
        if not oid or not label:
            continue
        options.append({"id": oid, "label": label, "default": bool(o.get("default"))})
    if not options:
        return None
    out: dict[str, Any] = {
        "v": 1,
        "id": cid,
        "title": title,
        "body": body,
        "options": options,
        "countdown_sec": cs,
        "status": status,
    }
    resolved_at = card.get("resolved_at")
    if isinstance(resolved_at, str) and len(resolved_at) < 80:
        out["resolved_at"] = resolved_at
    sel = card.get("selected_ids")
    if isinstance(sel, list):
        out["selected_ids"] = [str(x)[:64] for x in sel[:24] if isinstance(x, (str, int))]
    via = card.get("via")
    if via == "timeout":
        out["via"] = "timeout"
    return out


def supersede_pending_cards(messages: list[dict[str, Any]]) -> None:
    for m in messages:
        c = m.get("card")
        if isinstance(c, dict) and c.get("status") == "pending":
            c["status"] = "superseded"
            c.pop("via", None)
