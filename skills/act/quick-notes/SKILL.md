---
name: quick-notes
description: |
  快速笔记技能。
  功能: 快速保存笔记、查看笔记、搜索笔记、删除笔记。
  触发条件: 用户要求记录笔记、保存想法或查看笔记时。
---

# Quick Notes

让AI快速记录笔记和想法。

## 功能概述

- **添加笔记**：快速保存文字笔记
- **查看笔记**：列出所有笔记
- **搜索笔记**：按关键词搜索
- **删除笔记**：删除指定笔记

## 技能使用场景

当用户提到以下内容时使用此技能：
- "记一下xxx"
- "保存这个想法"
- "查看笔记"
- "搜索xxx笔记"

## 可用命令

```bash
# 添加笔记
python scripts/notes.py --add "笔记内容"

# 查看所有笔记
python scripts/notes.py --list

# 搜索笔记
python scripts/notes.py --search "关键词"

# 删除笔记
python scripts/notes.py --delete 1
```
