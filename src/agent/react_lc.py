"""ReAct：LangChain create_agent + LangGraph（与 DeerFlow lead agent 同类模式），默认 Ollama。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError

from src.agent.memory_tools import (
    browse_memory_formatted,
    search_history as run_search_history,
    search_memory_keyword,
    search_memory_semantic as run_search_memory_semantic,
)
from src.agent.tools import (
    tool_list_dir,
    tool_read_file,
    tool_run_shell,
    tool_write_file,
)
from src.config import LLMConfig
from src.debug_log import (
    LangChainLlmSummaryHandler,
    ReactTraceToolCallbackHandler,
    is_llm_summary_enabled,
    is_react_trace_enabled,
)
from src.llm.chat_model import chat_model_from_config
from src.llm.prompts import SCHEDULED_TASK_REPLY_RULES, action_card_system_hint, build_system_block
from src.skills.loader import build_react_skills_block, get_registry

_LOG = logging.getLogger("ruyi72.react")


def _lc_callbacks(llm_cfg: LLMConfig, *, label: str) -> list[Any]:
    cbs: list[Any] = []
    if is_llm_summary_enabled(llm_cfg):
        cbs.append(LangChainLlmSummaryHandler(llm_cfg, label=label))
    if is_react_trace_enabled():
        cbs.append(ReactTraceToolCallbackHandler())
    return cbs


_SCHEDULER_BLOCK = """
内置定时任务（仅当工具列表中出现 save_session_scheduled_task 时可用）：
- save_session_scheduled_task：为「当前会话」创建或更新一条计划（存于会话目录 scheduled_tasks.json，与主对话历史独立）。触发时执行 noop 或向本会话追加 system 消息；会话 id 由系统固定，不可改。
  - trigger_type：interval_sec（需 interval_seconds，30～604800）或 daily_at（需 daily_time_hhmm，如 09:00）。
  - action_type：noop、append_system_message（message_text 必填）、call_llm_once（call_llm_user_prompt 必填）。
  - 可选 persist_output_to：messages / task_runs_log / both；missed_run_after_wake：catch_up_once 或 skip。
  - 可选 task_label：任务名称（便于用户在列表中识别）。
"""


_REACT_SYSTEM = """你是具备工具调用能力的智能体，必须在给定「工作区」目录下协助用户完成任务。
工作区绝对路径: {workspace}

你可以使用以下工具：
- read_file / list_dir / write_file / run_shell：在工作区内读文件、列目录、**写入或覆盖 UTF-8 文本**、执行命令。
- 创建多行脚本或小项目时**优先 write_file** 写入 `.py` 等文件，再 `run_shell` 运行；勿把大量代码塞进单行命令（Windows 命令行长度约限 8191 字符，会失败）。
- load_skill：按需加载某个技能的完整说明（来自 skills 目录的 SKILL.md）。
- browse_memory：浏览用户跨会话长期记忆中最近若干条（事实/事件/关系），只读本地存储，与工作区无关。
- search_memory：按关键词在记忆库中子串检索（非向量），用于查找与当前任务相关的历史记忆。可选 event_world_kinds / event_temporal_kinds（逗号分隔，仅过滤**事件**命中；留空表示该维度不过滤）。
- search_memory_semantic：对重要事实做向量语义检索（需配置开启 memory.vector_enabled 且 Ollama embedding 可用）。
- search_history：在已索引的会话消息中按关键词检索（需 memory.messages_index_enabled；可选传入 session_id 限定本会话）。

当前可用技能（仅元信息，不含实现细节）：

{skills_block}

风险等级说明：
- safe(0)：只读/查询/分析，默认 Ask 模式即可使用。
- act(1)：可能修改本地文件/状态，请谨慎使用。
- warn_act(2)：高危操作（磁盘/进程/服务/云/数据库/剪贴板等），必须先征得用户明确同意后再调用。

如需了解某个技能详情，请先调用 load_skill(name=技能名)，阅读返回的说明，再决定是否通过工具或脚本执行相关操作。
{scheduler_extra}
"""

_SCHEDULER_ASK_SAFE = """你是具备只读工具辅助的智能体。当前为定时任务安全模式：仅允许使用 safe(0) 级别能力——工作区内读文件与列目录、按名加载技能文档（可含网络检索等技能的说明与脚本指引）、浏览/检索跨会话记忆库；**未提供** run_shell，不得执行系统命令。

