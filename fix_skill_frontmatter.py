from __future__ import annotations

from pathlib import Path

import yaml


def infer_from_body(path: Path, body_lines: list[str]) -> tuple[str, str]:
    name = None
    desc = None
    for i, line in enumerate(body_lines):
        stripped = line.lstrip("#").strip()
        if line.lstrip().startswith("#") and stripped:
            name = stripped
            # description: 下一行起第一条非空且不是标题的文本
            for j in range(i + 1, len(body_lines)):
                s = body_lines[j].strip()
                if not s:
                    continue
                if s.startswith("#"):
                    break
                desc = s
                break
            break
    if name is None:
        name = path.parent.name
    if desc is None:
        desc = f"Skill {name}"
    return name, desc


def process_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines:
        return

    # 已有 front-matter 的情况
    if lines[0].startswith("---"):
        try:
            end_idx = next(
                i for i, l in enumerate(lines[1:], start=1) if l.startswith("---")
            )
        except StopIteration:
            # 只有一个 ---，当作没有 front-matter
            body = lines
            name, desc = infer_from_body(path, [l.rstrip("\n") for l in body])
            header = [
                "---\n",
                f"name: {name}\n",
                f"description: {desc}\n",
                "---\n",
            ]
            path.write_text("".join(header + body), encoding="utf-8")
            return

        header_lines = lines[1:end_idx]
        body = lines[end_idx + 1 :]
        header_text = "".join(header_lines)

        try:
            data = yaml.safe_load(header_text) or {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}

        need_name = not data.get("name")
        need_desc = not data.get("description")

        if not (need_name or need_desc):
            # 已经有 name 和 description，跳过
            return

        name, desc = infer_from_body(path, [l.rstrip("\n") for l in body])
        if need_name:
            data["name"] = name
        if need_desc:
            data["description"] = desc

        new_header = (
            "---\n"
            + yaml.safe_dump(data, allow_unicode=True, sort_keys=False).rstrip()
            + "\n---\n"
        )
        path.write_text(new_header + "".join(body), encoding="utf-8")
        return

    # 没有 front-matter 的情况：新增
    body = lines
    name, desc = infer_from_body(path, [l.rstrip("\n") for l in body])
    header = [
        "---\n",
        f"name: {name}\n",
        f"description: {desc}\n",
        "---\n",
    ]
    path.write_text("".join(header + body), encoding="utf-8")


def main() -> None:
    root = Path("skills")
    for p in root.rglob("SKILL.md"):
        process_file(p)


if __name__ == "__main__":
    main()

