---
name: process-manager
description: |
  ⚙️ Windows 系统进程管理技能，查看、搜索、结束进程，获取进程详情。
  功能: 查看进程列表、进程详情、结束进程、搜索进程、进程树显示。
  触发条件: 用户要求"查看进程"、"结束进程"、"搜索进程"、"process list"、"kill process"等。
---

# Process Manager Skill

Windows 系统进程管理技能，提供进程查看和控制功能。

## 功能特性

- **查看进程**：列出所有运行中的进程
- **进程详情**：获取进程 CPU、内存占用信息
- **结束进程**：强制终止指定进程
- **搜索进程**：按名称查找进程
- **进程树**：显示进程父子关系
- **进程过滤**：按 CPU/内存使用率排序

## 触发词

- "查看进程"
- "结束进程"
- "进程管理"
- "process list"
- "kill process"
- "搜索进程"
- "进程详情"
- "CPU 占用"
- "内存占用"

## 使用示例

```
用户：查看所有运行中的进程
助手：[列出进程列表，包含 PID、CPU、内存信息]

用户：结束 chrome 进程
助手：[查找 chrome 进程并终止]

用户：哪个进程占用内存最多
助手：[按内存使用率排序显示进程]

用户：搜索 python 进程
助手：[查找所有 python 进程]

用户：显示进程树
助手：[显示进程的父子关系树]
```

## 技术实现

使用 PowerShell 命令：
- `Get-Process` - 获取进程信息
- `Stop-Process` - 终止进程
- `Where-Object` - 进程过滤和搜索

## 依赖要求

- Python 3.8+
- Windows PowerShell 5.1+
- Windows 10/11 或 Windows Server 2016+

## 安装说明

1. 将此文件夹复制到 OpenClaw skills 目录
2. 确保 Windows 系统已安装 PowerShell
3. 重启 OpenClaw 即可使用

## 注意事项

- 结束系统关键进程可能导致系统不稳定
- 部分进程受保护无法结束
- 建议在操作前确认进程名称和 PID
