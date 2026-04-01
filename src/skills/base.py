"""
技能基类

定义技能的基本接口
"""

import json
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class SkillParameter:
    """技能参数定义"""
    name: str
    description: str
    type: str = "string"
    required: bool = True
    default: Any = None


class Skill(ABC):
    """
    技能基类
    
    所有技能必须继承此类并实现 execute 方法
    """
    
    name: str = "base_skill"
    description: str = "Base skill"
    category: str = "general"
    parameters: list[SkillParameter] = []
    triggers: list[str] = []
    
    def __init__(self):
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> SkillResult:
        """执行技能"""
        pass
    
    def get_schema(self) -> dict:
        """获取技能 Schema"""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.default is not None:
                properties[param.name]["default"] = param.default
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "triggers": self.triggers,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


class ScriptSkill(Skill):
    """
    脚本技能
    
    通过执行外部脚本实现功能
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        script_path: str,
        script_type: str = "python",  # python, powershell
        category: str = "general",
        parameters: list[SkillParameter] = None,
        triggers: list[str] = None,
        timeout: int = 30,
    ):
        super().__init__()
        self.name = name
        self.description = description
        self.script_path = script_path
        self.script_type = script_type
        self.category = category
        self.parameters = parameters or []
        self.triggers = triggers or []
        self.timeout = timeout
    
    async def execute(self, **kwargs) -> SkillResult:
        """执行脚本技能"""
        import asyncio
        import time
        start_time = time.time()
        
        try:
            # 准备环境变量
            env = {
                "SKILL_PARAMS": json.dumps(kwargs),
                "SKILL_WORKSPACE": kwargs.get("_workspace", "."),
                "SKILL_SESSION_ID": kwargs.get("_session_id", ""),
            }
            
            # 执行脚本
            if self.script_type == "python":
                cmd = ["python", self.script_path]
            elif self.script_type == "powershell":
                cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", self.script_path]
            else:
                cmd = [self.script_path]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            
            # 发送参数
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=json.dumps(kwargs).encode()),
                timeout=self.timeout,
            )
            
            execution_time = time.time() - start_time
            
            if proc.returncode == 0:
                try:
                    result = json.loads(stdout.decode())
                    return SkillResult(
                        success=result.get("success", True),
                        output=result.get("output"),
                        metadata={"execution_time": execution_time, **result.get("metadata", {})},
                    )
                except json.JSONDecodeError:
                    return SkillResult(
                        success=True,
                        output=stdout.decode(),
                        metadata={"execution_time": execution_time},
                    )
            else:
                return SkillResult(
                    success=False,
                    error=stderr.decode() or "Script execution failed",
                    metadata={"execution_time": execution_time, "returncode": proc.returncode},
                )
                
        except asyncio.TimeoutError:
            return SkillResult(
                success=False,
                error=f"Script execution timeout ({self.timeout}s)",
                metadata={"execution_time": time.time() - start_time},
            )
        except Exception as e:
            logger.error(f"Script skill error: {e}")
            return SkillResult(
                success=False,
                error=str(e),
                metadata={"execution_time": time.time() - start_time},
            )


__all__ = ["Skill", "SkillResult", "SkillParameter", "ScriptSkill"]
