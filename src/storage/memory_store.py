from __future__ import annotations

"""跨会话记忆存储：以 JSONL 文档形式追加写入。"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

# 事件关系类型（v2.0）：0 表示无关系不落库；1–11 见设计文档 §4.1.2
RELATION_TYPE_NONE = 0
RELATION_TYPE_MIN = 1
RELATION_TYPE_MAX = 11

RELATION_TYPE_LABELS: dict[int, str] = {
    1: "因果",
    2: "果因",
    3: "前后时序",
    4: "后前时序",
    5: "条件",
    6: "逆条件",
    7: "目的",
    8: "逆目的",
    9: "子事件",
    10: "父事件",
    11: "其它关系",
}


def relation_type_label(code: int) -> str:
    return RELATION_TYPE_LABELS.get(code, str(code))


def normalize_event_world_kind(raw: object) -> str:
    """v3.0 世界层；非法或缺省为 real。"""
    s = str(raw or "").strip().lower()
    if s in ("real", "fictional", "hypothetical", "unknown"):
        return s
    return "real"


def normalize_event_temporal_kind(raw: object) -> str:
    """v3.0 时间层；非法或缺省为 past（与旧叙事兼容）。"""
    s = str(raw or "").strip().lower()
    if s in ("past", "present", "future_planned", "future_uncertain", "atemporal"):
        return s
    return "past"


def normalize_planned_window_dict(raw: object) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    return {}


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
    tier: str = "important"
    identity_target: str = ""
    merge_hint: str = ""


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
    source_session_id: str = ""
    subject_actors: list[str] = field(default_factory=list)
    object_actors: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    assertion: str = "actual"
    world_kind: str = "real"
    temporal_kind: str = "past"
    planned_window: dict = field(default_factory=dict)


@dataclass
class PendingIdentityMerge:
    """永驻事实待合并队列（不直接写 USER/SOUL/MEMORY.md）。"""

    id: str
    created_at: str
    identity_target: str
    key: str
    value: str
    summary: str
    merge_hint: str
    confidence: float
    tags: list[str]
    source_session_id: str = ""


@dataclass
class EventRelation:
    id: str
    created_at: str
    event_a_id: str
    event_b_id: str
    relation_type: int
    explanation: str
    relation_legacy: str = ""


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

    def append_pending_identity(self, items: Iterable[PendingIdentityMerge]) -> int:
        path = self._root / "pending_identity.jsonl"
        count = 0
        with path.open("a", encoding="utf-8") as f:
            for item in items:
                data = asdict(item)
                f.write(json.dumps(data, ensure_ascii=False))
                f.write("\n")
                count += 1
        return count

    def read_recent_pending_identity(self, limit: int = 50) -> list[dict]:
        path = self._root / "pending_identity.jsonl"
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

    def find_pending_identity(self, pending_id: str) -> dict | None:
        pid = (pending_id or "").strip()
        if not pid:
            return None
        for e in self.read_recent_pending_identity(2000):
            if isinstance(e, dict) and e.get("id") == pid:
                return e
        return None

    def remove_pending_identity_if_exists(self, pending_id: str) -> bool:
        pid = (pending_id or "").strip()
        if not pid:
            return False
        path = self._root / "pending_identity.jsonl"
        if not path.is_file():
            return False
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        kept: list[str] = []
        removed = False
        for line in lines:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if isinstance(obj, dict) and obj.get("id") == pid:
                removed = True
            else:
                kept.append(line)
        if not removed:
            return False
        try:
            path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        except OSError:
            return False
        return True

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

    def read_recent_events_for_bootstrap(
        self,
        limit: int,
        *,
        exclude_world_kinds: frozenset[str],
    ) -> list[dict]:
        """冷启动：从 events.jsonl 尾部扫描，跳过指定 world_kind，凑满 limit 条（较新优先）。"""
        if not exclude_world_kinds:
            return self.read_recent("events", limit)
        path = self._path_for("events")
        if not path.is_file():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        lim = max(1, int(limit))
        tail_n = min(len(lines), max(lim * 15, 50), 500)
        segment = lines[-tail_n:]
        out: list[dict] = []
        for line in reversed(segment):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            wk = normalize_event_world_kind(obj.get("world_kind"))
            if wk in exclude_world_kinds:
                continue
            out.append(obj)
            if len(out) >= lim:
                break
        return out

    def read_recent_events_main_for_bootstrap(
        self,
        limit: int,
        *,
        exclude_world_kinds: frozenset[str],
        exclude_planned_temporal: bool,
    ) -> list[dict]:
        """冷启动主事件区；exclude_planned_temporal 为 True 时排除 future_planned / future_uncertain。"""
        path = self._path_for("events")
        if not path.is_file():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        lim = max(1, int(limit))
        tail_n = min(len(lines), max(lim * 15, 50), 500)
        segment = lines[-tail_n:]
        planned_t = frozenset({"future_planned", "future_uncertain"})
        out: list[dict] = []
        for line in reversed(segment):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            wk = normalize_event_world_kind(obj.get("world_kind"))
            if exclude_world_kinds and wk in exclude_world_kinds:
                continue
            tk = normalize_event_temporal_kind(obj.get("temporal_kind"))
            if exclude_planned_temporal and tk in planned_t:
                continue
            out.append(obj)
            if len(out) >= lim:
                break
        return out

    def read_recent_planned_events_for_bootstrap(
        self,
        limit: int,
        *,
        exclude_world_kinds: frozenset[str],
    ) -> list[dict]:
        """冷启动「近期计划」：仅 future_planned / future_uncertain，较新优先。"""
        if limit <= 0:
            return []
        path = self._path_for("events")
        if not path.is_file():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        lim = max(1, int(limit))
        tail_n = min(len(lines), max(lim * 20, 50), 500)
        segment = lines[-tail_n:]
        planned_t = frozenset({"future_planned", "future_uncertain"})
        out: list[dict] = []
        for line in reversed(segment):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            wk = normalize_event_world_kind(obj.get("world_kind"))
            if exclude_world_kinds and wk in exclude_world_kinds:
                continue
            tk = normalize_event_temporal_kind(obj.get("temporal_kind"))
            if tk not in planned_t:
                continue
            out.append(obj)
            if len(out) >= lim:
                break
        return out


def default_store() -> MemoryStore:
    return MemoryStore(None)


def new_fact_id() -> str:
    return f"fact_{int(datetime.now(timezone.utc).timestamp() * 1000)}"


def new_event_id() -> str:
    return f"event_{int(datetime.now(timezone.utc).timestamp() * 1000)}"


def new_relation_id() -> str:
    return f"rel_{int(datetime.now(timezone.utc).timestamp() * 1000)}"


def new_pending_identity_id() -> str:
    return f"pid_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

