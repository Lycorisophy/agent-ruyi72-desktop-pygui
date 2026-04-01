"""
如意 Agent 配置管理模块

使用 Pydantic Settings 进行配置管理
支持从 config.yaml 和环境变量加载配置
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class AppConfig(BaseModel):
    """应用配置"""
    name: str = "ruyi72"
    version: str = "1.0.0"
    environment: str = "development"


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "127.0.0.1"
    port: int = 8765
    reload: bool = False


class OllamaConfig(BaseModel):
    """Ollama LLM 配置"""
    base_url: str = "http://localhost:11434"
    model: str = "qwen3.5:35b-a3b-q8_0-nothink"
    timeout: int = 120
    temperature: float = 0.7
    max_tokens: int = 4096
    num_ctx: int = 8192
    num_gpu: int = 1


class SandboxConfig(BaseModel):
    """沙箱配置"""
    enabled: bool = True
    max_execution_time: int = 30
    allowed_commands: list[str] = ["python", "node", "git", "pip", "npm"]
    allowed_paths: list[str] = []


class AgentConfig(BaseModel):
    """Agent 配置"""
    default_mode: str = "general"
    max_iterations: int = 50
    max_cycles: int = 30


class SkillsConfig(BaseModel):
    """技能系统配置"""
    skills_dir: str = "./skills"
    auto_load: bool = True
    enabled_skills: list[str] = []  # 空表示启用所有


class Settings(BaseSettings):
    """主配置类"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )
    
    app: AppConfig = Field(default_factory=AppConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)


def load_yaml_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """从 YAML 文件加载配置"""
    if config_path is None:
        config_path = CONFIG_DIR / "config.yaml"
    
    if not config_path.exists():
        return {}
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache()
def get_settings() -> Settings:
    """获取单例配置实例"""
    yaml_config = load_yaml_config()
    
    settings = Settings()
    
    if yaml_config:
        for section, values in yaml_config.items():
            if hasattr(settings, section) and isinstance(values, dict):
                section_obj = getattr(settings, section)
                for key, value in values.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)
    
    return settings


# 全局配置实例
settings = get_settings()


__all__ = [
    "Settings",
    "settings",
    "get_settings",
    "PROJECT_ROOT",
    "CONFIG_DIR",
]
