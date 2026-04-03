from __future__ import annotations

"""跨会话记忆存储：以 JSONL 文档形式追加写入。"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Fact:
    id: str
    created_at: str
    source: str
    key: str
    value: str
    summary: str
    confidence: float
    tags: list[str]


@dataclass
class Event:
    id: str
    created_at: str
    time: str
    location: str
    actors: list[str]
    action: str
    result: str
    metadata: dict


@dataclass
class EventRelation:
    id: str
    created_at: str
    event_a_id: str
    event_b_id: str
    relation: str
    explanation: str


MemoryKind = Literal["facts", "events", "relations"]


class MemoryStore:
    """简单的 JSONL 文件存储，不做检索，仅负责持久化。"""

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = Path.home() / ".ruyi72" / "memory"
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _path_for(self, kind: MemoryKind) -> Path:
        return self._root / f"{kind}.jsonl"

    def append_facts(self, facts: Iterable[Fact]) -> int:
        return self._append("facts", facts)

    def append_events(self, events: Iterable[Event]) -> int:
        return self._append("events", events)

    def append_relations(self, relations: Iterable[EventRelation]) -> int:
        return self._append("relations", relations)

    def _append(self, kind: MemoryKind, items: Iterable[object]) -> int:
        path = self._path_for(kind)
        count = 0
        with path.open("a", encoding="utf-8") as f:
            for item in items:
                data = asdict(item)
                f.write(json.dumps(data, ensure_ascii=False))
                f.write("\n")
                count += 1
        return count

    def read_recent(self, kind: MemoryKind, limit: int = 20) -> list[dict]:
        """读取最近的若干条记忆，简单从文件尾部截取。"""
        path = self._path_for(kind)
        if not path.is_file():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        if limit > 0:
            lines = lines[-limit:]
        out: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
        return out


def default_store() -> MemoryStore:
    return MemoryStore(None)


def new_fact_id() -> str:
    return f"fact_{int(datetime.now(timezone.utc).timestamp() * 1000)}"


def new_event_id() -> str:
    return f"event_{int(datetime.now(timezone.utc).timestamp() * 1000)}"


def new_relation_id() -> str:
    return f"rel_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

