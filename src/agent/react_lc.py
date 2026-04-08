"""ReAct：LangChain create_agent + LangGraph（与 DeerFlow lead agent 同类模式），默认 Ollama。"""

from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError

from src.agent.memory_tools import browse_memory_formatted, search_memory_keyword
from src.agent.tools import tool_list_dir, tool_read_file, tool_run_shell
from src.config import LLMConfig
from src.llm.chat_model import chat_model_from_config
from src.llm.prompts import action_card_system_hint, build_system_block
from src.scheduler import crud as scheduler_crud
from src.skills.loader import build_react_skills_block, get_registry


_SCHEDULER_BLOCK = """
内置定时任务（仅当工具列表中出现 save_session_scheduled_task 时可用）：
- save_session_scheduled_task：为「当前会话」创建或更新一条计划（存于会话目录 scheduled_tasks.json，与主对话历史独立）。触发时执行 noop 或向本会话追加 system 消息；会话 id 由系统固定，不可改。
  - trigger_type：interval_sec（需 interval_seconds，30～604800）或 daily_at（需 daily_time_hhmm，如 09:00）。
  - action_type：noop，或 append_system_message（此时 message_text 必填）。
  - 可选 persist_output_to：messages / task_runs_log / both；missed_run_after_wake：catch_up_once 或 skip。
"""


_REACT_SYSTEM = """你是具备工具调用能力的智能体，必须在给定「工作区」目录下协助用户完成任务。
工作区绝对路径: {workspace}

你可以使用以下工具：
- read_file / list_dir / run_shell：在工作区内读文件、列目录、执行命令。
- load_skill：按需加载某个技能的完整说明（来自 skills 目录的 SKILL.md）。
- browse_memory：浏览用户跨会话长期记忆中最近若干条（事实/事件/关系），只读本地存储，与工作区无关。
- search_memory：按关键词在记忆库中子串检索（非向量），用于查找与当前任务相关的历史记忆。

当前可用技能（仅元信息，不含实现细节）：

{skills_block}

风险等级说明：
- safe(0)：只读/查询/分析，默认 Ask 模式即可使用。
- act(1)：可能修改本地文件/状态，请谨慎使用。
- warn_act(2)：高危操作（磁盘/进程/服务/云/数据库/剪贴板等），必须先征得用户明确同意后再调用。

如需了解某个技能详情，请先调用 load_skill(name=技能名)，阅读返回的说明，再决定是否通过工具或脚本执行相关操作。
{scheduler_extra}
"""


