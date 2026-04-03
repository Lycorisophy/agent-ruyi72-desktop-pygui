"""ReAct：思考—行动—观察循环，直到 finish 或达到步数上限。"""

from __future__ import annotations

import json
import re
from typing import Any

from src.agent.tools import ToolError, dispatch_tool
from src.config import LLMConfig
from src.llm.ollama import OllamaClient, OllamaClientError


_REACT_SYSTEM = """你是 ReAct 智能体，必须在「工作区」目录下完成任务。
工作区绝对路径: {workspace}

每一步必须用**一个 JSON 对象**回复（不要 markdown 代码围栏），仅使用下列 action 之一：
1) {{"thought":"用中文简述推理","action":"read_file","args":{{"path":"相对工作区的路径"}}}}
2) {{"thought":"...","action":"list_dir","args":{{"path":"."}}}}
3) {{"thought":"...","action":"run_shell","args":{{"command":"单条 shell 命令"}}}}
4) {{"thought":"...","action":"finish","args":{{"answer":"给用户的最终自然语言回答"}}}}

要求：
- path 相对于工作区；首次可先 list_dir 了解结构。
- run_shell 在 Windows 上可用，请注意命令安全；长耗时命令可能超时。
- 若已能直接回答用户，优先使用 action=finish。
"""


def _extract_json_object(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    if not t:
        raise ValueError("空响应")
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if fence:
        t = fence.group(1).strip()
    try:
        data = json.loads(t)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        chunk = t[start : end + 1]
        data = json.loads(chunk)
        if isinstance(data, dict):
            return data
    raise ValueError(f"无法解析 JSON: {t[:400]}")


def run_react(
    llm_cfg: LLMConfig,
    messages: list[dict[str, str]],
    *,
    workspace: str,
    max_steps: int,
) -> tuple[bool, str]:
    """
    在 messages 末尾应已包含最新用户消息。会追加多轮 assistant/user（观察），或最终 assistant。
    返回 (ok, 展示文本)。
    """
    if max_steps < 1:
        return False, "react_max_steps 无效。"

    client = OllamaClient(llm_cfg)
    sys_text = _REACT_SYSTEM.format(workspace=workspace)
    trace_lines: list[str] = []

    conv: list[dict[str, str]] = [{"role": "system", "content": sys_text}]
    conv.extend(list(messages))

    for step in range(max_steps):
        try:
            raw = client.chat(conv)
        except OllamaClientError as e:
            return False, str(e)

        trace_lines.append(f"【第 {step + 1} 步模型输出】\n{raw.strip()}")
        conv.append({"role": "assistant", "content": raw})

        try:
            obj = _extract_json_object(raw)
        except (json.JSONDecodeError, ValueError) as e:
            err = f"模型未输出合法 JSON，已停止。{e!s}"
            conv.append({"role": "user", "content": f"系统: {err}"})
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"系统: {err}"})
            return False, "\n\n".join(trace_lines) + f"\n\n{err}"

        args = obj.get("args") if isinstance(obj.get("args"), dict) else {}
        action = str(obj.get("action", "")).strip().lower()

        if action == "finish":
            ans = str((args or {}).get("answer", "")).strip()
            if not ans:
                ans = str(obj.get("thought", "")).strip() or "(空回答)"
            messages.append({"role": "assistant", "content": ans})
            trace_lines.append(f"【最终回答】\n{ans}")
            return True, "\n\n".join(trace_lines)

        try:
            obs = dispatch_tool(workspace, action, args)
        except ToolError as e:
            obs = f"工具错误: {e!s}"

        obs_msg = f"观察结果（第 {step + 1} 步）:\n{obs}"
        trace_lines.append(obs_msg)
        conv.append({"role": "user", "content": obs_msg})
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": obs_msg})

    tail = f"\n\n已达到最大步数 {max_steps}，未收到 finish。"
    return False, "\n\n".join(trace_lines) + tail
