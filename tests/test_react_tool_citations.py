"""ReAct 工具 citations 解析与 output_review 合并（unittest）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from src.agent.react_lc import (  # noqa: E402
    _citation_rows_from_tool_text,
    collect_citation_rows_from_agent_messages,
)
from src.service.output_review import build_sync_record  # noqa: E402
from src.service.output_review_sync import extract_urls_as_tool_citation_rows  # noqa: E402


class TestCitationRowsFromToolText(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(_citation_rows_from_tool_text(""), [])

    def test_whole_json(self) -> None:
        raw = '{"citations":[{"url":"https://a.example/x","title":"A"}]}'
        rows = _citation_rows_from_tool_text(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://a.example/x")
        self.assertEqual(rows[0]["title"], "A")

    def test_fenced_json(self) -> None:
        raw = """intro
```json
{"citations":[{"url":"https://b.example","title":""}]}
```
"""
        rows = _citation_rows_from_tool_text(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://b.example")


class TestCollectCitationRows(unittest.TestCase):
    def test_no_final_ai(self) -> None:
        msgs = [
            HumanMessage(content="hi"),
            ToolMessage(
                content='{"citations":[{"url":"https://x.com"}]}',
                tool_call_id="1",
            ),
        ]
        self.assertEqual(collect_citation_rows_from_agent_messages(msgs), [])

    def test_tool_before_last_assistant(self) -> None:
        js = '{"citations":[{"url":"https://doc.example/p","title":"P"}]}'
        msgs = [
            HumanMessage(content="q"),
            ToolMessage(content=js, tool_call_id="t1", name="search_history"),
            AIMessage(content="Answer with https://inline.com ref."),
        ]
        rows = collect_citation_rows_from_agent_messages(msgs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://doc.example/p")

    def test_dedupe_by_url(self) -> None:
        js = '{"citations":[{"url":"https://same.io"},{"url":"https://same.io","title":"dup"}]}'
        msgs = [
            HumanMessage(content="q"),
            ToolMessage(content=js, tool_call_id="t1"),
            AIMessage(content="ok"),
        ]
        rows = collect_citation_rows_from_agent_messages(msgs)
        self.assertEqual(len(rows), 1)

    def test_url_fallback_for_whitelist_tool(self) -> None:
        plain = "命中片段见 https://example.com/doc 与 https://other.io/path "
        msgs = [
            HumanMessage(content="q"),
            ToolMessage(content=plain, tool_call_id="t1", name="search_history"),
            AIMessage(content="总结如上。"),
        ]
        rows = collect_citation_rows_from_agent_messages(msgs)
        urls = {r["url"] for r in rows}
        self.assertIn("https://example.com/doc", urls)
        self.assertIn("https://other.io/path", urls)

    def test_no_url_fallback_for_non_whitelist_tool(self) -> None:
        plain = "链接 https://evil.com/x 勿提取"
        msgs = [
            HumanMessage(content="q"),
            ToolMessage(content=plain, tool_call_id="t1", name="read_file"),
            AIMessage(content="ok"),
        ]
        self.assertEqual(collect_citation_rows_from_agent_messages(msgs), [])


class TestExtractUrlsAsToolCitationRows(unittest.TestCase):
    def test_skips_fenced_code(self) -> None:
        text = "```\nhttps://skip.me/hidden\n```\n可见 https://keep.me/a"
        rows = extract_urls_as_tool_citation_rows(text)
        urls = [r["url"] for r in rows]
        self.assertIn("https://keep.me/a", urls)
        self.assertNotIn("https://skip.me/hidden", urls)


class TestBuildSyncRecordMerge(unittest.TestCase):
    def test_tool_rows_merge(self) -> None:
        content = "See https://in-body.com for more."
        rec = build_sync_record(
            0,
            content,
            [{"url": "https://tool-only.com", "title": "T"}],
        )
        urls = {c.url for c in rec.citations}
        self.assertIn("https://in-body.com", urls)
        self.assertIn("https://tool-only.com", urls)


if __name__ == "__main__":
    unittest.main()
