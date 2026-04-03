---
name: quick-commands
description: |
  快捷命令技能。
  功能: 自定义快捷命令，一键执行复杂操作。
  触发条件: 用户要求添加、执行、列出或删除快捷命令时。
---

# Quick Commands

自定义快捷命令，一键执行复杂操作。

## 功能概述

- **定义快捷命令**：创建自定义命令
- **执行命令**：快速执行已保存的命令
- **命令列表**：查看所有快捷命令

## 技能使用场景

当用户提到以下内容时使用此技能：
- "添加快捷命令"
- "执行xxx命令"
- "列出所有命令"
- "删除命令"

## 可用命令

```bash
# 添加命令
python scripts/commands.py --add "hello" "echo hello"

# 执行命令
python scripts/commands.py --run hello

# 列出命令
python scripts/commands.py --list

# 删除命令
python scripts/commands.py --delete hello
```
