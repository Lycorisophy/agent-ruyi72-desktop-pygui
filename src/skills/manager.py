"""
技能管理器

管理技能执行和生命周期
"""

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from src.skills.base import Skill, SkillResult, ScriptSkill
from src.skills.registry import SkillRegistry
from src.skills.builtin import BUILTIN_SKILLS
from src.logger import get_logger

logger = get_logger(__name__)


class SkillManager:
    """
    技能管理器
    
    统一管理技能注册和执行
    """
    
    def __init__(
        self,
        skills_dir: str = "./skills",
        max_execution_time: int = 30,
    ):
        self.skills_dir = Path(skills_dir)
        self.max_execution_time = max_execution_time
        
        # 技能注册表
        self.registry = SkillRegistry()
        
        # 初始化
        self._init()
    
    def _init(self):
        """初始化技能系统"""
        # 注册内置技能
        self.registry.register_builtin_skills()
        
        # 从目录加载自定义技能
        self.registry.load_skills_from_dir(self.skills_dir)
        
        logger.info(f"SkillManager initialized with {len(self.list_skills())} skills")
    
    def list_skills(self) -> list[dict]:
        """列出所有技能"""
        return self.registry.list_skills()
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self.registry.get(name)
    
    async def execute(
        self,
        skill_name: str,
        **params,
    ) -> SkillResult:
        """
        执行技能
        
        Args:
            skill_name: 技能名称
            **params: 技能参数
        
        Returns:
            SkillResult: 执行结果
        """
        skill = self.registry.get(skill_name)
        
        if not skill:
            return SkillResult(
                success=False,
                error=f"Skill not found: {skill_name}",
            )
        
        try:
            logger.info(f"Executing skill: {skill_name}")
            result = await skill.execute(**params)
            logger.info(f"Skill {skill_name} completed: {result.success}")
            return result
            
        except Exception as e:
            logger.error(f"Skill execution error: {e}")
            return SkillResult(
                success=False,
                error=str(e),
            )
    
    async def execute_raw(
        self,
        command: str,
        workspace: str = ".",
        timeout: int = None,
    ) -> SkillResult:
        """
        执行原始命令（用于内置命令支持）
        
        Args:
            command: 命令字符串
            workspace: 工作目录
            timeout: 超时时间
        
        Returns:
            SkillResult: 执行结果
        """
        import time
        timeout = timeout or self.max_execution_time
        start_time = time.time()
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            
            execution_time = time.time() - start_time
            
            return SkillResult(
                success=proc.returncode == 0,
                output=stdout.decode() if stdout else "",
                error=stderr.decode() if stderr else None,
                metadata={
                    "returncode": proc.returncode,
                    "execution_time": execution_time,
                },
            )
            
        except asyncio.TimeoutError:
            return SkillResult(
                success=False,
                error=f"Command timeout ({timeout}s)",
                metadata={"execution_time": time.time() - start_time},
            )
        except Exception as e:
            logger.error(f"Raw command error: {e}")
            return SkillResult(
                success=False,
                error=str(e),
            )
    
    def parse_skill_call(self, text: str) -> Optional[tuple[str, dict]]:
        """
        解析技能调用
        
        Args:
            text: 文本（如 "Read path='/tmp/file.txt'"）
        
        Returns:
            (skill_name, params) 或 None
        """
        # 匹配格式: SkillName param1="value1" param2=123
        pattern = r'^(\w+)\s+(.+)$'
        match = re.match(pattern, text.strip())
        
        if match:
            skill_name = match.group(1)
            params_str = match.group(2)
            
            # 解析参数
            params = self._parse_params(params_str)
            
            return skill_name, params
        
        return None
    
    def _parse_params(self, params_str: str) -> dict:
        """解析参数字符串"""
        params = {}
        
        # 匹配 key=value 或 key="value" 或 key='value'
        patterns = [
            r'(\w+)="([^"]*)"',  # key="value"
            r"(\w+)='([^']*)'",  # key='value'
            r'(\w+)=(\S+)',      # key=value
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, params_str)
            for key, value in matches:
                # 尝试转换类型
                if value.isdigit():
                    value = int(value)
                elif value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                params[key] = value
        
        return params


__all__ = ["SkillManager"]
