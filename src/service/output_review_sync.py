"""同步层：从正文中提取 URL 引用（跳过 fenced code block），并划分 Markdown/弱规则章节。"""

from __future__ import annotations

import re
from typing import Any

from src.service.utf16_text import char_index_to_utf16_offset

# 保守 URL：非空白截断
_URL_RE = re.compile(r"https?://[^\s\]\)\"\'<>]+", re.IGNORECASE)


def _strip_trailing_punct(url: str) -> str:
    u = url.rstrip()
    while u and u[-1] in ".,;:!?）】」」）":
        u = u[:-1]
    return u


def _iter_non_code_spans(text: str) -> list[tuple[int, int]]:
    """返回非 ``` fenced 块内的 (char_start, char_end) 半开区间。"""
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    fence = "```"
    while i < n:
        j = text.find(fence, i)
        if j < 0:
            spans.append((i, n))
            break
        if j > i:
            spans.append((i, j))
        close = text.find(fence, j + 3)
        if close < 0:
            i = n
            break
        i = close + len(fence)
        while i < n and text[i] in "\r\n":
            i += 1
    return spans


def extract_url_citations(content: str) -> list[dict[str, Any]]:
    """
    返回 citations：start/end 为 UTF-16 码元偏移（与前端 Range/JS 一致）。
    """
    raw = content or ""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    spans = _iter_non_code_spans(raw)
    for a, b in spans:
        segment = raw[a:b]
        for m in _URL_RE.finditer(segment):
            url = _strip_trailing_punct(m.group(0))
            if not url or url in seen:
                continue
            seen.add(url)
            abs_start = a + m.start()
            abs_end = a + m.end()
            # 与 strip 对齐
            while abs_end > abs_start and raw[abs_end - 1 : abs_end] in ".,;:!?）】」":
                abs_end -= 1
            u0 = char_index_to_utf16_offset(raw, abs_start)
            u1 = char_index_to_utf16_offset(raw, abs_end)
            out.append(
                {
                    "id": f"u{len(out)}",
                    "start": u0,
                    "end": u1,
                    "url": url,
                    "title": "",
                }
            )
    return out


def extract_urls_as_tool_citation_rows(text: str) -> list[dict[str, Any]]:
    """
    从文本中提取 https URL（跳过 fenced 块，规则与 extract_url_citations 一致），
    不设 start/end，供 ReAct 记忆/检索类工具在无 JSON citations 时侧栏合并。
    """
    raw = text or ""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    spans = _iter_non_code_spans(raw)
    for a, b in spans:
        segment = raw[a:b]
        for m in _URL_RE.finditer(segment):
            url = _strip_trailing_punct(m.group(0))
            if not url:
                continue
            abs_start = a + m.start()
            abs_end = a + m.end()
            while abs_end > abs_start and raw[abs_end - 1 : abs_end] in ".,;:!?）】」":
                abs_end -= 1
            url = _strip_trailing_punct(raw[abs_start:abs_end])
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({"url": url, "title": ""})
    return out


_HEADING_MD = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_HEADING_CN = re.compile(r"^([一二三四五六七八九十]+[、．.])\s*(.+)$", re.MULTILINE)
_HEADING_NUM = re.compile(r"^(\d+[\.、])\s*(.+)$", re.MULTILINE)


def extract_sections(content: str) -> list[dict[str, Any]]:
    """章节 [start,end) 为 UTF-16；用于按节检查按钮。"""
    raw = content or ""
    lines = raw.splitlines(keepends=True)
    headings: list[tuple[int, int, int, str]] = []
    char_pos = 0
    for line in lines:
        stripped = line.lstrip()
        title = ""
        level = 1
        if stripped.startswith("#"):
            m = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
        elif _HEADING_CN.match(stripped):
            m = _HEADING_CN.match(stripped)
            assert m is not None
            title = (m.group(2) or m.group(0)).strip()
            level = 2
        elif _HEADING_NUM.match(stripped):
            m = _HEADING_NUM.match(stripped)
            assert m is not None
            title = (m.group(2) or m.group(0)).strip()
            level = 2
        if title:
            c0 = char_pos
            c1 = char_pos + len(line)
            u0 = char_index_to_utf16_offset(raw, c0)
            u1 = char_index_to_utf16_offset(raw, c1)
            headings.append((u0, u1, level, title[:200]))
        char_pos += len(line)

    if not headings:
        return []

    sections: list[dict[str, Any]] = []
    total_u16 = char_index_to_utf16_offset(raw, len(raw))
    for i, (u0, u1, level, title) in enumerate(headings):
        next_start = headings[i + 1][0] if i + 1 < len(headings) else total_u16
        sections.append(
            {
                "id": f"s{i}",
                "heading_level": level,
                "start": u0,
                "end": next_start,
                "title": title,
            }
        )
    return sections


def extend_citations_from_tools(
    base: list[dict[str, Any]], tool_rows: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """
    P3：合并检索工具返回的引用（url/title/start/end 可选）。
    无 offset 的条目仅追加到列表供侧栏展示，不强行对齐正文。
    """
    out = list(base)
    if not tool_rows:
        return out
    seen = {str(c.get("url") or "") for c in out}
    for i, row in enumerate(tool_rows):
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        item: dict[str, Any] = {
            "id": f"t{i}",
            "url": url,
            "title": str(row.get("title") or "")[:300],
        }
        try:
            s = int(row.get("start", -1))
            e = int(row.get("end", -1))
            if s >= 0 and e > s:
                item["start"] = s
                item["end"] = e
        except (TypeError, ValueError):
            pass
        out.append(item)
    return out
