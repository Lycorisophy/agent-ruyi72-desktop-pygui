"""助手消息输出检查：同步引用、异步存疑、按节评审；持久化 output_annotations.json。"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.config import RuyiConfig
from src.llm.ollama import OllamaClient, OllamaClientError
from src.service.output_review_sync import (
    extend_citations_from_tools,
    extract_sections,
    extract_url_citations,
)
from src.service.utf16_text import (
    char_index_to_utf16_offset,
    utf16_length,
    utf16_span_to_char_span,
)

_LOG = logging.getLogger("ruyi72.output_review")


class CitationItem(BaseModel):
    id: str = ""
    start: int | None = None
    end: int | None = None
    url: str = ""
    title: str = ""


class DoubtItem(BaseModel):
    id: str = ""
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    severity: str = "low"
    reason: str = ""
    model: str = ""
    created_at: str = ""


class SectionItem(BaseModel):
    id: str = ""
    heading_level: int = Field(default=1, ge=1, le=6)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    title: str = ""


class SectionReviewItem(BaseModel):
    section_id: str = ""
    summary: str = ""
    issues: list[str] = Field(default_factory=list)
    created_at: str = ""


class MessageOutputRecord(BaseModel):
    schema_version: int = 1
    message_index: int = Field(ge=0)
    content_hash: str = ""
    citations: list[CitationItem] = Field(default_factory=list)
    doubts: list[DoubtItem] = Field(default_factory=list)
    sections: list[SectionItem] = Field(default_factory=list)
    section_reviews: dict[str, SectionReviewItem] = Field(default_factory=dict)
    doubt_job_status: str = ""  # "" | "pending" | "done" | "error"


def _content_fingerprint(content: str) -> str:
    return str(utf16_length(content or "")) + ":" + str(hash(content or ""))


def annotations_file(session_dir: Path) -> Path:
    return session_dir / "output_annotations.json"


def load_annotations_map(session_dir: Path) -> dict[str, Any]:
    p = annotations_file(session_dir)
    if not p.is_file():
        return {"schema_version": 1, "by_index": {}}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"schema_version": 1, "by_index": {}}
        raw.setdefault("schema_version", 1)
        raw.setdefault("by_index", {})
        return raw
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "by_index": {}}


def save_annotations_map(session_dir: Path, data: dict[str, Any]) -> None:
    p = annotations_file(session_dir)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_doubt_json(text: str, content: str, model_name: str) -> list[DoubtItem]:
    """解析模型返回的 JSON 数组；start/end 视为 UTF-16 与正文一致。"""
    t = (text or "").strip()
    if not t:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    try:
        arr = json.loads(t)
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []
    out: list[DoubtItem] = []
    max_u = char_index_to_utf16_offset(content, len(content))
    for it in arr[:24]:
        if not isinstance(it, dict):
            continue
        try:
            s = int(it.get("start", -1))
            e = int(it.get("end", -1))
        except (TypeError, ValueError):
            continue
        if s < 0 or e < 0 or s >= e or s >= max_u:
            continue
        e = min(e, max_u)
        sev = str(it.get("severity") or "low").lower()
        if sev not in ("low", "medium", "high"):
            sev = "low"
        out.append(
            DoubtItem(
                id=str(it.get("id") or f"d{len(out)}"),
                start=s,
                end=e,
                severity=sev,
                reason=str(it.get("reason") or "")[:500],
                model=model_name,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    return out


_DOUBT_SYSTEM = """你是文本审慎检查助手。只标出**可能**不准确、缺依据或与用户问题无关的夸大表述。
输出**仅**一个 JSON 数组，无其它文字。每个元素字段：
- start, end：在原文中的 UTF-16 码元索引（与 JavaScript 字符串一致），半开区间 [start,end)
- severity: "low" | "medium" | "high"
- reason: 一句中文说明（不超过 80 字）

不要超过 12 个片段；若无明显问题，输出 []。"""


def run_doubt_checker(
    cfg: RuyiConfig,
    content: str,
    *,
    user_context: str = "",
) -> list[DoubtItem]:
    orc = cfg.output_review
    text = (content or "")[: int(orc.checker_max_input_chars)]
    if not text.strip():
        return []
    model = (orc.checker_model or "").strip() or cfg.llm.model
    user_part = f"【用户/上下文】\n{user_context[:2000]}\n\n" if user_context else ""
    user_msg = (
        user_part
        + "【待检查正文】\n"
        + text
        + "\n\n请输出 JSON 数组。"
    )
    messages = [
        {"role": "system", "content": _DOUBT_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    try:
        client = OllamaClient(cfg.llm)
        reply = client.chat(
            messages,
            model_override=model,
            caller="output_review.run_doubt_checker",
            max_tokens_override=int(orc.checker_max_tokens),
            read_timeout_sec=float(orc.checker_timeout_sec),
        )
    except OllamaClientError as e:
        _LOG.warning("doubt checker failed: %s", e)
        return []
    return _parse_doubt_json(reply, content, model)


_SECTION_SYSTEM = """你是事实与依据检查助手。用户给出的是对话中**一小节**正文，请仅针对本节评估。
输出**仅**一个 JSON 对象，字段：
- summary: 一句中文本节要点（可选）
- issues: 字符串数组，每条不超过 100 字，描述可能的问题或缺失依据；若无问题则为 []

