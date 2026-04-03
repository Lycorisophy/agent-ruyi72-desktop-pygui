"""ReAct：LangChain create_agent + LangGraph（与 DeerFlow lead agent 同类模式），默认 Ollama。"""

from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError

from src.agent.tools import tool_list_dir, tool_read_file, tool_run_shell
from src.config import LLMConfig
from src.llm.chat_model import chat_model_from_config


_REACT_SYSTEM = """你是具备工具调用能力的智能体，必须在给定「工作区」目录下协助用户完成任务。
工作区绝对路径: {workspace}

规则：
- 仅使用提供的工具访问文件与执行命令；路径均为相对工作区的相对路径（如 "."、"src/foo.txt"）。
- run_shell 在 Windows 上执行，请注意安全；长命令可能超时。
- 先观察再行动；能直接回答时可直接回复用户，不必强行调用工具。
"""


def _make_tools(workspace: str):
    ws = workspace

    @tool
    def read_file(path: str) -> str:
        """读取工作区内 UTF-8 文本文件。path 为相对工作区的路径。"""
        return tool_read_file(ws, path)

    @tool
    def list_dir(path: str = ".") -> str:
        """列出工作区内目录内容。path 为相对工作区的目录，默认当前目录。"""
        return tool_list_dir(ws, path)

    @tool
    def run_shell(command: str) -> str:
        """在工作区根目录下执行一条 shell 命令。"""
        return tool_run_shell(ws, command)

    return [read_file, list_dir, run_shell]


def _dicts_to_messages(msgs: list[dict[str, str]]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in msgs:
        role = m.get("role", "user")
        content = str(m.get("content", ""))
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        elif role == "system":
            out.append(SystemMessage(content=content))
    return out


def _messages_to_dicts(msgs: list[BaseMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in msgs:
        if isinstance(m, HumanMessage):
            out.append({"role": "user", "content": str(m.content)})
        elif isinstance(m, AIMessage):
            text = str(m.content) if m.content else ""
            if m.tool_calls:
                tc_ser: list[dict[str, Any]] = []
                for tc in m.tool_calls:
                    if isinstance(tc, dict):
                        tc_ser.append(
                            {
                                "name": tc.get("name", ""),
                                "args": tc.get("args") or tc.get("arguments") or {},
                            }
                        )
                    else:
                        tc_ser.append({"name": getattr(tc, "name", ""), "args": getattr(tc, "args", {})})
                text = (
                    text + "\n[tool_calls] " + json.dumps(tc_ser, ensure_ascii=False)
                ).strip()
            out.append({"role": "assistant", "content": text})
        elif isinstance(m, ToolMessage):
            name = getattr(m, "name", "") or "tool"
            out.append({"role": "user", "content": f"[工具 {name}]\n{m.content}"})
        elif isinstance(m, SystemMessage):
            out.append({"role": "system", "content": str(m.content)})
    return out


def _display_trace(msgs: list[dict[str, str]]) -> str:
    if not msgs:
        return ""
    tail = msgs[-8:] if len(msgs) > 8 else msgs
    parts: list[str] = []
    for m in tail:
        parts.append(f"【{m['role']}】\n{m.get('content', '')}")
    return "\n\n".join(parts)


def run_react(
    llm_cfg: LLMConfig,
    messages: list[dict[str, str]],
    *,
    workspace: str,
    max_steps: int,
) -> tuple[bool, str]:
    """
    使用 LangChain create_agent（底层为 LangGraph）执行工具循环。
    成功时更新 messages 为可持久化的扁平记录，并返回 (True, 展示文本)。
    """
    if max_steps < 1:
        return False, "react_max_steps 无效。"

    llm = chat_model_from_config(llm_cfg)
    tools = _make_tools(workspace)
    system_prompt = _REACT_SYSTEM.format(workspace=workspace)

    agent = create_agent(
        llm,
        tools,
        system_prompt=system_prompt,
    )

    lc_in = _dicts_to_messages(messages)
    recursion_limit = max(12, min(200, max_steps * 3 + 6))

    try:
        result: dict[str, Any] = agent.invoke(
            {"messages": lc_in},
            config={"recursion_limit": recursion_limit},
        )
    except GraphRecursionError as e:
        return False, f"已达到 ReAct 步数/递归上限（recursion_limit={recursion_limit}）。{e!s}"
    except Exception as e:
        return False, f"Agent 执行失败: {e!s}"

    raw_msgs = result.get("messages")
    if not isinstance(raw_msgs, list):
        return False, "Agent 返回中缺少 messages。"

    flat = _messages_to_dicts(raw_msgs)
    flat = [m for m in flat if m.get("role") != "system"]

    messages.clear()
    messages.extend(flat)

    trace = _display_trace(flat)
    return True, trace or "(已完成，无文本摘要)"
