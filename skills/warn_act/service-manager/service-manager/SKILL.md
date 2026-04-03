---
name: service-manager
description: |
  🔧 Windows 服务管理技能，查看、启动、停止、重启服务，创建定时任务。
  功能: 查看服务列表、服务状态、启动停止重启、服务详情、创建定时任务。
  触发条件: 用户要求"查看服务"、"启动服务"、"停止服务"、"重启服务"、"创建定时任务"、"schtasks"等。
---

# Service Manager Skill

Windows 系统服务管理技能，支持服务操作和定时任务管理。

## 功能特性

- **查看服务**：列出所有 Windows 服务及其状态
- **服务状态**：显示服务运行/停止/暂停状态
- **启动服务**：启动指定服务
- **停止服务**：停止指定服务
- **重启服务**：重启指定服务
- **服务详情**：获取服务的详细配置信息
- **创建定时任务**：使用 schtasks 创建定时任务
- **删除定时任务**：删除已创建的定时任务

## 触发词

- "查看服务"
- "启动服务"
- "停止服务"
- "重启服务"
- "服务管理"
- "service manager"
- "定时任务"
- "创建任务"
- "删除任务"
- "schtasks"

## 使用示例

```
用户：查看所有 Windows 服务
助手：[列出所有服务及其状态]

用户：启动 MySQL 服务
助手：[启动 MySQL 服务并显示结果]

用户：停止某个服务
助手：[停止指定服务]

用户：查看服务状态
助手：[显示服务运行状态]

用户：创建定时任务，每天1点运行脚本
助手：[使用 schtasks 创建定时任务]

用户：删除定时任务
助手：[删除指定的定时任务]
```

## 技术实现

使用 PowerShell 和 schtasks 命令：
- `Get-Service` - 获取服务信息
- `Start-Service/Stop-Service/Restart-Service` - 服务控制
- `schtasks /create` - 创建定时任务
- `schtasks /delete` - 删除定时任务
- `schtasks /query` - 查询定时任务

## 依赖要求

- Python 3.8+
- Windows PowerShell 5.1+
- Windows 10/11 或 Windows Server 2016+

## 安装说明

1. 将此文件夹复制到 OpenClaw skills 目录
2. 确保 Windows 系统已安装 PowerShell
3. 重启 OpenClaw 即可使用

## 注意事项

- 部分系统服务无法停止或重启
- 创建定时任务需要管理员权限
- 任务名称建议使用英文避免编码问题
