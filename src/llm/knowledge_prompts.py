"""知识库会话：从 resources/knowledge_base 加载系统说明片段。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_KB_ROOT = Path(__file__).resolve().parent.parent.parent / "resources" / "knowledge_base"
_VALID_PRESETS = frozenset({"general", "ingest", "summarize", "qa"})


def _read_file(rel: str) -> str:
    p = _KB_ROOT / rel
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


@lru_cache(maxsize=8)
def _cached_bundle(preset: str) -> str:
    common = _read_file("common.md")
    body = _read_file(f"presets/{preset}.md")
    parts = [
        "【知识库管理 · 会话专用说明】",
        common or "（未找到 common.md，请检查 resources/knowledge_base。）",
    ]
    if body:
        parts.append(body)
    return "\n\n".join(parts).strip()


def knowledge_base_system_hint(preset: str | None) -> str:
    """返回拼入 Chat / ReAct system 的知识库说明（含公共段与 preset 专段）。"""
    p = (preset or "general").strip().lower()
    if p not in _VALID_PRESETS:
        p = "general"
    return _cached_bundle(p)


def clear_knowledge_prompt_cache() -> None:
    """测试或热重载时可调用。"""
    _cached_bundle.cache_clear()
