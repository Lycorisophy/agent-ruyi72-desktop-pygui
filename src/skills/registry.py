"""
技能注册表

管理所有可用技能
"""

from pathlib import Path
from typing import Optional

import yaml

from src.skills.base import Skill, ScriptSkill, SkillParameter
from src.skills.builtin import BUILTIN_SKILLS
from src.logger import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """
    技能注册表
    
    管理所有可用技能的注册和访问
    """
    
    def __init__(self):
        self.skills: dict[str, Skill] = {}
    
    def register(self, skill: Skill):
        """注册技能"""
        self.skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")
    
    def get(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self.skills.get(name)
    
    def list_skills(self) -> list[dict]:
        """列出所有技能"""
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "parameters": [
                    {
                        "name": p.name,
                        "description": p.description,
                        "type": p.type,
                        "required": p.required,
                        "default": p.default,
                    }
                    for p in skill.parameters
                ],
                "triggers": skill.triggers,
            }
            for skill in self.skills.values()
        ]
    
    def get_by_category(self, category: str) -> list[Skill]:
        """按类别获取技能"""
        return [
            skill for skill in self.skills.values()
            if skill.category == category
        ]
    
    def register_builtin_skills(self):
        """注册内置技能"""
        for skill in BUILTIN_SKILLS:
            self.register(skill)
        logger.info(f"Registered {len(BUILTIN_SKILLS)} built-in skills")
    
    def load_skills_from_dir(self, skills_dir: Path):
        """从目录加载技能"""
        if not skills_dir.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return
        
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            
            # 解析 SKILL.md
            skill_config = self._parse_skill_md(skill_md)
            if not skill_config:
                continue
            
            # 查找脚本文件
            script_files = list(skill_dir.glob("*.py")) + list(skill_dir.glob("*.ps1"))
            if script_files:
                script = script_files[0]
                script_type = "python" if script.suffix == ".py" else "powershell"
                
                skill = ScriptSkill(
                    name=skill_config["name"],
                    description=skill_config["description"],
                    script_path=str(script),
                    script_type=script_type,
                    category=skill_config.get("category", "general"),
                    parameters=skill_config.get("parameters", []),
                    triggers=skill_config.get("triggers", []),
                )
                self.register(skill)
    
    def _parse_skill_md(self, skill_md: Path) -> Optional[dict]:
        """解析 SKILL.md"""
        try:
            content = skill_md.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            name = None
            description = None
            category = "general"
            parameters = []
            triggers = []
            in_params = False
            in_triggers = False
            
            for line in lines:
                line = line.strip()
                
                if line.startswith("## Skill:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("## Description"):
                    in_params = False
                    in_triggers = False
                elif line.startswith("## Parameters"):
                    in_params = True
                    in_triggers = False
                elif line.startswith("## Triggers"):
                    in_params = False
                    in_triggers = True
                elif line.startswith("## "):
                    in_params = False
                    in_triggers = False
                elif line.startswith("# "):
                    # 跳过标题
                    pass
                elif in_params and line.startswith("|"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 5 and "参数名" not in parts[1]:
                        parameters.append(SkillParameter(
                            name=parts[1],
                            description=parts[4] if len(parts) > 4 else "",
                            type="string",
                            required="是" in parts[2],
                            default=None,
                        ))
                elif in_triggers and line.startswith("-"):
                    triggers.append(line[1:].strip())
            
            if name and description:
                return {
                    "name": name,
                    "description": description,
                    "category": category,
                    "parameters": parameters,
                    "triggers": triggers,
                }
            
        except Exception as e:
            logger.error(f"Failed to parse {skill_md}: {e}")
        
        return None


__all__ = ["SkillRegistry"]
