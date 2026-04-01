"""
Agent 运行器

封装 ReAct 循环执行逻辑
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

from src.agent.base import Agent, AgentMode, AgentResponse
from src.llm.prompts import build_react_prompt, get_agent_prompt, get_system_prompt
from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ReActState:
    """ReAct 状态"""
    task: str
    session_id: Optional[str] = None
    iterations: int = 0
    max_iterations: int = 50
    thought: str = ""
    action: str = ""
    observation: str = ""
    response: str = ""
    history: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"
    
    def add_history(self, thought: str = "", action: str = "", observation: str = ""):
        """添加历史记录"""
        self.history.append({
            "thought": thought,
            "action": action,
            "observation": observation,
        })


class AgentRunner:
    """
    Agent 运行器
    
    封装 ReAct (Reason + Act) 循环执行逻辑
    """
    
    def __init__(
        self,
        llm,
        skill_manager,
        max_iterations: int = 50,
    ):
        self.llm = llm
        self.skill_manager = skill_manager
        self.max_iterations = max_iterations
        
        # 创建各模式 Agent
        self.agents: dict[str, Agent] = {}
        
        logger.info("AgentRunner initialized")
    
    def register_agent(self, mode: str, agent: Agent):
        """注册 Agent"""
        self.agents[mode] = agent
    
    def get_agent(self, mode: AgentMode) -> Agent:
        """获取 Agent"""
        return self.agents.get(mode.value, self.agents.get("general"))
    
    async def run(
        self,
        message: str,
        mode: str = "general",
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AgentResponse:
        """
        运行 Agent
        
        Args:
            message: 用户消息
            mode: Agent 模式
            session_id: 会话 ID
            context: 额外上下文
        
        Returns:
            AgentResponse: 执行结果
        """
        agent = self.get_agent(AgentMode(mode))
        if agent:
            return await agent.run(message, session_id, context)
        
        return AgentResponse(
            message="Agent 模式不存在",
            success=False,
            mode=mode,
        )
    
    async def run_stream(
        self,
        message: str,
        mode: str = "general",
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式运行 Agent
        
        Args:
            message: 用户消息
            mode: Agent 模式
            session_id: 会话 ID
            context: 额外上下文
        
        Yields:
            str: 响应片段
        """
        agent = self.get_agent(AgentMode(mode))
        if agent:
            async for chunk in agent.run_stream(message, session_id, context):
                yield chunk
        else:
            yield "Agent 模式不存在"
    
    async def run_react(
        self,
        task: str,
        session_id: Optional[str] = None,
        max_iterations: Optional[int] = None,
    ) -> ReActState:
        """
        运行 ReAct 循环
        
        Args:
            task: 任务描述
            session_id: 会话 ID
            max_iterations: 最大迭代次数
        
        Returns:
            ReActState: 最终状态
        """
        state = ReActState(
            task=task,
            session_id=session_id,
            max_iterations=max_iterations or self.max_iterations,
        )
        
        system_prompt = get_system_prompt()
        skills_desc = self._format_skills()
        
        logger.info(f"[ReAct] Starting task: {task[:50]}...")
        
        while state.iterations < state.max_iterations:
            state.iterations += 1
            
            # 构建提示词
            history_text = self._format_history(state.history)
            prompt = build_react_prompt(
                task=task,
                tools_description=skills_desc,
                history=history_text,
                system_prompt=system_prompt,
            )
            
            # 调用 LLM
            response = await self.llm.generate(prompt=prompt)
            content = response.get("content", "")
            
            # 解析输出
            thought, action, observation = self._parse_output(content)
            
            if thought:
                state.thought = thought
            
            if action:
                state.action = action
                
                # 解析工具调用
                tool_name, params = self._parse_action(action)
                
                if tool_name:
                    # 执行工具
                    result = await self.skill_manager.execute(tool_name, **params)
                    state.observation = str(result)
                    state.add_history(thought, action, state.observation)
                    
                    # 检查是否完成
                    if self._is_finish(action, state.observation):
                        state.finish_reason = "completed"
                        state.response = self._extract_response(state.observation)
                        break
                else:
                    # 结束
                    state.finish_reason = "stop"
                    state.response = content
                    break
            else:
                # 无需工具调用，直接结束
                state.finish_reason = "stop"
                state.response = content
                break
        
        if state.iterations >= state.max_iterations:
            state.finish_reason = "max_iterations"
            state.response = f"已达到最大迭代次数 ({state.max_iterations})"
        
        logger.info(f"[ReAct] Finished: {state.finish_reason}")
        
        return state
    
    def _format_skills(self) -> str:
        """格式化技能描述"""
        skills = self.skill_manager.list_skills()
        if not skills:
            return "无可用技能"
        
        lines = []
        for skill in skills:
            params = skill.get("parameters", [])
            params_str = ", ".join([p["name"] for p in params]) if params else "无参数"
            lines.append(f"- {skill['name']}({params_str}): {skill['description']}")
        
        return "\n".join(lines)
    
    def _format_history(self, history: list[dict]) -> str:
        """格式化历史记录"""
        if not history:
            return "（无历史记录）"
        
        lines = []
        for i, h in enumerate(history[-5:], 1):  # 只显示最近5条
            lines.append(f"{i}. Thought: {h.get('thought', '')}")
            if h.get('action'):
                lines.append(f"   Action: {h['action']}")
            if h.get('observation'):
                lines.append(f"   Observation: {h['observation'][:200]}...")
        
        return "\n".join(lines)
    
    def _parse_output(self, text: str) -> tuple[str, str, str]:
        """解析 LLM 输出"""
        thought = ""
        action = ""
        
        # 提取 Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=\nAction:|$)', text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
        
        # 提取 Action
        action_match = re.search(r'Action:\s*(.+?)(?=\n|$)', text, re.DOTALL)
        if action_match:
            action = action_match.group(1).strip()
        
        return thought, action, ""
    
    def _parse_action(self, action: str) -> tuple[Optional[str], dict]:
        """解析动作"""
        # 匹配格式: ToolName {"param": "value"}
        pattern = r'^(\w+)\s*(\{.*\}|\(.*\))$'
        match = re.match(pattern, action.strip())
        
        if match:
            tool_name = match.group(1)
            params_str = match.group(2)
            try:
                params = json.loads(params_str.replace("'", '"'))
            except:
                params = {}
            return tool_name, params
        
        return None, {}
    
    def _is_finish(self, action: str, observation: str) -> bool:
        """判断是否完成"""
        # 如果动作包含 finish 或 observation 表示完成
        if "finish" in action.lower():
            return True
        
        # 如果是响应类工具，可能表示完成
        finish_keywords = ["final", "result", "answer", "done"]
        for keyword in finish_keywords:
            if keyword in action.lower():
                return True
        
        return False
    
    def _extract_response(self, text: str) -> str:
        """提取响应内容"""
        # 尝试提取 JSON 中的 response 字段
        try:
            data = json.loads(text)
            return data.get("response", text)
        except:
            return text


__all__ = ["AgentRunner", "ReActState"]
