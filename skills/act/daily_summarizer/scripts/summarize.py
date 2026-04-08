"""
每日总结脚本
每天凌晨自动总结前一天的对话

用法:
    python summarize.py                  # 总结昨天
    python summarize.py --date 2026-03-17  # 总结指定日期
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# 配置路径
WORKSPACE = Path.home() / ".ruyi72" / "workspace"
MEMORY_DIR = WORKSPACE / "memory"
SHORT_TERM_DIR = MEMORY_DIR / "SHORT_TERM"
LONG_TERM_DIR = MEMORY_DIR / "LONG_TERM"
EPISODIC_DIR = LONG_TERM_DIR / "episodic"

def get_yesterday():
    """获取昨天的日期"""
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def read_daily_log(date: str) -> str:
    """读取指定日期的日志"""
    log_file = MEMORY_DIR / f"{date}.md"
    
    if not log_file.exists():
        # 尝试在memory目录查找
        alt_file = SHORT_TERM_DIR / f"{date}.md"
        if alt_file.exists():
            with open(alt_file, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    
    with open(log_file, "r", encoding="utf-8") as f:
        return f.read()

def generate_summary(date: str, content: str) -> str:
    """
    生成每日总结
    这里应该接入LLM进行智能总结
    当前为基于规则的结构化提取
    """
    if not content:
        return f"# 每日总结 - {date}\n\n## 概述\n这一天没有对话记录。\n"
    
    summary = f"# 每日总结 - {date}\n\n"
    
    # 简化版分析
    lines = content.split("\n")
    
    events = []
    facts = []
    emotions = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        if "[event]" in line.lower():
            events.append(line)
        elif "[fact]" in line.lower():
            facts.append(line)
        elif "[emotion]" in line.lower():
            emotions.append(line)
    
    # 生成概述
    if events or facts:
        summary += f"## 概述\n今天共有 {len(events)} 个事件记录，{len(facts)} 条新事实。\n\n"
    else:
        summary += "## 概述\n这一天有对话但没有提取到特定事件。\n\n"
    
    # 重要事件
    if events:
        summary += "## 重要事件\n"
        for e in events[:5]:  # 最多5个
            summary += f"- {e}\n"
        summary += "\n"
    
    # 事实更新
    if facts:
        summary += "## 事实更新\n"
        for f in facts:
            summary += f"- {f}\n"
        summary += "\n"
    
    # 情感轨迹
    if emotions:
        summary += "## 情感轨迹\n"
        emotion_text = "、".join([e.split("]")[1].split("(")[0] if "]" in e else e for e in emotions[:3]])
        summary += f"用户表达了: {emotion_text}\n\n"
    
    # 明日关注
    summary += "## 明日关注\n"
    summary += "- 跟进今天提到的重要事项\n"
    summary += "- 关注用户状态变化\n"
    
    summary += f"\n---\n*由每日总结技能自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
    
    return summary

def save_summary(date: str, summary: str):
    """保存总结到情景记忆目录"""
    # 创建月份子目录
    month_dir = EPISODIC_DIR / date[:7]  # e.g., 2026-03
    month_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = month_dir / f"{date}.md"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary)
    
    print(f"[每日总结] 已保存到: {output_file}")

def clear_buffer():
    """清理短期记忆缓冲区"""
    buffer_file = SHORT_TERM_DIR / "buffer.md"
    if buffer_file.exists():
        # 只保留最近的内容
        with open(buffer_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split("\n")
        # 保留最后20行
        keep_lines = lines[-20:] if len(lines) > 20 else lines
        
        with open(buffer_file, "w", encoding="utf-8") as f:
            f.write("\n".join(keep_lines))
        
        print(f"[每日总结] 已清理缓冲区，保留最近 {len(keep_lines)} 行")

def main():
    date = get_yesterday()
    
    # 解析参数
    for i, arg in enumerate(sys.argv):
        if arg == "--date" and i + 1 < len(sys.argv):
            date = sys.argv[i + 1]
    
    print(f"[每日总结] 正在总结: {date}")
    
    # 读取日志
    content = read_daily_log(date)
    
    # 生成总结
    summary = generate_summary(date, content)
    
    # 保存
    save_summary(date, summary)
    
    # 清理缓冲区
    clear_buffer()
    
    print(f"[每日总结] 完成!")
    print("\n" + summary)

if __name__ == "__main__":
    main()
