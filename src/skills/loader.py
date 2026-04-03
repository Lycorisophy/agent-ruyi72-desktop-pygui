from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml


@dataclass(frozen=True)
class SkillMeta:
    id: str           # 例如 "safe/deep-research"
    name: str
    description: str
    level: int        # 0 = safe, 1 = act, 2 = warn_act
    path: Path        # SKILL.md 绝对路径
    extra: dict       # 头部其它字段


class SkillRegistry:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._skills: list[SkillMeta] = []
        self._by_name: dict[str, SkillMeta] = {}
        self._load()

    @property
    def skills(self) -> list[SkillMeta]:
        return list(self._skills)

    def list_by_levels(self, levels: Iterable[int]) -> list[SkillMeta]:
        level_set = set(levels)
        return [s for s in self._skills if s.level in level_set]

    def get_by_name(self, name: str) -> SkillMeta | None:
        return self._by_name.get(name.strip())

    def read_full(self, skill: SkillMeta) -> str:
        return skill.path.read_text(encoding="utf-8")

    def _load(self) -> None:
        root = self._root
        if not root.is_dir():
            return

        def iter_paths() -> list[tuple[Path, int]]:
            items: list[tuple[Path, int]] = []
            for level, sub in ((0, "safe"), (1, "act"), (2, "warn_act")):
                base = root / sub
                if not base.is_dir():
                    continue
                for p in base.rglob("SKILL.md"):
                    items.append((p, level))
            return items

        for path, level in iter_paths():
            rel = path.relative_to(root)
            # 例如 safe/deep-research/SKILL.md -> safe/deep-research
            skill_id = str(rel.with_suffix("")).rsplit("/", 1)[0].replace("\\", "/")

            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            meta_dict: dict = {}
            body_lines: list[str] = []
            if lines and lines[0].startswith("---"):
                try:
                    end_idx = next(i for i, l in enumerate(lines[1:], start=1) if l.startswith("---"))
                except StopIteration:
                    header_text = ""
                    body_lines = lines
                else:
                    header_text = "\n".join(lines[1:end_idx])
                    body_lines = lines[end_idx + 1 :]
                if header_text:
                    try:
                        loaded = yaml.safe_load(header_text) or {}
                    except Exception:
                        loaded = {}
                    if isinstance(loaded, dict):
                        meta_dict = loaded
            else:
                body_lines = lines

            name = str(meta_dict.get("name") or "").strip()
            desc = str(meta_dict.get("description") or "").strip()

            if not name:
                # 退化：用目录名
                name = path.parent.name
            if not desc:
                # 从正文首行取一句
                for line in body_lines:
                    s = line.lstrip("#").strip()
                    if not s:
                        continue
                    if s.startswith("#"):
                        continue
                    desc = s
                    break
                if not desc:
                    desc = f"Skill {name}"

            extra = {k: v for k, v in meta_dict.items() if k not in ("name", "description")}

            meta = SkillMeta(
                id=skill_id,
                name=name,
                description=desc,
                level=level,
                path=path.resolve(),
                extra=extra,
            )
            self._skills.append(meta)
            # name 可能重复，此时保留第一个
            self._by_name.setdefault(name, meta)

        # 按 level, name 排序，便于展示
        self._skills.sort(key=lambda s: (s.level, s.name.lower()))


@lru_cache(maxsize=1)
def get_registry() -> SkillRegistry:
    # 根目录 skills/ 相对项目根（app.py 所在目录）
    root = Path(__file__).resolve().parents[2] / "skills"
    return SkillRegistry(root)


def build_safe_skills_prompt() -> str:
    """为对话模式构建仅包含 safe 技能的提示文案。"""
    reg = get_registry()
    safe_skills = reg.list_by_levels({0})
    if not safe_skills:
        return ""

    lines: list[str] = []
    lines.append("你可以在需要时参考以下“安全技能”（level=0）。这里只提供概要，如果你需要某个技能的详细说明，请明确说出技能名称。")
    lines.append("")
    for s in safe_skills:
        lines.append(f"- {s.name}：{s.description}")
    return "\n".join(lines)


def build_react_skills_block() -> str:
    """为 ReAct system prompt 构建包含全部技能 + 等级的文本块。"""
    reg = get_registry()
    skills = reg.skills
    if not skills:
        return ""

    by_level: dict[int, list[SkillMeta]] = {0: [], 1: [], 2: []}
    for s in skills:
        by_level.setdefault(s.level, []).append(s)

    labels = {
        0: "safe(0) — 只读/查询/分析，默认 Ask 模式可用",
        1: "act(1) — 可能修改本地文件/状态，需要谨慎",
        2: "warn_act(2) — 高危操作（磁盘/进程/服务/云/数据库/剪贴板等），每次需用户确认",
    }

    lines: list[str] = []
    for level in (0, 1, 2):
        group = by_level.get(level) or []
        if not group:
            continue
        lines.append(f"[{labels.get(level, str(level))}]")
        for s in group:
            lines.append(f"- {s.name}：{s.description}")
        lines.append("")
    return "\n".join(lines).rstrip()