不要其它文字。"""


def run_section_review(
    cfg: RuyiConfig,
    section_text: str,
    *,
    section_title: str = "",
) -> SectionReviewItem:
    orc = cfg.output_review
    model = (orc.checker_model or "").strip() or cfg.llm.model
    body = (section_text or "")[: int(orc.checker_max_input_chars)]
    user_msg = f"【小节标题】{section_title}\n\n【正文】\n{body}"
    messages = [
        {"role": "system", "content": _SECTION_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    try:
        client = OllamaClient(cfg.llm)
        reply = client.chat(
            messages,
            model_override=model,
            caller="output_review.run_section_review",
            max_tokens_override=min(1024, int(orc.checker_max_tokens)),
            read_timeout_sec=float(orc.checker_timeout_sec),
        )
    except OllamaClientError as e:
        _LOG.warning("section review failed: %s", e)
        return SectionReviewItem(
            section_id="",
            summary="",
            issues=[str(e)[:200]],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    t = (reply or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        return SectionReviewItem(
            section_id="",
            summary="",
            issues=["无法解析模型输出"],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    if not isinstance(obj, dict):
        return SectionReviewItem(
            section_id="",
            summary="",
            issues=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    issues = obj.get("issues")
    if not isinstance(issues, list):
        issues = []
    issues_s = [str(x)[:200] for x in issues if str(x).strip()][:20]
    return SectionReviewItem(
        section_id="",
        summary=str(obj.get("summary") or "")[:500],
        issues=issues_s,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def build_sync_record(
    message_index: int,
    content: str,
    tool_rows: list[dict[str, Any]] | None = None,
) -> MessageOutputRecord:
    cites = extract_url_citations(content)
    if tool_rows:
        cites = extend_citations_from_tools(cites, tool_rows)
    secs = extract_sections(content)
    return MessageOutputRecord(
        message_index=message_index,
        content_hash=_content_fingerprint(content),
        citations=[CitationItem(**c) for c in cites],
        sections=[SectionItem(**s) for s in secs],
    )


def merge_record_with_stored(
    content: str,
    message_index: int,
    stored: MessageOutputRecord | None,
    tool_rows: list[dict[str, Any]] | None = None,
) -> MessageOutputRecord:
    sync = build_sync_record(message_index, content, tool_rows)
    if stored is None:
        return sync
    if stored.content_hash != sync.content_hash:
        # 正文已变：保留 doubts/reviews 仅当谨慎；此处清空存疑
        return MessageOutputRecord(
            message_index=message_index,
            content_hash=sync.content_hash,
            citations=sync.citations,
            sections=sync.sections,
            doubts=[],
            section_reviews={},
            doubt_job_status="",
        )
    return MessageOutputRecord(
        message_index=message_index,
        content_hash=sync.content_hash,
        citations=sync.citations,
        sections=sync.sections,
        doubts=stored.doubts,
        section_reviews=dict(stored.section_reviews),
        doubt_job_status=stored.doubt_job_status,
    )


def record_from_dict(d: dict[str, Any]) -> MessageOutputRecord:
    return MessageOutputRecord.model_validate(d)


def record_to_dict(rec: MessageOutputRecord) -> dict[str, Any]:
    return rec.model_dump(mode="json")


# —— 后台队列 —— #
_job_queue: queue.Queue[tuple[Any, ...]] | None = None
_worker_started = False
_worker_lock = threading.Lock()


def _ensure_worker() -> queue.Queue[tuple[Any, ...]]:
    global _job_queue, _worker_started
    with _worker_lock:
        if _job_queue is None:
            _job_queue = queue.Queue()
        if not _worker_started:
            _worker_started = True
            t = threading.Thread(target=_worker_loop, name="output-review-worker", daemon=True)
            t.start()
        return _job_queue


def _worker_loop() -> None:
    q = _job_queue
    if q is None:
        return
    while True:
        item = q.get()
        try:
            if item[0] == "doubt":
                _, cfg, session_dir, idx, content, user_ctx = item
                rec = _load_record(session_dir, idx)
                if rec is None:
                    continue
                if _content_fingerprint(content) != rec.content_hash:
                    continue
                doubts = run_doubt_checker(cfg, content, user_context=user_ctx)
                data = load_annotations_map(session_dir)
                by = data.get("by_index")
                if not isinstance(by, dict):
                    continue
                key = str(idx)
                if key not in by:
                    continue
                cur = record_from_dict(by[key])
                cur.doubts = doubts
                cur.doubt_job_status = "done"
                by[key] = record_to_dict(cur)
                save_annotations_map(session_dir, data)
        except Exception:
            _LOG.exception("output review worker job failed")
        finally:
            try:
                q.task_done()
            except Exception:
                pass


def enqueue_doubt_job(
    cfg: RuyiConfig,
    session_dir: Path,
    message_index: int,
    content: str,
    user_context: str,
) -> None:
    if not cfg.output_review.enabled or not cfg.output_review.async_doubt_after_reply:
        return
    _ensure_worker().put(
        ("doubt", cfg, session_dir, message_index, content, user_context)
    )


def _load_record(session_dir: Path, idx: int) -> MessageOutputRecord | None:
    data = load_annotations_map(session_dir)
    by = data.get("by_index")
    if not isinstance(by, dict):
        return None
    raw = by.get(str(idx))
    if not isinstance(raw, dict):
        return None
    try:
        return record_from_dict(raw)
    except Exception:
        return None


def persist_merged_record(session_dir: Path, rec: MessageOutputRecord) -> None:
    data = load_annotations_map(session_dir)
    by = data.setdefault("by_index", {})
    assert isinstance(by, dict)
    by[str(rec.message_index)] = record_to_dict(rec)
    save_annotations_map(session_dir, data)


def api_get_message_annotations(
    cfg: RuyiConfig,
    session_dir: Path,
    messages: list[dict[str, Any]],
    message_index: int,
) -> dict[str, Any]:
    if not cfg.output_review.enabled:
        return {"ok": True, "enabled": False}
    if message_index < 0 or message_index >= len(messages):
        return {"ok": False, "error": "消息下标无效"}
    msg = messages[message_index]
    if str(msg.get("role") or "") != "assistant":
        return {"ok": False, "error": "仅支持助手消息"}
    content = str(msg.get("content") or "")
    tool_raw = msg.get("tool_citations")
    tool_rows: list[dict[str, Any]] | None = None
    if isinstance(tool_raw, list) and tool_raw:
        tool_rows = [x for x in tool_raw if isinstance(x, dict)]
    data = load_annotations_map(session_dir)
    by = data.get("by_index")
    if not isinstance(by, dict):
        by = {}
    raw_stored = by.get(str(message_index))
    stored: MessageOutputRecord | None = None
    if isinstance(raw_stored, dict):
        try:
            stored = record_from_dict(raw_stored)
        except Exception:
            stored = None
    merged = merge_record_with_stored(content, message_index, stored, tool_rows)
    persist_merged_record(session_dir, merged)
    return {
        "ok": True,
        "enabled": True,
        "annotation": record_to_dict(merged),
    }


def api_request_output_review(
    cfg: RuyiConfig,
    session_dir: Path,
    messages: list[dict[str, Any]],
    message_index: int,
    user_context: str = "",
) -> dict[str, Any]:
    if not cfg.output_review.enabled:
        return {"ok": False, "error": "output_review 未启用"}
    if not cfg.output_review.async_doubt_after_reply:
        return {"ok": False, "error": "未开启 async_doubt_after_reply"}
    if message_index < 0 or message_index >= len(messages):
        return {"ok": False, "error": "消息下标无效"}
    msg = messages[message_index]
    if str(msg.get("role") or "") != "assistant":
        return {"ok": False, "error": "仅支持助手消息"}
    content = str(msg.get("content") or "")
    g = api_get_message_annotations(cfg, session_dir, messages, message_index)
    if not g.get("ok"):
        return g
    ann = g.get("annotation") or {}
    rec = record_from_dict(ann)
    if rec.doubt_job_status == "pending":
        return {"ok": True, "status": "pending"}
    if rec.doubt_job_status == "done":
        return {"ok": True, "status": "done"}
    # error 时允许再次排队重试
    rec.doubt_job_status = "pending"
    persist_merged_record(session_dir, rec)
    enqueue_doubt_job(cfg, session_dir, message_index, content, user_context)
    return {"ok": True, "status": "queued"}


def api_review_message_section(
    cfg: RuyiConfig,
    session_dir: Path,
    messages: list[dict[str, Any]],
    message_index: int,
    section_id: str,
) -> dict[str, Any]:
    if not cfg.output_review.enabled:
        return {"ok": False, "error": "output_review 未启用"}
    if message_index < 0 or message_index >= len(messages):
        return {"ok": False, "error": "消息下标无效"}
    msg = messages[message_index]
    content = str(msg.get("content") or "")
    g = api_get_message_annotations(cfg, session_dir, messages, message_index)
    if not g.get("ok"):
        return g
    ann = g.get("annotation") or {}
    rec = record_from_dict(ann)
    sec = next((s for s in rec.sections if s.id == section_id), None)
    if sec is None:
        return {"ok": False, "error": "小节不存在"}
    cs, ce = utf16_span_to_char_span(content, sec.start, sec.end)
    section_text = content[cs:ce]
    rev = run_section_review(cfg, section_text, section_title=sec.title)
    rev.section_id = section_id
    rec.section_reviews[section_id] = rev
    persist_merged_record(session_dir, rec)
    return {"ok": True, "review": rev.model_dump(mode="json")}
