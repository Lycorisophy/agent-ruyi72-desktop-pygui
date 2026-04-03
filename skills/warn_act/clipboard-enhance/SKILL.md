---
name: clipboard-enhance
description: |
  增强版剪贴板技能。
  功能: 自动监听剪贴板变化、智能识别内容类型、收藏功能。
  触发条件: 用户要求监控剪贴板、收藏内容或查看历史时。
---

# Clipboard Enhance

增强版剪贴板，支持自动监听和智能识别。

## 功能概述

- **自动监听**：监控剪贴板变化
- **智能识别**：自动识别内容类型（文本/链接/代码）
- **收藏功能**：收藏重要内容
- **快速粘贴**：一键粘贴收藏内容

## 技能使用场景

当用户提到以下内容时使用此技能：
- "打开剪贴板监听"
- "查看剪贴板历史"
- "收藏当前内容"
- "粘贴收藏内容"

## 可用命令

```bash
# 查看剪贴板
python scripts/clipboard.py --watch

# 收藏内容
python scripts/clipboard.py --fav "内容"

# 查看收藏
python scripts/clipboard.py --favorites

# 粘贴收藏
python scripts/clipboard.py --paste 1
```
