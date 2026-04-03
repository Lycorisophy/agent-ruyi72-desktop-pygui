"""在工作区内执行的 ReAct 工具（路径限制在工作区根目录下）。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class ToolError(Exception):
    """可展示给模型与用户的工具错误。"""


def _workspace_root(workspace: str) -> Path:
    p = Path(workspace).expanduser()
    if not p.is_absolute():
        p = p.resolve()
    return p


def safe_child(root: Path, relative: str) -> Path:
    rel = (relative or ".").replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise ToolError("禁止在路径中使用 ..")
    child = (root / rel).resolve()
    root_r = root.resolve()
    try:
        child.relative_to(root_r)
    except ValueError as e:
        raise ToolError("路径超出工作区范围") from e
    return child


def tool_read_file(workspace: str, path: str) -> str:
    root = _workspace_root(workspace)
    if not root.is_dir():
        return f"错误: 工作区不存在或不是目录: {root}"
    target = safe_child(root, path)
    if not target.is_file():
        return f"错误: 不是文件或不存在: {path}"
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > 120_000:
            return text[:120_000] + "\n…(已截断)"
        return text
    except OSError as e:
        return f"错误: 读取失败 {e!s}"


def tool_list_dir(workspace: str, path: str = ".") -> str:
    root = _workspace_root(workspace)
    if not root.is_dir():
        return f"错误: 工作区不存在或不是目录: {root}"
    target = safe_child(root, path)
    if not target.is_dir():
        return f"错误: 不是目录或不存在: {path}"
    try:
        lines: list[str] = []
        for c in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            kind = "dir" if c.is_dir() else "file"
            lines.append(f"[{kind}] {c.name}")
        return "\n".join(lines) if lines else "(空目录)"
    except OSError as e:
        return f"错误: 列出失败 {e!s}"


def tool_run_shell(workspace: str, command: str) -> str:
    root = _workspace_root(workspace)
    if not root.is_dir():
        return f"错误: 工作区不存在或不是目录: {root}"
    cmd = (command or "").strip()
    if not cmd:
        return "错误: 命令为空"
    try:
        # Windows: 通过 cmd 执行一行命令；cwd 固定在工作区
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        out: list[str] = []
        if proc.stdout:
            out.append(proc.stdout)
        if proc.stderr:
            out.append("[stderr]\n" + proc.stderr)
        body = "\n".join(out).strip() or "(无输出)"
        if len(body) > 80_000:
            body = body[:80_000] + "\n…(已截断)"
        tail = f"\n[exit_code={proc.returncode}]"
        return body + tail
    except subprocess.TimeoutExpired:
        return "错误: 命令超时（120s）"
    except OSError as e:
        return f"错误: 执行失败 {e!s}"


def dispatch_tool(workspace: str, action: str, args: dict[str, Any]) -> str:
    a = (action or "").strip().lower()
    if a in ("finish", "done"):
        return ""
    if a == "read_file":
        p = str(args.get("path", "."))
        return tool_read_file(workspace, p)
    if a in ("list_dir", "listdir"):
        p = str(args.get("path", "."))
        return tool_list_dir(workspace, p)
    if a in ("run_shell", "shell", "bash", "cmd"):
        c = str(args.get("command", ""))
        return tool_run_shell(workspace, c)
    return f"错误: 未知 action: {action}"

