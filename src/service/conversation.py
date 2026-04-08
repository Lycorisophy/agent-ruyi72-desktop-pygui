"""多会话编排：对话 / ReAct、本地持久化。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agent.action_card import (
    split_reply_action_card,
    supersede_pending_cards,
    utc_now_iso,
)
from src.agent.memory_tools import build_memory_bootstrap_block
from src.agent.persona_runtime import CHECKPOINT_NAME, PersonaRuntime
from src.agent.react import run_react
from src.agent.team_turn import run_team_turn
from src.config import LLMConfig, PersonaConfig, RuyiConfig
from src.llm.ollama import OllamaClient, OllamaClientError
from src.llm.prompts import action_card_system_hint, build_system_block
from src.skills.loader import build_safe_skills_prompt, get_registry
from src.storage.session_store import Mode, SessionMeta, SessionStore


def resolve_sessions_root(cfg: RuyiConfig) -> Path:
    s = (cfg.storage.sessions_root or "").strip()
    if s:
        return Path(s).expanduser().resolve()
    return (Path.home() / ".ruyi72" / "sessions").resolve()


class ConversationService:
    def __init__(self, cfg: RuyiConfig, store: SessionStore, *, react_default_steps: int) -> None:
        self._cfg = cfg
        self._llm = cfg.llm
        self._store = store
        self._react_default = react_default_steps
        self._active_id: str | None = None
        self._messages: list[dict[str, Any]] = []
        self._meta: SessionMeta | None = None
        self._memory_bootstrap_pending = False
        self._persona_emit: Any = None
        self._persona_rt: PersonaRuntime | None = None

    def set_persona_emit(self, fn: Any) -> None:
        """由 app.Api 注入：把拟人事件推到前端（如 pywebview evaluate_js）。"""
        self._persona_emit = fn

    def llm_config(self) -> LLMConfig:
        return self._llm

    def persona_config(self) -> PersonaConfig:
        return self._cfg.persona

    def active_session_id(self) -> str | None:
        return self._active_id

    def session_path_for(self, session_id: str) -> Path:
        return self._store.root / session_id

    def messages_snapshot(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def messages_for_llm(self) -> list[dict[str, str]]:
        """传给 LLM 时仅保留 role + content，避免携带 card 等 UI 字段。"""
        return [
            {"role": str(m.get("role") or "user"), "content": str(m.get("content") or "")}
            for m in self._messages
        ]

    def consume_memory_bootstrap_for_persona(self) -> str:
        if self._memory_bootstrap_pending:
            self._memory_bootstrap_pending = False
            return build_memory_bootstrap_block()
        return ""

    def build_proactive_nudge_message(self) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "你是贴心助手。用户一段时间没有发消息。请生成一句简短、自然、"
                    "不过分打扰的承接或关心，不超过 50 字；不要罗列多个问题。"
                ),
            },
            {"role": "user", "content": "只输出这一句话。"},
        ]

    def _try_skill_load(self, text: str) -> tuple[bool, str, bool]:
        skill_name = text.split(":", 1)[1].strip()
        if not skill_name:
            return False, "技能名称为空，例如：加载技能: deep-research", True
        reg = get_registry()
        sm = reg.get_by_name(skill_name)
        if sm is None:
            return (
                False,
                f"未找到名为 {skill_name!r} 的技能，请确认 name 是否与 SKILL.md 头部一致。",
                True,
            )
        doc = reg.read_full(sm)
        if sm.level >= 2:
            prefix = (
                f"技能 {sm.name} 属于 warn_act(2) 高危技能：可能涉及磁盘/进程/服务/云盘/数据库/剪贴板等敏感操作。\n"
                f"在据此执行真实操作前，请你先向用户解释风险，并等待用户在对话中明确确认，例如：「我确认使用 {sm.name} 技能 执行 XXX」。\n\n"
            )
            return True, prefix + doc, False
        return True, doc, False

    def _stop_persona(self) -> None:
        if self._persona_rt:
            self._persona_rt.shutdown()
            self._persona_rt = None

    def _ensure_persona(self) -> PersonaRuntime:
        if self._persona_rt is None:

            def emit(evt: dict) -> None:
                if self._persona_emit:
                    self._persona_emit(evt)

            self._persona_rt = PersonaRuntime(self, emit=emit)
        return self._persona_rt

    def _sync_persona_runtime(self) -> None:
        self._stop_persona()
        if (
            self._meta is not None
            and self._meta.mode == "persona"
            and self._meta.session_variant == "standard"
        ):
            self._ensure_persona().start()

    def persona_prepare_turn(self, text: str) -> bool:
        assert self._active_id is not None and self._meta is not None
        ws = (self._meta.workspace or "").strip()
        if not ws:
            return False
        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return False
        self._messages.append({"role": "user", "content": text})
        self._store.save_messages(self._active_id, self._messages)
        return True

    def persona_append_assistant(self, content: str) -> None:
        assert self._active_id is not None
        self._messages.append({"role": "assistant", "content": content})
        self._store.save_messages(self._active_id, self._messages)
        self._meta, _ = self._store.load(self._active_id)

    def persona_send(self, text: str) -> dict:
        self.ensure_session()
        assert self._active_id is not None and self._meta is not None
        t = (text or "").strip()
        if not t:
            return {"ok": False, "error": "请输入内容。", "sync": True}
        if self._meta.session_variant == "team":
            return {"ok": False, "error": "团队会话不支持拟人模式。", "sync": True}
        if self._meta.mode != "persona":
            return {"ok": False, "error": "当前会话不是拟人模式。", "sync": True}
        if t.startswith("加载技能:"):
            ok, msg, ae = self._try_skill_load(t)
            return {"ok": ok, "sync": True, "message": msg, "append_error": ae}
        ws = (self._meta.workspace or "").strip()
        if not ws:
            return {
                "ok": False,
                "sync": True,
                "message": "请先在侧栏或上方设置「工作区」为有效文件夹路径。",
                "append_error": True,
            }
        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return {
                "ok": False,
                "sync": True,
                "message": f"工作区不存在或不是目录: {root}",
                "append_error": True,
            }
        self._ensure_persona().start()
        self._persona_rt.notify_user_activity()
        tid = self._persona_rt.enqueue_user_text(t)
        return {"ok": True, "async": True, "turn_id": tid}

    def persona_interrupt(self) -> dict:
        if self._persona_rt:
            self._persona_rt.interrupt()
        return {"ok": True}

    def persona_resume(self) -> dict:
        self.ensure_session()
        assert self._active_id is not None
        if self._persona_rt:
            self._persona_rt.clear_pause()
        else:
            p = self.session_path_for(self._active_id) / CHECKPOINT_NAME
            if p.is_file():
                import json as _json

                try:
                    data = _json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        data["paused"] = False
                        data["pause_reason"] = ""
                        p.write_text(
                            _json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                except (OSError, _json.JSONDecodeError):
                    pass
        return {"ok": True}

    def persona_pause(self, reason: str = "") -> dict:
        self.ensure_session()
        if self._persona_rt:
            self._persona_rt.set_pause(reason)
        elif self._active_id:
            p = self.session_path_for(self._active_id) / CHECKPOINT_NAME
            import json as _json

            try:
                data: dict = {"paused": True, "pause_reason": reason}
                if p.is_file():
                    cur = _json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(cur, dict):
                        cur.update(data)
                        data = cur
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
        return {"ok": True}

    def ensure_session(self) -> None:
        if self._active_id:
            return
        sessions = self._store.list_sessions()
        if sessions:
            self.open_session(sessions[0].id)
        else:
            m = self._store.create_session(react_max_steps=self._react_default)
            self._active_id = m.id
            self._meta = m
            self._messages = []
            self._memory_bootstrap_pending = True

    def list_sessions(self) -> list[dict]:
        return [m.model_dump() for m in self._store.list_sessions()]

    def search_sessions_text(self, query: str) -> list[dict[str, Any]]:
        return self._store.search_full_text(query or "")

    def create_session(self, title: str | None = None) -> dict:
        m = self._store.create_session(title=title, react_max_steps=self._react_default)
        return self.open_session(m.id)

    def create_team_session(self, team_size: int, title: str | None = None) -> dict:
        m_count = len(self._cfg.team.models)
        if m_count < 2:
            raise ValueError("请先在 ruyi72.yaml 中配置至少 2 条 team.models。")
        cap = min(4, m_count)
        if not (2 <= team_size <= cap):
            raise ValueError(f"团队人数须在 2～{cap} 之间（当前已配置 {m_count} 个模型）。")
        m = self._store.create_team_session(
            team_size,
            title=title,
            react_max_steps=self._react_default,
        )
        return self.open_session(m.id)

    def open_session(self, session_id: str) -> dict:
        self._stop_persona()
        meta, messages = self._store.load(session_id)
        self._active_id = session_id
        self._meta = meta
        self._messages = messages
        self._memory_bootstrap_pending = True
        self._sync_persona_runtime()
        return {"meta": self._meta.model_dump(), "messages": list(self._messages)}

    def get_active(self) -> dict:
        self.ensure_session()
        assert self._meta is not None and self._active_id is not None
        return {"meta": self._meta.model_dump(), "messages": list(self._messages)}

    def update_session(
        self,
        *,
        title: str | None = None,
        workspace: str | None = None,
        mode: str | None = None,
        react_max_steps: int | float | None = None,
    ) -> dict:
        self.ensure_session()
        assert self._active_id is not None
        mode_t: Mode | None = None
        if mode is not None:
            if mode not in ("chat", "react", "persona"):
                raise ValueError("mode 必须是 chat、react 或 persona")
            if self._meta.session_variant == "team" and mode == "react":
                raise ValueError("团队会话不能使用 ReAct 模式。")
            if self._meta.session_variant == "team" and mode == "persona":
                raise ValueError("团队会话不能使用拟人模式。")
            mode_t = mode  # type: ignore[assignment]
        steps: int | None = None
        if react_max_steps is not None:
            steps = int(react_max_steps)
        meta = self._store.update_meta(
            self._active_id,
            title=title,
            workspace=workspace,
            mode=mode_t,
            react_max_steps=steps,
        )
        self._meta = meta
        self._sync_persona_runtime()
        return {"meta": meta.model_dump()}

    def rename_session(self, session_id: str, title: str) -> dict:
        """按 id 更新标题（可为非当前会话）。"""
        self.ensure_session()
        t = (title or "").strip() or "新对话"
        try:
            meta = self._store.update_meta(session_id, title=t)
        except FileNotFoundError:
            return {"ok": False, "error": "会话不存在。"}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if self._active_id == session_id:
            self._meta = meta
            self._sync_persona_runtime()
        return {"ok": True, "meta": meta.model_dump()}

    def delete_session(self, session_id: str) -> dict:
        self.ensure_session()
        assert self._active_id is not None
        if session_id == self._active_id:
            self._stop_persona()
        try:
            self._store.delete_session(session_id)
        except FileNotFoundError:
            return {"ok": False, "error": "会话不存在或已删除。"}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if session_id == self._active_id:
            sessions = self._store.list_sessions()
            if sessions:
                return self.open_session(sessions[0].id)
            m = self._store.create_session(react_max_steps=self._react_default)
            return self.open_session(m.id)
        return {"ok": True}

    def _chat_style_followup_after_card(self, memory_extra: str) -> str | None:
        """在已有历史（含卡片确认 user 行）上走一轮与对话模式相同的 Chat，追加 assistant。"""
        assert self._meta is not None
        ws = (self._meta.workspace or "").strip()
        if not ws:
            return "请先在侧栏或上方设置「工作区」为有效文件夹路径。"
        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return f"工作区不存在或不是目录: {root}"
        skills_prompt = build_safe_skills_prompt()
        extras = [action_card_system_hint()]
        if skills_prompt:
            extras.insert(0, skills_prompt)
        system_block = build_system_block(extra_system="\n\n".join(extras))
        if memory_extra:
            system_block = system_block + "\n\n" + memory_extra
        call_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_block}
        ]
        call_messages.extend(self.messages_for_llm())
        try:
            reply = OllamaClient(self._llm).chat(call_messages)
        except OllamaClientError as e:
            return str(e)
        visible, card = split_reply_action_card(reply)
        content = visible.strip() if visible else ""
        if card is not None:
            if not content:
                content = str(card.get("title") or "").strip() or "请确认下列设置。"
            supersede_pending_cards(self._messages)
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": content,
                "card": card,
            }
        else:
            assistant_msg = {"role": "assistant", "content": content or reply}
        self._messages.append(assistant_msg)
        return None

    def _followup_llm_after_action_card(self) -> str | None:
        """
        卡片确认产生的 user 摘要已写入历史后，自动请求模型下一条回复。
        拟人模式：使用与对话相同的一次 Chat（不走路径异步拟人管道），避免无回复。
        """
        self.ensure_session()
        assert self._active_id is not None and self._meta is not None
        if not self._messages or self._messages[-1].get("role") != "user":
            return None
        user_text = str(self._messages[-1].get("content") or "").strip()
        if not user_text.startswith("（卡片确认）"):
            return None

        memory_extra = ""
        if self._memory_bootstrap_pending:
            memory_extra = build_memory_bootstrap_block()
            self._memory_bootstrap_pending = False

        try:
            if self._meta.session_variant == "team":
                ts = self._meta.team_size
                m_count = len(self._cfg.team.models)
                if ts is None or not (2 <= ts <= 4):
                    return "团队会话元数据无效。"
                if ts > m_count:
                    return f"team.models 仅 {m_count} 条，无法继续团队编排。"
                try:
                    reply = run_team_turn(
                        self._cfg,
                        team_size=ts,
                        prior_messages=list(self._messages[:-1]),
                        user_text=user_text,
                        memory_extra=memory_extra or None,
                    )
                except ValueError as e:
                    self._messages.append({"role": "assistant", "content": str(e)})
                except OllamaClientError as e:
                    self._messages.append({"role": "assistant", "content": str(e)})
                else:
                    self._messages.append({"role": "assistant", "content": reply})
            elif self._meta.mode == "react":
                ws = (self._meta.workspace or "").strip()
                if not ws:
                    return "请先在侧栏或上方设置「工作区」为有效文件夹路径。"
                root = Path(ws).expanduser().resolve()
                if not root.is_dir():
                    return f"工作区不存在或不是目录: {root}"
                ok, _out = run_react(
                    self._llm,
                    self._messages,
                    workspace=str(root),
                    max_steps=self._meta.react_max_steps,
                    memory_bootstrap=memory_extra or None,
                )
                if ok:
                    self._parse_action_card_on_last_assistant(self._messages)
            else:
                err = self._chat_style_followup_after_card(memory_extra)
                if err:
                    return err

            self._store.save_messages(self._active_id, self._messages)
            self._meta, self._messages = self._store.load(self._active_id)
        except OllamaClientError as e:
            return str(e)
        except ValueError as e:
            return str(e)
        return None

    def submit_action_card(
        self,
        card_id: str,
        action: str,
        selected_ids: list[Any] | None = None,
        *,
        from_timeout: bool = False,
    ) -> dict[str, Any]:
        """处理确认卡片：更新 assistant 消息中的 card，并追加一条 user 摘要。"""
        self.ensure_session()
        assert self._active_id is not None
        cid = (card_id or "").strip()
        act = (action or "").strip().lower()
        if act not in ("confirm", "reject"):
            return {"ok": False, "error": "action 须为 confirm 或 reject。"}
        if not cid:
            return {"ok": False, "error": "缺少 card_id。"}
        raw_ids = selected_ids if isinstance(selected_ids, list) else []
        picked = [str(x).strip()[:64] for x in raw_ids if x is not None and str(x).strip()]

        card_ref: dict[str, Any] | None = None
        option_list: list[Any] = []
        for m in self._messages:
            if m.get("role") != "assistant":
                continue
            c = m.get("card")
            if not isinstance(c, dict):
                continue
            if str(c.get("id")) != cid:
                continue
            if c.get("status") != "pending":
                return {"ok": False, "error": "卡片已处理。"}
            card_ref = c
            option_list = c.get("options") if isinstance(c.get("options"), list) else []
            break

        if card_ref is None:
            return {"ok": False, "error": "卡片不存在或已处理。"}

        valid = {
            str(o.get("id"))
            for o in option_list
            if isinstance(o, dict) and o.get("id") is not None
        }
        picked = [x for x in picked if x in valid]
        label_by_id = {
            str(o.get("id")): str(o.get("label") or o.get("id"))
            for o in option_list
            if isinstance(o, dict) and o.get("id") is not None
        }
        labels = [label_by_id.get(i, i) for i in picked]
        joined = ", ".join(labels) if labels else "（无）"

        if act == "reject":
            card_ref["status"] = "rejected"
            card_ref["selected_ids"] = []
            card_ref["resolved_at"] = utc_now_iso()
            card_ref.pop("via", None)
            summary = "（卡片确认）已拒绝。"
        else:
            if from_timeout:
                card_ref["status"] = "expired"
                card_ref["via"] = "timeout"
            else:
                card_ref["status"] = "confirmed"
                card_ref.pop("via", None)
            card_ref["selected_ids"] = picked
            card_ref["resolved_at"] = utc_now_iso()
            if from_timeout:
                summary = f"（卡片确认）已超时自动确认，选用：{joined}。"
            else:
                summary = f"（卡片确认）已确认，选用：{joined}。"

        self._messages.append({"role": "user", "content": summary})
        self._store.save_messages(self._active_id, self._messages)
        self._meta, self._messages = self._store.load(self._active_id)

        followup_error = self._followup_llm_after_action_card()
        return {
            "ok": True,
            "meta": self._meta.model_dump(),
            "messages": list(self._messages),
            "followup_error": followup_error,
        }

    def _parse_action_card_on_last_assistant(self, messages: list[dict[str, Any]]) -> None:
        """从最近一条 assistant 正文中提取 ```action_card```，写入 card 并 supersede 旧 pending。"""
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if m.get("role") != "assistant":
                continue
            c = m.get("content")
            if not isinstance(c, str):
                return
            visible, card = split_reply_action_card(c)
            if card is None:
                return
            content = visible.strip() if visible else ""
            if not content:
                content = str(card.get("title") or "").strip() or "请确认下列设置。"
            supersede_pending_cards(messages)
            messages[i] = {"role": "assistant", "content": content, "card": card}
            return

    def send_message(self, text: str) -> tuple[bool, str, bool]:
        """
        返回 (ok, message, append_error)。
        append_error=True 时前端在刷新后额外展示一条错误气泡（仅对话模式 LLM 失败等未写入历史的情况）。
        """
        self.ensure_session()
        assert self._active_id is not None and self._meta is not None

        text = (text or "").strip()
        if not text:
            return False, "请输入内容。", True

        if self._meta.mode == "persona" and self._meta.session_variant == "standard":
            r = self.persona_send(text)
            if r.get("sync"):
                return r["ok"], r.get("message", ""), r.get("append_error", False)
            return bool(r.get("ok")), "", False

        # 特殊命令：加载技能文档（Ask 模式下的渐进披露）
        if text.startswith("加载技能:"):
            ok, msg, ae = self._try_skill_load(text)
            return ok, msg, ae

        ws = (self._meta.workspace or "").strip()
        if not ws:
            return False, "请先在侧栏或上方设置「工作区」为有效文件夹路径。", True

        root = Path(ws).expanduser().resolve()
        if not root.is_dir():
            return False, f"工作区不存在或不是目录: {root}", True

        memory_extra = ""
        if self._memory_bootstrap_pending:
            memory_extra = build_memory_bootstrap_block()
            self._memory_bootstrap_pending = False

        if self._meta.session_variant == "team":
            ts = self._meta.team_size
            m_count = len(self._cfg.team.models)
            if ts is None or not (2 <= ts <= 4):
                return False, "团队会话元数据无效（缺少 team_size）。", True
            if ts > m_count:
                return (
                    False,
                    f"当前配置的 team.models 仅 {m_count} 条，小于本会话的 team_size={ts}。"
                    "请补充配置或改用标准会话。",
                    True,
                )
            self._messages.append({"role": "user", "content": text})
            try:
                reply = run_team_turn(
                    self._cfg,
                    team_size=ts,
                    prior_messages=list(self._messages[:-1]),
                    user_text=text,
                    memory_extra=memory_extra or None,
                )
            except ValueError as e:
                self._messages.pop()
                return False, str(e), True
            except OllamaClientError as e:
                self._messages.pop()
                return False, str(e), True
            self._messages.append({"role": "assistant", "content": reply})
            self._store.save_messages(self._active_id, self._messages)
            self._meta, _ = self._store.load(self._active_id)
            return True, reply, False

        if self._meta.mode == "chat":
            # 对话模式：在每次调用前临时注入固定 system 提示 + safe 技能目录 + action_card 说明，不写入历史。
            skills_prompt = build_safe_skills_prompt()
            extras = [action_card_system_hint()]
            if skills_prompt:
                extras.insert(0, skills_prompt)
            system_block = build_system_block(extra_system="\n\n".join(extras))
            if memory_extra:
                system_block = system_block + "\n\n" + memory_extra

            call_messages: list[dict[str, str]] = [
                {"role": "system", "content": system_block}
            ]
            call_messages.extend(self.messages_for_llm())
            call_messages.append({"role": "user", "content": text})

            try:
                reply = OllamaClient(self._llm).chat(call_messages)
            except OllamaClientError as e:
                return False, str(e), True

            visible, card = split_reply_action_card(reply)
            content = visible.strip() if visible else ""
            if card is not None:
                if not content:
                    content = str(card.get("title") or "").strip() or "请确认下列设置。"
                supersede_pending_cards(self._messages)
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content,
                    "card": card,
                }
            else:
                assistant_msg = {"role": "assistant", "content": content or reply}

            self._messages.append({"role": "user", "content": text})
            self._messages.append(assistant_msg)
            self._store.save_messages(self._active_id, self._messages)
            self._meta, self._messages = self._store.load(self._active_id)
            return True, reply, False

        # ReAct 模式：历史中先追加用户消息，后续由 run_react 修改 messages 列表。
        self._messages.append({"role": "user", "content": text})
        ok, out = run_react(
            self._llm,
            self._messages,
            workspace=str(root),
            max_steps=self._meta.react_max_steps,
            memory_bootstrap=memory_extra or None,
        )
        if ok:
            self._parse_action_card_on_last_assistant(self._messages)
        self._store.save_messages(self._active_id, self._messages)
        self._meta, _ = self._store.load(self._active_id)
        return ok, out, False