def _make_tools(
    workspace: str,
    scheduler_context: tuple[Any, str] | None = None,
):
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

    @tool
    def load_skill(name: str) -> str:
        """按技能名加载 SKILL.md 全文；warn_act(2) 技能会提示需用户确认后再使用。"""
        reg = get_registry()
        meta = reg.get_by_name(name)
        if meta is None:
            return f"未找到名为 {name!r} 的技能。请检查技能 name 是否与 SKILL.md 头部一致。"

        if meta.level >= 2:
            return (
                f"技能 {meta.name} 属于 warn_act(2) 高危技能：可能涉及磁盘/进程/服务/云盘/数据库/剪贴板等敏感操作。\n"
                f"在调用该技能相关脚本或命令前，必须先征得用户的明确同意，例如：\"我确认使用 {meta.name} 技能\"。\n\n"
                f"以下为技能文档供你审阅：\n\n{reg.read_full(meta)}"
            )

        # safe / act 直接返回文档
        return reg.read_full(meta)

    @tool
    def browse_memory(limit: int = 10) -> str:
        """浏览跨会话记忆中各类最近若干条（事实、事件、关系）。limit 为每类最多条数。"""
        return browse_memory_formatted(limit)

    @tool
    def search_memory(query: str, max_per_kind: int = 15) -> str:
        """在记忆库 JSONL 中按关键词做子串匹配；max_per_kind 为每类最多返回条数。"""
        return search_memory_keyword(query, max_per_kind=max_per_kind)

    tools: list[Any] = [read_file, list_dir, run_shell, load_skill, browse_memory, search_memory]

    if scheduler_context is not None:
        svc, sid = scheduler_context

        @tool
        def save_session_scheduled_task(
            trigger_type: str,
            interval_seconds: int = 3600,
            daily_time_hhmm: str = "09:00",
            action_type: str = "noop",
            message_text: str = "",
            persist_output_to: str = "messages",
            missed_run_after_wake: str = "skip",
        ) -> str:
            """为当前会话创建或更新内置定时任务（noop 或定时追加 system 消息）。"""
            tt = (trigger_type or "").strip().lower()
            act = (action_type or "").strip().lower()
            pot = (persist_output_to or "messages").strip().lower()
            mr = (missed_run_after_wake or "skip").strip().lower()
            if pot not in ("messages", "task_runs_log", "both"):
                return f"persist_output_to 无效: {persist_output_to!r}"
            if mr not in ("catch_up_once", "skip"):
                return f"missed_run_after_wake 无效: {missed_run_after_wake!r}"

            payload: dict[str, Any] = {
                "kind": "session",
                "session_id": sid,
                "enabled": True,
                "run_when_session_inactive": True,
                "persist_output_to": pot,
                "missed_run_after_wake": mr,
            }
            if tt == "interval_sec":
                sec = int(interval_seconds)
                sec = max(30, min(sec, 86400 * 7))
                payload["trigger"] = {"type": "interval_sec", "value": sec}
            elif tt == "daily_at":
                hh = (daily_time_hhmm or "09:00").strip()
                payload["trigger"] = {"type": "daily_at", "value": hh}
            else:
                return (
                    "trigger_type 须为 interval_sec 或 daily_at，"
                    f"收到: {trigger_type!r}"
                )

            if act == "noop":
                payload["action"] = {"type": "noop"}
            elif act == "append_system_message":
                text = (message_text or "").strip()
                if not text:
                    return "action_type 为 append_system_message 时 message_text 不能为空。"
                payload["action"] = {"type": "append_system_message", "text": text}
            else:
                return f"action_type 须为 noop 或 append_system_message，收到: {action_type!r}"

            res = scheduler_crud.save_task(svc, payload)
            if res.get("ok"):
                t = res.get("task") or {}
                tid = t.get("id", "")
                return f"已保存定时任务 id={tid[:16]}… next_run_at={t.get('next_run_at')!r}"
            return "保存失败：" + str(res.get("error", "unknown"))

        tools.append(save_session_scheduled_task)

    return tools


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
    messages: list[dict[str, Any]],
    *,
    workspace: str,
    max_steps: int,
    memory_bootstrap: str | None = None,
    extra_system: str | None = None,
    scheduler_context: tuple[Any, str] | None = None,
) -> tuple[bool, str]:
    """
    使用 LangChain create_agent（底层为 LangGraph）执行工具循环。
    成功时更新 messages 为可持久化的扁平记录，并返回 (True, 展示文本)。
    """
    if max_steps < 1:
        return False, "react_max_steps 无效。"

    llm = chat_model_from_config(llm_cfg)
    tools = _make_tools(workspace, scheduler_context)
    skills_block = build_react_skills_block()
    sched_extra = _SCHEDULER_BLOCK if scheduler_context else ""
    react_system = _REACT_SYSTEM.format(
        workspace=workspace,
        skills_block=skills_block or "（当前未发现任何技能定义）",
        scheduler_extra=sched_extra,
    )
    system_prompt = build_system_block(extra_system=react_system)
    if memory_bootstrap:
        system_prompt = system_prompt + "\n\n" + memory_bootstrap
    if extra_system:
        system_prompt = system_prompt + "\n\n" + extra_system.strip()
    system_prompt = system_prompt + "\n\n" + action_card_system_hint()

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
