"""
Agent 基类

定义 Agent 的基本接口和行为
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from src.logger import get_logger
from src.llm.prompts import get_agent_prompt, get_system_prompt

logger = get_logger(__name__)


class AgentMode(Enum):
    """Agent 模式枚举"""
    GENERAL = "general"
    PLAN = "plan"
    VERIFY = "verify"
    EXPLORE = "explore"
    GUIDE = "guide"


@dataclass
class AgentResponse:
    """Agent 响应"""
    message: str
    success: bool = True
    mode: str = "general"
    tokens_used: Optional[int] = None
    finish_reason: str = "stop"
    metadata: dict = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)


class Agent(ABC):
    """
    Agent 基类
    
    定义所有 Agent 的基本接口
    """
    
    def __init__(
        self,
        mode: AgentMode,
        name: str,
        description: str,
        llm,
        skill_manager,
        max_iterations: int = 50,
    ):
        self.mode = mode
        self.name = name
        self.description = description
        self.llm = llm
        self.skill_manager = skill_manager
        self.max_iterations = max_iterations
        
        # 获取提示词
        self.system_prompt = get_agent_prompt(mode.value)
        self.base_prompt = get_system_prompt()
        
        logger.info(f"Initialized {self.__class__.__name__} in {mode.value} mode")
    
    @abstractmethod
    async def run(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AgentResponse:
        """执行 Agent"""
        pass
    
    @abstractmethod
    async def run_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """流式执行 Agent"""
        pass
    
    def format_skills_description(self) -> str:
        """格式化技能描述"""
        skills = self.skill_manager.list_skills()
        if not skills:
            return "无可用技能"
        
        lines = ["可用技能："]
        for skill in skills:
            lines.append(f"- **{skill['name']}**: {skill['description']}")
        
        return "\n".join(lines)
    
    async def think(self, prompt: str) -> str:
        """调用 LLM 进行思考"""
        response = await self.llm.generate(
            prompt=prompt,
            system=self.base_prompt,
        )
        return response.get("content", "")
    
    async def think_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """流式调用 LLM"""
        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            system=self.base_prompt,
        ):
            yield chunk
    
    def parse_tool_call(self, text: str) -> Optional[tuple[str, dict]]:
        """
        解析工具调用
        
        Args:
            text: LLM 输出文本
        
        Returns:
            (tool_name, parameters) 或 None
        """
        # 匹配 Action: tool_name {"param": "value"}
        pattern = r'Action:\s*(\w+)\s*(\{.*\}|\[.*\])'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            tool_name = match.group(1)
            params_str = match.group(2)
            try:
                params = json.loads(params_str)
                return tool_name, params
            except json.JSONDecodeError:
                return tool_name, {}
        
        return None


class GeneralAgent(Agent):
    """通用 Agent - 处理日常对话和任务"""
    
    def __init__(self, llm, skill_manager, **kwargs):
        super().__init__(
            mode=AgentMode.GENERAL,
            name="如意助手",
            description="通用智能助手，处理日常对话和任务",
            llm=llm,
            skill_manager=skill_manager,
            **kwargs,
        )
    
    async def run(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AgentResponse:
        """执行通用对话"""
        skills_desc = self.format_skills_description()
        
        prompt = f"""{self.system_prompt}

{skills_desc}

用户消息：
{message}
"""
        
        response = await self.think(prompt)
        
        return AgentResponse(
            message=response,
            success=True,
            mode=self.mode.value,
        )
    
    async def run_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """流式执行通用对话"""
        skills_desc = self.format_skills_description()
        
        prompt = f"""{self.system_prompt}

{skills_desc}

用户消息：
{message}
"""
        
        async for chunk in self.think_stream(prompt):
            yield chunk


__all__ = ["Agent", "AgentMode", "AgentResponse", "GeneralAgent"]
