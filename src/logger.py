"""
如意 Agent 日志模块

使用 Loguru 进行日志管理
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# 日志格式
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

# 日志文件配置
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "ruyi72.log"
LOG_ROTATION = "100 MB"
LOG_RETENTION = "30 days"


def setup_logger(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    console: bool = True,
) -> None:
    """
    配置日志系统
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        console: 是否输出到控制台
    """
    # 移除默认处理器
    logger.remove()
    
    # 控制台输出
    if console:
        logger.add(
            sys.stderr,
            format=LOG_FORMAT,
            level=level,
            colorize=True,
        )
    
    # 文件输出
    if log_file is None:
        log_file = LOG_FILE
    
    # 确保日志目录存在
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_file,
        format=LOG_FORMAT,
        level=level,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="zip",
        encoding="utf-8",
    )
    
    logger.info(f"日志系统初始化完成，日志级别: {level}")


def get_logger(name: Optional[str] = None):
    """
    获取日志记录器
    
    Args:
        name: 模块名称
    
    Returns:
        logger 实例
    """
    if name:
        return logger.bind(name=name)
    return logger


# 初始化默认日志
setup_logger(level="INFO")


__all__ = ["logger", "get_logger", "setup_logger"]
