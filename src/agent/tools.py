"""在工作区内执行的 ReAct 工具（路径限制在工作区根目录下）。"""

from __future__ import annotations

import locale
import subprocess
import sys
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


def _decode_shell_bytes(data: bytes) -> str:
    """Windows cmd 多为 GBK/系统 ANSI；与 UTF-8 误配会产生乱码，故按序尝试多种解码。"""
    if not data:
        return ""
    if data.startswith(b"\xef\xbb\xbf"):
        try:
            return data[3:].decode("utf-8")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    le = locale.getpreferredencoding(False)
    if le:
        try:
            return data.decode(le, errors="replace")
        except (LookupError, UnicodeDecodeError):
            pass
    return data.decode("utf-8", errors="replace")


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
        # Windows: 通过 cmd 执行；cwd 固定在工作区。捕获字节再解码，避免 GBK  stderr 变乱码。
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            shell=True,
            capture_output=True,
            timeout=120,
        )
        stdout = _decode_shell_bytes(proc.stdout or b"")
        stderr = _decode_shell_bytes(proc.stderr or b"")
        out: list[str] = []
        if stdout:
            out.append(stdout)
        if stderr:
            out.append("[stderr]\n" + stderr)
        body = "\n".join(out).strip() or "(无输出)"
        if len(body) > 80_000:
            body = body[:80_000] + "\n…(已截断)"
        tail = f"\n[exit_code={proc.returncode}]"
        hint = ""
        if proc.returncode != 0 and sys.platform == "win32":
            if len(cmd) > 7800:
                hint = (
                    "\n[提示] Windows 单行命令长度约限 8191 字符；"
                    "请勿把大段源码塞进 python -c 或 echo。"
                    "应改用：在工作区用 list_dir 确认路径后，"
                    "分多步 write（若可用）或把脚本写入短路径文件再 python 文件名.py。"
                )
            elif any(
                x in (stderr + stdout)
                for x in ("命令行太长", "命令语法不正确", "The command line is too long")
            ):
                hint = (
                    "\n[提示] 疑似命令行过长或 cmd 语法问题；"
                    "长代码请写入 .py 文件（多行 heredoc 或编辑器）再执行，勿单行塞入。"
                )
        return body + tail + hint
    except subprocess.TimeoutExpired:
        return "错误: 命令超时（120s）"
    except OSError as e:
        return f"错误: 执行失败 {e!s}"


def tool_write_file(workspace: str, path: str, content: str) -> str:
    """在工作区内创建或覆盖 UTF-8 文本文件（多行代码请用本工具，勿塞进单行 run_shell）。"""
    root = _workspace_root(workspace)
    if not root.is_dir():
        return f"错误: 工作区不存在或不是目录: {root}"
    target = safe_child(root, path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return f"错误: 无法创建父目录 {e!s}"
    text = content if content is not None else ""
    if len(text) > 2_000_000:
        return "错误: 内容过长（>2MB）"
    try:
        target.write_text(text, encoding="utf-8", newline="\n")
    except OSError as e:
        return f"错误: 写入失败 {e!s}"
    return f"已写入: {path}（{len(text)} 字符）"


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
    if a in ("write_file", "write"):
        p = str(args.get("path", ""))
        c = args.get("content", "")
        if isinstance(c, str):
            body = c
        else:
            body = str(c) if c is not None else ""
        return tool_write_file(workspace, p, body)
    if a in ("run_shell", "shell", "bash", "cmd"):
        c = str(args.get("command", ""))
        return tool_run_shell(workspace, c)
    return f"错误: 未知 action: {action}"

