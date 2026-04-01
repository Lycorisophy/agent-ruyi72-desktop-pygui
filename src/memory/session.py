"""
会话记忆模块

管理对话历史和上下文
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json

from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Message:
    """消息"""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = None
    metadata: dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class SessionMemory:
    """
    会话记忆管理器
    
    管理单个会话的消息历史
    """
    
    def __init__(
        self,
        session_id: str,
        max_history: int = 100,
        context_window: int = 10,
    ):
        self.session_id = session_id
        self.max_history = max_history
        self.context_window = context_window
        self.messages: list[Message] = []
        
        logger.info(f"SessionMemory initialized: {session_id}")
    
    def add_user_message(self, content: str, metadata: dict = None):
        """添加用户消息"""
        message = Message(role="user", content=content, metadata=metadata)
        self.messages.append(message)
        self._trim_history()
        logger.debug(f"Added user message to {self.session_id}")
    
    def add_assistant_message(self, content: str, metadata: dict = None):
        """添加助手消息"""
        message = Message(role="assistant", content=content, metadata=metadata)
        self.messages.append(message)
        self._trim_history()
        logger.debug(f"Added assistant message to {self.session_id}")
    
    def add_system_message(self, content: str, metadata: dict = None):
        """添加系统消息"""
        message = Message(role="system", content=content, metadata=metadata)
        self.messages.append(message)
        logger.debug(f"Added system message to {self.session_id}")
    
    def _trim_history(self):
        """修剪历史记录"""
        if len(self.messages) > self.max_history:
            # 保留最近的 max_history 条
            self.messages = self.messages[-self.max_history:]
    
    def get_context(self, include_system: bool = True) -> list[dict]:
        """
        获取上下文
        
        Args:
            include_system: 是否包含系统消息
        
        Returns:
            消息列表
        """
        messages = []
        
        for msg in self.messages:
            if msg.role == "system" and not include_system:
                continue
            messages.append({"role": msg.role, "content": msg.content})
        
        return messages
    
    def get_recent_context(self, n: int = None) -> list[dict]:
        """
        获取最近的上下文
        
        Args:
            n: 消息数量，None 表示 context_window
        
        Returns:
            消息列表
        """
        if n is None:
            n = self.context_window
        
        messages = self.messages[-n:] if n > 0 else self.messages
        
        return [{"role": msg.role, "content": msg.content} for msg in messages]
    
    def get_history(self) -> list[dict]:
        """获取完整历史"""
        return [msg.to_dict() for msg in self.messages]
    
    def clear(self):
        """清空历史"""
        self.messages.clear()
        logger.info(f"Cleared memory for {self.session_id}")
    
    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps({
            "session_id": self.session_id,
            "messages": [msg.to_dict() for msg in self.messages],
        }, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, data: str, **kwargs) -> "SessionMemory":
        """从 JSON 反序列化"""
        obj = json.loads(data)
        session_id = obj["session_id"]
        messages = obj.get("messages", [])
        
        memory = cls(session_id=session_id, **kwargs)
        for msg_data in messages:
            msg = Message(
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                metadata=msg_data.get("metadata", {}),
            )
            memory.messages.append(msg)
        
        return memory


class MemoryStore:
    """
    记忆存储管理器
    
    管理多个会话的记忆
    """
    
    def __init__(self):
        self.sessions: dict[str, SessionMemory] = {}
        logger.info("MemoryStore initialized")
    
    def get_session(self, session_id: str) -> SessionMemory:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionMemory(session_id)
        return self.sessions[session_id]
    
    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
    
    def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        return list(self.sessions.keys())


__all__ = ["SessionMemory", "MemoryStore", "Message"]
