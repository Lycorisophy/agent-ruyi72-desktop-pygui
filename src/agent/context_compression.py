"""会话上文压缩：检查点 + token 估算 + 启发式裁剪 + LLM 摘要。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.config import RuyiConfig

_LOG = logging.getLogger("ruyi72.context_compression")

SUMMARY_USER_PROMPT = """以下摘录按时间从早到晚排列（越靠上越早、越靠下越近）。

请用中文输出一段摘要（总长度不超过规定字符数），并遵守**压缩梯度**：
- **越早的对话**：允许概括得更狠，只保留主题线索与里程碑，细节可删。
- **越近的对话**：保留更多原意与具体表述，尽量少删。
- **用户明确提出的指令、要求、约束**：无论早晚，压缩程度都要**低**，尽量保留原意甚至短句引用。
- **已确认的结论、约定、关键决策**：压缩程度**低**，表述要准。

将「此前已摘要」与本轮摘录合并为**一份**连贯摘要：旧摘要中若与上述冲突，以更近的对话为准；旧摘要可对更早部分再压缩一层。

只输出摘要正文，不要前缀说明或 Markdown 标题。

---
{chunk}
---
"""


class ContextCheckpoint(BaseModel):
    """持久化于会话目录 context_checkpoint.json。"""

    schema_version: int = 1
    anchor_message_index: int = Field(default=0, ge=0)
    summary_text: str = ""
    updated_at: str = ""
    compression_round: int = Field(default=0, ge=0)


def estimate_tokens_messages(messages: list[dict[str, Any]]) -> int:
    """粗估 token：总字符 / 4（中英混合近似）。"""
    n = 0
    for m in messages:
        c = str(m.get("content") or "")
        n += max(1, len(c) // 4) if c else 0
    return n


def raw_flat_from_stored_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """与 ConversationService 原 messages_for_llm 一致：仅 role + content。"""
    return [
        {"role": str(m.get("role") or "user"), "content": str(m.get("content") or "")}
        for m in messages
    ]


def apply_checkpoint_to_flat(
    raw_flat: list[dict[str, str]],
    ck: ContextCheckpoint | None,
) -> list[dict[str, str]]:
    """在原始扁平消息上应用检查点：摘要 system + tail[anchor:]。"""
    if not ck or ck.anchor_message_index <= 0:
        return list(raw_flat)
    anchor = min(ck.anchor_message_index, len(raw_flat))
    tail = raw_flat[anchor:]
    st = (ck.summary_text or "").strip()
    if st:
        # user：便于 team_turn 等仅转发 user/assistant 的入口仍带上摘要
        return [
            {"role": "user", "content": f"【会话前文摘要】\n{st}"},
        ] + tail
    return tail


def phase_a_trim_long_messages(
    msgs: list[dict[str, str]], *, max_chars: int
) -> list[dict[str, str]]:
    """阶段 A：对过长单条做头尾保留截断（不改变磁盘上的 messages.json）。"""
    if max_chars < 200:
        return list(msgs)
    out: list[dict[str, str]] = []
    half = max(100, max_chars // 2 - 40)
    for m in msgs:
        role = str(m.get("role") or "user")
        c = str(m.get("content") or "")
        if len(c) <= max_chars:
            out.append({"role": role, "content": c})
            continue
        mid = "\n…[中间已省略]…\n"
        c2 = c[:half] + mid + c[-half:]
        out.append({"role": role, "content": c2})
    return out


def phase_a_skip_leading_empty(
    raw_flat: list[dict[str, str]], anchor: int
) -> int:
    """在 [anchor, end) 内跳过首部空消息，返回新 anchor（不减小）。"""
    i = max(0, anchor)
    while i < len(raw_flat) and not str(raw_flat[i].get("content") or "").strip():
        i += 1
    return i


def format_chunk_for_summary(raw_flat: list[dict[str, str]], start: int, end: int) -> str:
    """将 [start,end) 格式化为摘要输入；块内越早的行截断越狠，越近保留越长。"""
    lines: list[str] = []
    s, e = max(0, start), min(end, len(raw_flat))
    span = max(1, e - s)
    for i in range(s, e):
        m = raw_flat[i]
        role = m.get("role", "user")
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        tag = "用户" if role == "user" else ("助手" if role == "assistant" else role)
        one = content.replace("\n", " ")
        # 块内相对位置 0=最早 → 1=最晚；单条时按「最近」给足长度
        pos = (i - s) / max(1, span - 1) if span > 1 else 1.0
        # 早约 380 字封顶，晚约 1400 字封顶（用户句略多给一点，便于保留指令）
        base = 380 + pos * 1020
        max_line = int(base + (80 if role == "user" else 0))
        if len(one) > max_line:
            one = one[: max_line - 1] + "…"
        lines.append(f"[{tag}] {one}")
    return "\n".join(lines)


def summarize_chunk_with_llm(
    cfg: RuyiConfig,
    *,
    existing_summary: str,
    chunk_text: str,
    max_out_chars: int,
) -> str:
    """调用主 LLM 生成摘要文本。"""
    from src.llm.ollama import OllamaClient, OllamaClientError

    parts: list[str] = []
    if (existing_summary or "").strip():
        parts.append("【此前已摘要】\n" + existing_summary.strip())
    parts.append(SUMMARY_USER_PROMPT.format(chunk=chunk_text))
    user_content = "\n\n".join(parts)
    cc = cfg.context_compression
    max_tok = min(int(cc.summary_max_tokens), 4096)
    messages = [
        {
            "role": "system",
            "content": (
                "你是对话压缩助手，只输出摘要正文，不要客套。"
                "摘要须体现时间梯度：越早的内容越概括，越近的内容越完整。"
                "用户指令与关键结论、约定在任何位置都要少压缩、保准确。"
            ),
        },
        {"role": "user", "content": user_content},
    ]
    try:
        client = OllamaClient(cfg.llm)
        reply = client.chat(
            messages,
            caller="context_compression.summarize",
            max_tokens_override=max_tok,
        )
    except OllamaClientError as e:
        _LOG.warning("context_compression summarize failed: %s", e)
        return existing_summary.strip() + "\n\n（摘要生成失败，已保留部分原文索引。）"
    text = (reply or "").strip()
    if len(text) > max_out_chars:
        text = text[: max_out_chars - 1] + "…"
    return text


def run_compression_round(
    cfg: RuyiConfig,
    raw_flat: list[dict[str, str]],
    ck: ContextCheckpoint,
) -> ContextCheckpoint:
    """一轮压缩：先 phase A，再必要时 LLM 折叠一段。"""
    from datetime import datetime, timezone

    def _iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    cc = cfg.context_compression
    anchor = min(ck.anchor_message_index, len(raw_flat))
    anchor = phase_a_skip_leading_empty(raw_flat, anchor)

    n = len(raw_flat)
    if anchor >= n:
        return ContextCheckpoint(
            anchor_message_index=anchor,
            summary_text=ck.summary_text,
            updated_at=_iso(),
            compression_round=ck.compression_round,
        )

    # 至少再折叠「剩余一半」或 1 条（chunk 内从早到晚，format 对早段截断更狠）
    new_anchor = min(n, anchor + max(1, (n - anchor) // 2))
    if new_anchor <= anchor:
        new_anchor = min(n, anchor + 1)

    chunk = format_chunk_for_summary(raw_flat, anchor, new_anchor)
    if not chunk.strip():
        return ContextCheckpoint(
            anchor_message_index=new_anchor,
            summary_text=ck.summary_text,
            updated_at=_iso(),
            compression_round=ck.compression_round + 1,
        )

    merged = summarize_chunk_with_llm(
        cfg,
        existing_summary=ck.summary_text,
        chunk_text=chunk,
        max_out_chars=int(cc.max_summary_chars),
    )
    return ContextCheckpoint(
        anchor_message_index=new_anchor,
        summary_text=merged[: int(cc.max_summary_chars)],
        updated_at=_iso(),
        compression_round=ck.compression_round + 1,
    )
