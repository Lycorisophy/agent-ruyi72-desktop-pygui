"""最小对话会话：维护消息列表并调用 LLM。"""

from __future__ import annotations

from src.config import LLMConfig
from src.llm.ollama import OllamaClient, OllamaClientError


class AgentSession:
    def __init__(self, llm_cfg: LLMConfig) -> None:
        self._llm_cfg = llm_cfg
        self._messages: list[dict[str, str]] = []

    @property
    def messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def send_message(self, text: str) -> tuple[bool, str]:
        text = (text or "").strip()
        if not text:
            return False, "请输入内容。"

        self._messages.append({"role": "user", "content": text})
        try:
            reply = OllamaClient(self._llm_cfg).chat(self._messages)
        except OllamaClientError as e:
            return False, str(e)

        self._messages.append({"role": "assistant", "content": reply})
        return True, reply
