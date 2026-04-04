"""团队会话：链式多模型 + team_decision_v1 解析（P0，无工具）。"""

from __future__ import annotations

import json
import re
from typing import Any

from src.config import RuyiConfig, TeamConfig
from src.llm.ollama import OllamaClient
from src.llm.prompts import build_system_block


def build_team_roster_block(team: TeamConfig) -> str:
    lines = [
        "【团队模型分工（由用户在配置中填写，所有 Agent 均可见）】",
    ]
    for i, entry in enumerate(team.models, start=1):
        lines.append(f"- A{i}（模型: {entry.model}）：{entry.suitable_for or '（未填写特长说明）'}")
    return "\n".join(lines)


_DECISION_SCHEMA = """
你必须在回复中给出**恰好一个** JSON 对象，表示本轮决策（schema_version 固定为 team_decision_v1）。
可用 Markdown 的 ```json 代码块包裹该 JSON。

字段说明：
- schema_version: 固定 "team_decision_v1"
- action: "complete" | "delegate_full" | "delegate_partial"
- target: 委派时为下一跳 "A{k+1}"，完成时为 null
- done_summary: delegate_partial 时必填（已完成部分摘要）
- handoff: delegate_partial 时必填；delegate_full 可为 null
- user_visible: 可选，默认 false
- final_answer: action 为 complete 时必填（给用户的完整可见回复）
- progress_note: 可选

末位 Agent 仅允许 action=complete 且 target=null。
不要输出 JSON 以外的无关正文，除非放在 progress_note / final_answer 语义所需处；JSON 必须可解析。
"""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text or not text.strip():
        return None
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(t[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _normalize_decision(raw: dict[str, Any], *, slot: int, n_total: int) -> dict[str, Any] | None:
    if raw.get("schema_version") != "team_decision_v1":
        return None
    action = raw.get("action")
    if action not in ("complete", "delegate_full", "delegate_partial"):
        return None
    last = slot >= n_total
    if last:
        if action != "complete":
            return None
        if raw.get("target") not in (None, ""):
            return None
        fa = raw.get("final_answer")
        if not isinstance(fa, str) or not fa.strip():
            return None
        return {
            "action": "complete",
            "target": None,
            "final_answer": fa.strip(),
            "done_summary": raw.get("done_summary"),
            "handoff": raw.get("handoff"),
        }
    if action == "complete":
        fa = raw.get("final_answer")
        if not isinstance(fa, str) or not fa.strip():
            return None
        return {
            "action": "complete",
            "target": None,
            "final_answer": fa.strip(),
        }
    expected_target = f"A{slot + 1}"
    tgt = raw.get("target")
    if tgt != expected_target:
        return None
    if action == "delegate_partial":
        ds = raw.get("done_summary")
        ho = raw.get("handoff")
        if not isinstance(ds, str) or not ds.strip():
            return None
        if not isinstance(ho, str) or not ho.strip():
            return None
        return {
            "action": "delegate_partial",
            "target": expected_target,
            "done_summary": ds.strip(),
            "handoff": ho.strip(),
        }
    if action == "delegate_full":
        return {
            "action": "delegate_full",
            "target": expected_target,
            "handoff": (raw.get("handoff") or "").strip() or None,
        }
    return None


def _slot_system_prompt(
    roster: str,
    *,
    slot: int,
    n_total: int,
) -> str:
    lines = [
        f"当前你是 **A{slot}**，团队共 **{n_total}** 个串联角色（你处于第 {slot} 跳）。",
    ]
    if slot < n_total:
        lines.append(
            f"若非末位：可向下一槽位 **A{slot + 1}** 委派（整包或部分）；禁止跳过槽位。"
        )
    else:
        lines.append("你是**末位**：必须在本轮直接完成用户任务，action 只能为 complete，禁止委派。")
    lines.append(
        "P0 团队模式：不要声称执行了本地命令或读取了文件；仅用文本推理与 JSON 决策回复。"
    )
    role = "\n".join(lines) + "\n\n"
    return roster + "\n\n" + role + _DECISION_SCHEMA


def run_team_turn(
    cfg: RuyiConfig,
    *,
    team_size: int,
    prior_messages: list[dict[str, str]],
    user_text: str,
    memory_extra: str | None = None,
) -> str:
    """
    执行一轮用户消息的团队链式调用，返回最终给用户展示的文本。
    """
    team = cfg.team
    m_count = len(team.models)
    if m_count < 2:
        raise ValueError("配置中 team.models 少于 2 条，无法使用团队模式。")
    if not (2 <= team_size <= min(4, m_count)):
        raise ValueError(
            f"会话 team_size={team_size} 无效，应在 2～{min(4, m_count)} 且不超过已配置模型数 {m_count}。"
        )

    n = team_size
    roster = build_team_roster_block(team)
    client = OllamaClient(cfg.llm)
    user_original = user_text.strip()
    handoff_notes: list[str] = []

    for slot in range(1, n + 1):
        model_name = team.models[slot - 1].model
        slot_sys = _slot_system_prompt(roster, slot=slot, n_total=n)
        system = build_system_block(extra_system=slot_sys)
        if slot == 1 and memory_extra:
            system = system + "\n\n" + memory_extra

        if slot == 1:
            call: list[dict[str, str]] = [{"role": "system", "content": system}]
            for msg in prior_messages:
                r = msg.get("role")
                c = msg.get("content")
                if r in ("user", "assistant") and isinstance(c, str):
                    call.append({"role": r, "content": c})
            call.append({"role": "user", "content": user_original})
        else:
            parts = [f"【原始用户本轮问题】\n{user_original}"]
            if handoff_notes:
                parts.append("【前序交接】\n" + "\n\n".join(handoff_notes))
            if slot < n:
                parts.append(
                    f"请作为 A{slot} 继续处理：若可独立完成则 complete；否则按 JSON 规则委派给 A{slot + 1}。"
                )
            else:
                parts.append(f"请作为 A{slot}（末位）直接完成：仅允许 action=complete。")
            call = [
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(parts)},
            ]

        def call_llm(msgs: list[dict[str, str]]) -> str:
            return client.chat(msgs, model_override=model_name)

        reply = call_llm(call)
        last_reply = reply
        decision = _normalize_decision(_extract_json_object(reply) or {}, slot=slot, n_total=n)

        if decision is None:
            retry_user = (
                "你上一则回复无法解析为合法的 team_decision_v1 JSON。"
                "请**仅**输出一个符合约定的 JSON 对象（可用 ```json 包裹），不要其它说明。"
            )
            call_retry = call + [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": retry_user},
            ]
            reply2 = call_llm(call_retry)
            last_reply = reply2
            decision = _normalize_decision(_extract_json_object(reply2) or {}, slot=slot, n_total=n)

        if decision is None:
            text = last_reply.strip()
            if not text:
                text = "团队链路解析失败：模型未返回合法 team_decision_v1 JSON。"
            return text

        if decision["action"] == "complete":
            return str(decision["final_answer"])

        note_lines = [f"[A{slot} → A{slot + 1}]"]
        if decision["action"] == "delegate_full":
            note_lines.append("委派方式：整包")
            if decision.get("handoff"):
                note_lines.append(f"附言：{decision['handoff']}")
        else:
            note_lines.append(f"已完成：{decision.get('done_summary', '')}")
            note_lines.append(f"交给下一跳：{decision.get('handoff', '')}")
        handoff_notes.append("\n".join(note_lines))

    return "团队链路未正常结束。"
