---
name: enhanced-memory
description: |
  💫 增强记忆系统。
  功能: 自动记录重要对话、学习用户习惯、标记重要事件。
  触发条件: 对话中识别到重要信息时自动激活。
---

# Enhanced Memory

增强记忆系统，自动记录重要对话和学习用户习惯。

## 功能概述

- **自动记录**：记录重要对话
- **习惯学习**：记录用户偏好
- **重要事件**：标记重要日期和事件
- **定期总结**：定期总结关系发展

## 技能使用场景

当用户提到以下内容时使用此技能：
- "记住这个"
- "我更喜欢"
- "我的爱好是"
- "查看记忆"

## 可用命令

```bash
# 记录重要信息
python scripts/memory.py --remember "用户喜欢的主题"

# 记录偏好
python script/memory.py --preference "咖啡"

# 查看记忆
python scripts/memory.py --list

# 搜索记忆
python scripts/memory.py --search "关键词"
```