工作区绝对路径: {workspace}

工具说明：
- read_file / list_dir：在工作区内读文件、列目录。
- load_skill：按技能名加载 SKILL.md。
- browse_memory / search_memory / search_memory_semantic / search_history：浏览或检索记忆库；search_history 需开启消息索引。

技能元信息（不含全文）：

{skills_block}
"""


def _make_tools(
    workspace: str,
    scheduler_context: tuple[Any, str] | None = None,
    *,
    safe_only: bool = False,
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
    def write_file(path: str, content: str) -> str:
        """在工作区内创建或覆盖 UTF-8 文本文件。多行源码、小游戏等请用本工具写入 path，勿用过长单行 run_shell。"""
        return tool_write_file(ws, path, content)

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
    def search_memory(
        query: str,
        max_per_kind: int = 15,
        event_world_kinds: str = "",
        event_temporal_kinds: str = "",
    ) -> str:
        """按关键词检索记忆库；启用 sqlite/dual 且已迁移时用 FTS，否则 JSONL 子串匹配。max_per_kind 为每类上限。

        event_world_kinds：可选，逗号分隔，仅过滤事件。取值 real、fictional、hypothetical、unknown；留空表示不按世界层过滤。
        event_temporal_kinds：可选，逗号分隔，仅过滤事件。取值 past、present、future_planned、future_uncertain、atemporal；留空表示不按时间层过滤。
        """
        return search_memory_keyword(
            query,
            max_per_kind=max_per_kind,
            event_world_kinds=event_world_kinds,
            event_temporal_kinds=event_temporal_kinds,
        )

    @tool
    def search_memory_semantic(query: str, top_k: int = 8) -> str:
        """对重要事实向量索引做语义相似检索；top_k 为返回条数上限。"""
        return run_search_memory_semantic(query, top_k=top_k)

    @tool
    def search_history(query: str, session_id: str = "", limit: int = 15) -> str:
        """在已索引的对话历史中按关键词检索；session_id 为空则跨会话。需配置 memory.messages_index_enabled。"""
        return run_search_history(query, session_id=session_id, limit=limit)

    tools: list[Any] = [
        read_file,
        list_dir,
        write_file,
        run_shell,
        load_skill,
        browse_memory,
        search_memory,
        search_memory_semantic,
        search_history,
    ]
    if safe_only:
        tools = [
            read_file,
            list_dir,
            load_skill,
            browse_memory,
            search_memory,
            search_memory_semantic,
            search_history,
        ]
    elif scheduler_context is not None:
        svc, sid = scheduler_context

        @tool
        def save_session_scheduled_task(
            trigger_type: str,
            interval_seconds: int = 3600,
            daily_time_hhmm: str = "09:00",
            action_type: str = "noop",
            message_text: str = "",
            task_label: str = "",
            call_llm_system_prompt: str = "",
            call_llm_user_prompt: str = "",
            persist_output_to: str = "messages",
            missed_run_after_wake: str = "skip",
        ) -> str:
            """为当前会话创建或更新内置定时任务（noop、append_system_message、call_llm_once）。task_label 为可选任务名称。"""
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
                "label": (task_label or "").strip()[:200],
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
            elif act == "call_llm_once":
                u = (call_llm_user_prompt or "").strip()
                if not u:
                    return "action_type 为 call_llm_once 时 call_llm_user_prompt 不能为空。"
                payload["action"] = {
                    "type": "call_llm_once",
                    "system_prompt": (call_llm_system_prompt or "").strip(),
                    "user_prompt": u,
                }
            else:
                return (
                    "action_type 须为 noop、append_system_message 或 call_llm_once，"
                    f"收到: {action_type!r}"
                )

            # 延迟导入，避免 react_lc → scheduler → worker → conversation → react 循环依赖
            from src.scheduler import crud as scheduler_crud

            res = scheduler_crud.save_task(svc, payload)
            if res.get("ok"):
                t = res.get("task") or {}
                tid = t.get("id", "")
                return f"已保存定时任务 id={tid[:16]}… next_run_at={t.get('next_run_at')!r}"
            return "保存失败：" + str(res.get("error", "unknown"))

        tools.append(save_session_scheduled_task)

    return tools


def run_scheduler_safe_agent(
    llm_cfg: LLMConfig,
    *,
    workspace: str,
    user_prompt: str,
    extra_system: str = "",
    max_steps: int = 8,
) -> tuple[bool, str]:
    """
    内置定时任务安全模式：仅 SAFE 工具子集（无 run_shell、无会话定时任务工具）。
    返回 (成功, 展示文本/trace)。
    """
    if max_steps < 1:
        return False, "max_steps 无效。"
    llm = chat_model_from_config(llm_cfg)
    tools = _make_tools(workspace, None, safe_only=True)
    skills_block = build_react_skills_block()
    react_body = _SCHEDULER_ASK_SAFE.format(
        workspace=workspace,
        skills_block=skills_block or "（当前未发现任何技能定义）",
    )
    if (extra_system or "").strip():
        react_body = react_body + "\n\n【调度补充说明】\n" + extra_system.strip()
    react_body = react_body + "\n\n" + SCHEDULED_TASK_REPLY_RULES
    system_prompt = build_system_block(extra_system=react_body)

    agent = create_agent(
        llm,
        tools,
        system_prompt=system_prompt,
    )
    lc_in = _dicts_to_messages([{"role": "user", "content": user_prompt}])
    recursion_limit = max(12, min(200, max_steps * 3 + 6))
    invoke_cfg: dict[str, Any] = {"recursion_limit": recursion_limit}
    cbs = _lc_callbacks(llm_cfg, label="scheduler_safe_react")
    if cbs:
        invoke_cfg["callbacks"] = cbs
    try:
        result: dict[str, Any] = agent.invoke(
            {"messages": lc_in},
            config=invoke_cfg,
        )
    except GraphRecursionError as e:
        return False, f"已达到安全模式步数/递归上限（recursion_limit={recursion_limit}）。{e!s}"
    except Exception as e:
        return False, f"Agent 执行失败: {e!s}"

    raw_msgs = result.get("messages")
    if not isinstance(raw_msgs, list):
        return False, "Agent 返回中缺少 messages。"
    flat = _messages_to_dicts(raw_msgs)
    flat = [m for m in flat if m.get("role") != "system"]
    trace = _display_trace(flat)
    return True, trace or "(已完成，无文本摘要)"


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


def _safe_stream_emit(
    fn: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]
) -> None:
    if fn is None:
        return
    try:
        fn(payload)
    except Exception:
        pass


def _state_sig(state: dict[str, Any]) -> tuple[Any, ...]:
    msgs = state.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return (0, "")
    last = msgs[-1]
    tid = getattr(last, "id", None) or ""
    return (len(msgs), type(last).__name__, str(tid))


def _line_from_agent_state(state: dict[str, Any]) -> str | None:
    msgs = state.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return None
    last = msgs[-1]
    if isinstance(last, AIMessage):
        tcs = getattr(last, "tool_calls", None) or []
        if tcs:
            names: list[str] = []
            for tc in tcs:
                if isinstance(tc, dict):
                    n = tc.get("name") or ""
                else:
                    n = getattr(tc, "name", "") or ""
                if n:
                    names.append(str(n))
            if names:
                return "调用工具: " + ", ".join(names)
            return "模型请求工具调用…"
        content = getattr(last, "content", "") or ""
        c = str(content)
        if len(c) > 100:
            return "模型输出（片段）: " + c[:100].replace("\n", " ") + "…"
        return "模型已回复" if c.strip() else "模型轮次…"
    if isinstance(last, ToolMessage):
        name = getattr(last, "name", "") or "tool"
        c = str(getattr(last, "content", "") or "")
        one = c.replace("\n", " ")[:160]
        suf = "…" if len(c) > 160 else ""
        return f"工具 [{name}] 完成: {one}{suf}"
    if isinstance(last, HumanMessage):
        return "用户/工具输入（步骤推进）"
    return f"步骤推进（共 {len(msgs)} 条消息）"


def run_react(
    llm_cfg: LLMConfig,
    messages: list[dict[str, Any]],
    *,
    workspace: str,
    max_steps: int,
    memory_bootstrap: str | None = None,
    extra_system: str | None = None,
    scheduler_context: tuple[Any, str] | None = None,
    stream_emit: Callable[[dict[str, Any]], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    step_progress: Callable[[int], None] | None = None,
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
    invoke_cfg: dict[str, Any] = {"recursion_limit": recursion_limit}
    cbs = _lc_callbacks(llm_cfg, label="react")
    if cbs:
        invoke_cfg["callbacks"] = cbs

    inp: dict[str, Any] = {"messages": lc_in}
    t_wall = time.perf_counter()
    ws_short = workspace if len(workspace) <= 120 else workspace[:117] + "…"
    use_stream_loop = stream_emit is not None or cancel_check is not None
    _LOG.info(
        "[ReAct] start workspace=%s max_steps=%s recursion_limit=%s stream=%s",
        ws_short,
        max_steps,
        recursion_limit,
        use_stream_loop,
    )

    result: dict[str, Any] = {}
    interrupted = False
    try:
        if use_stream_loop:
            _safe_stream_emit(
                stream_emit,
                {"type": "react.start", "recursion_limit": recursion_limit},
            )
            last_state: dict[str, Any] | None = None
            last_sig: tuple[Any, ...] | None = None
            react_step_i = 0
            for state in agent.stream(inp, config=invoke_cfg, stream_mode="values"):
                if isinstance(state, dict):
                    last_state = state
                    sig = _state_sig(state)
                    if sig != last_sig:
                        last_sig = sig
                        react_step_i += 1
                        if step_progress:
                            try:
                                step_progress(react_step_i)
                            except Exception:
                                pass
                        line = _line_from_agent_state(state)
                        if line and stream_emit:
                            _safe_stream_emit(
                                stream_emit, {"type": "react.progress", "line": line}
                            )
                if cancel_check and cancel_check():
                    interrupted = True
                    break
            result = last_state if last_state is not None else {}
        else:
            if step_progress:
                try:
                    step_progress(1)
                except Exception:
                    pass
            result = agent.invoke(inp, config=invoke_cfg)
    except GraphRecursionError as e:
        ms = (time.perf_counter() - t_wall) * 1000.0
        _LOG.info("[ReAct] done ok=False ms=%.0f err=recursion_limit", ms)
        _safe_stream_emit(
            stream_emit,
            {
                "type": "react.done",
                "ok": False,
                "elapsed_ms": round(ms),
                "error": "recursion_limit",
            },
        )
        return False, f"已达到 ReAct 步数/递归上限（recursion_limit={recursion_limit}）。{e!s}"
    except Exception as e:
        ms = (time.perf_counter() - t_wall) * 1000.0
        _LOG.info("[ReAct] done ok=False ms=%.0f err=%s", ms, str(e)[:300])
        _safe_stream_emit(
            stream_emit,
            {
                "type": "react.done",
                "ok": False,
                "elapsed_ms": round(ms),
                "error": str(e)[:500],
            },
        )
        return False, f"Agent 执行失败: {e!s}"

    if interrupted:
        ms_i = (time.perf_counter() - t_wall) * 1000.0
        _LOG.info("[ReAct] done ok=False ms=%.0f err=interrupted", ms_i)
        _safe_stream_emit(
            stream_emit,
            {
                "type": "react.done",
                "ok": False,
                "elapsed_ms": round(ms_i),
                "error": "interrupted",
            },
        )
        raw_i = result.get("messages")
        if isinstance(raw_i, list):
            flat_i = _messages_to_dicts(raw_i)
            flat_i = [m for m in flat_i if m.get("role") != "system"]
            messages.clear()
            messages.extend(flat_i)
            trace_i = _display_trace(flat_i)
            return False, trace_i or "【已中断】"
        return False, "【已中断】"

    raw_msgs = result.get("messages")
    if not isinstance(raw_msgs, list):
        ms = (time.perf_counter() - t_wall) * 1000.0
        _LOG.info("[ReAct] done ok=False ms=%.0f err=missing_messages", ms)
        _safe_stream_emit(
            stream_emit,
            {
                "type": "react.done",
                "ok": False,
                "elapsed_ms": round(ms),
                "error": "missing_messages",
            },
        )
        return False, "Agent 返回中缺少 messages。"

    flat = _messages_to_dicts(raw_msgs)
    flat = [m for m in flat if m.get("role") != "system"]

    messages.clear()
    messages.extend(flat)

    ms = (time.perf_counter() - t_wall) * 1000.0
    _LOG.info("[ReAct] done ok=True ms=%.0f", ms)
    _safe_stream_emit(
        stream_emit,
        {"type": "react.done", "ok": True, "elapsed_ms": round(ms)},
    )

    trace = _display_trace(flat)
    return True, trace or "(已完成，无文本摘要)"
