---
name: clipboard-manager
description: |
  剪贴板管理技能。
  功能: 读取剪贴板、写入剪贴板、管理剪贴板历史。
  触发条件: 用户要求复制粘贴、读取剪贴板或查看历史时。
---

# Clipboard Manager

让AI管理剪贴板内容，包括读取、写入和历史记录。

## 功能概述

- **读取剪贴板**：获取当前剪贴板内容
- **写入剪贴板**：复制文本到剪贴板
- **剪贴板历史**：保存历史记录，方便查找

## 技能使用场景

当用户提到以下内容时使用此技能：
- "复制xxx到剪贴板"
- "读取剪贴板"
- "剪贴板历史"
- "复制这段文字"

## 可用命令

```bash
# 读取当前剪贴板
python scripts/clipboard.py --read

# 写入剪贴板
python scripts/clipboard.py --write "要复制的文本"

# 查看历史记录
python scripts/clipboard.py --history

# 清除历史
python scripts/clipboard.py --clear
```
