---
name: schedule-manager
description: |
  日程管理技能。
  功能: 添加日程提醒、查看日程、管理纪念日。
  触发条件: 用户要求设置提醒、查看日程或纪念日时。
---

# Schedule Manager

让AI管理日程和纪念日。

## 功能概述

- **添加日程**：设置提醒事项
- **查看日程**：列出今日/本周日程
- **添加纪念日**：记录重要日期
- **查看纪念日**：显示即将到来的纪念日

## 技能使用场景

当用户提到以下内容时使用此技能：
- "提醒我明天开会"
- "今天有什么日程"
- "记录xxx纪念日"
- "查看纪念日"

## 可用命令

```bash
# 添加日程
python scripts/schedule.py --add "事项" --date "2026-03-20"

# 查看今日日程
python scripts/schedule.py --today

# 查看本周日程
python scripts/schedule.py --week

# 添加纪念日
python scripts/schedule.py --add-memory "名称" --date "03-20"

# 查看纪念日
python scripts/schedule.py --memories
```
