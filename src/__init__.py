"""
如意 Agent 核心模块

整合 LangChain/LangGraph Agent 系统
"""

__version__ = "1.0.0"
__author__ = "ruyi72"

from src.config import settings, get_settings
from src.logger import get_logger, logger

__all__ = [
    "settings",
    "get_settings",
    "get_logger", 
    "logger",
]
