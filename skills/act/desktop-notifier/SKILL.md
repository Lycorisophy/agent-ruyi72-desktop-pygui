---
name: desktop-notifier
description: |
  🔔 桌面通知技能。
  功能: 发送Windows系统通知，支持即时通知和定时提醒。
  触发条件: 用户要求"通知我"、"提醒我"时。
---

# Desktop Notifier

让AI能够发送Windows系统通知，支持即时通知和定时提醒。

## 功能概述

- **即时通知**：AI可以立即发送系统通知给用户
- **定时提醒**：支持设置定时提醒，到时自动发送通知
- **健康提醒**：内置喝水、运动等健康提醒模板
- **持久化**：提醒记录保存在本地，重启后不丢失

## 技能使用场景

当用户提到以下内容时使用此技能：
- "提醒我喝水"
- "一小时后提醒我开会"
- "每天早上9点提醒我锻炼"
- "发送通知"
- "查看所有提醒"
- "取消某个提醒"

## 可用命令

### 1. 发送即时通知
```
python scripts/send_notification.py --title "标题" --message "内容"
```

### 2. 发送健康提醒
```
python scripts/send_notification.py --health-type drink_water
python scripts/send_notification.py --health-type exercise
python scripts/send_notification.py --health-type rest
python scripts/send_notification.py --health-type stand
```

### 3. 定时通知
```
python scripts/send_notification.py --title "标题" --message "内容" --schedule "in 30 minutes"
python scripts/send_notification.py --title "标题" --message "内容" --schedule "at 14:30"
```

### 4. 查看通知列表
```
python scripts/list_notifications.py
python scripts/list_notifications.py --status pending
python scripts/list_notifications.py --json
```

### 5. 取消通知
```
python scripts/cancel_notification.py --id 1
```

## 通知类型模板

| 类型 | 说明 | 适用场景 |
|-----|------|---------|
| default | 默认通知 | 一般消息 |
| urgent | 紧急通知 | 重要提醒 |
| health | 健康提醒 | 喝水、运动 |
| success | 成功通知 | 任务完成 |

## 健康提醒模板

| 类型 | 标题 | 内容 |
|-----|------|-----|
| drink_water | 喝水时间到！ | 忙碌了很久吧？来喝杯水休息一下哦～💧 |
| exercise | 运动时间到！ | 久坐对身体不好，起来活动一下吧！🏃 |
| rest | 休息一下！ | 眼睛也需要休息，看看远处放松一下吧～👀 |
| stand | 站起来走动！ | 坐太久了对身体不好，站起来走动一下吧！🚶 |

## 数据存储

所有数据保存在本地：
- `~/.ruyi72/workspace/memory/desktop-notifier/notifications.json`
