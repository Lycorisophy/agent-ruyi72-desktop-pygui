"""
记忆摄入脚本
从对话中提取重要信息并存储

用法:
    python memory_ingestion.py "对话内容"
    python memory_ingestion.py --file path/to/conversation.txt
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

# 配置路径
WORKSPACE = Path.home() / ".openclaw" / "workspace"
BUFFER_FILE = WORKSPACE / "memory" / "SHORT_TERM" / "buffer.md"
FACTS_FILE = WORKSPACE / "memory" / "LONG_TERM" / "facts" / "personal_info.md"

def extract_memories(conversation: str) -> list:
    """
    从对话中提取记忆
    这里可以接入AI模型进行智能提取
    当前为基于规则的简单实现
    """
    memories = []
    lines = conversation.split("\n")
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        # 简化版：逐行分析
        # 实际使用时应该用LLM来提取
        memory = analyze_line(line)
        if memory:
            memories.append(memory)
    
    return memories

def analyze_line(line: str) -> dict:
    """
    简单分析一行对话，提取记忆
    """
    # 简化实现
    memory = {
        "type": "event",
        "content": line,
        "tags": [],
        "importance": 5,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 关键词检测（简化版）
    keywords_fact = ["我叫", "我是", "生日", "住在", "喜欢", "不喜欢", "不能吃"]
    keywords_event = ["吃了", "去了", "买了", "看了", "玩了", "做了"]
    keywords_emotion = ["开心", "难过", "生气", "高兴", "生气", "舒服", "不舒服"]
    
    for kw in keywords_fact:
        if kw in line:
            memory["type"] = "fact"
            memory["importance"] = 7
            memory["tags"].append("个人信息")
            break
    
    for kw in keywords_emotion:
        if kw in line:
            memory["type"] = "emotion"
            memory["tags"].append("情绪")
            break
    
    return memory

def save_to_buffer(memories: list):
    """保存到短期记忆缓冲区"""
    with open(BUFFER_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## 记忆片段 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for mem in memories:
            f.write(f"- [{mem['type']}] {mem['content']} (重要性:{mem['importance']})\n")

def save_to_facts(memories: list):
    """保存重要事实到长期记忆"""
    facts = [m for m in memories if m["type"] == "fact" and m["importance"] >= 7]
    if not facts:
        return
    
    # 追加到facts文件
    with open(FACTS_FILE, "a", encoding="utf-8") as f:
        for fact in facts:
            f.write(f"\n## FACT_{datetime.now().strftime('%Y%m%d%H%M%S')}\n")
            f.write(f"- 内容: {fact['content']}\n")
            f.write(f"- 来源: 对话提取\n")
            f.write(f"- 时间: {fact['timestamp']}\n")
            f.write(f"- 标签: {', '.join(fact['tags'])}\n")

def main():
    if len(sys.argv) < 2:
        print("用法: python memory_ingestion.py <对话内容>")
        print("   或: python memory_ingestion.py --file <文件路径>")
        sys.exit(1)
    
    if sys.argv[1] == "--file":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            conversation = f.read()
    else:
        conversation = " ".join(sys.argv[1:])
    
    print(f"[记忆摄入] 分析对话...")
    memories = extract_memories(conversation)
    
    print(f"[记忆摄入] 提取到 {len(memories)} 条记忆")
    
    # 保存到缓冲区
    save_to_buffer(memories)
    print(f"[记忆摄入] 已保存到 {BUFFER_FILE}")
    
    # 保存重要事实
    save_to_facts(memories)
    print(f"[记忆摄入] 重要事实已归档")
    
    # 输出结果
    print("\n提取的记忆:")
    for mem in memories:
        print(f"  [{mem['type']}] {mem['content'][:50]}... (重要性:{mem['importance']})")

if __name__ == "__main__":
    main()
