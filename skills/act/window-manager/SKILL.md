---
name: window-manager
description: |
  窗口管理技能。
  功能: 列出窗口、切换窗口、最小化最大化关闭窗口。
  触发条件: 用户要求管理窗口、切换应用时。
---

# Window Manager

让AI管理窗口，包括列出、切换、最小化最大化窗口。

## 功能概述

- **列出窗口**：显示所有打开的窗口
- **切换窗口**：快速切换到指定应用
- **窗口控制**：最小化、最大化、关闭窗口

## 技能使用场景

当用户提到以下内容时使用此技能：
- "列出所有窗口"
- "切换到微信"
- "最小化当前窗口"
- "关闭这个窗口"

## 可用命令

```bash
# 列出所有窗口
python scripts/window_manager.py --list

# 切换到指定窗口
python scripts/window_manager.py --switch "窗口标题"

# 最小化窗口
python scripts/window_manager.py --minimize "窗口标题"

# 最大化窗口
python scripts/window_manager.py --maximize "窗口标题"

# 关闭窗口
python scripts/window_manager.py --close "窗口标题"
```
