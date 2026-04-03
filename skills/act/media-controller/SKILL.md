---
name: media-controller
description: |
  媒体控制技能。
  功能: 获取播放信息、播放控制、上一首下一首。
  触发条件: 用户询问当前播放歌曲或要求切歌时。
---

# Media Controller

让AI能够控制音乐播放器，获取播放信息。

## 功能概述

- **获取播放信息**：当前歌曲、艺术家、专辑
- **播放控制**：播放、暂停、上一首、下一首
- **播放状态**：获取当前是否正在播放

## 技能使用场景

当用户提到以下内容时使用此技能：
- "现在播放什么歌"
- "切歌"
- "暂停/播放"
- "下一首"
- "上一首"
- "播放状态"

## 可用命令

```bash
# 获取当前播放信息
python scripts/media_control.py --status

# 播放
python scripts/media_control.py --play

# 暂停
python scripts/media_control.py --pause

# 切换播放/暂停
python scripts/media_control.py --toggle

# 下一首
python scripts/media_control.py --next

# 上一首
python scripts/media_control.py --previous

# JSON输出
python scripts/media_control.py --json
```

## 输出示例

```
===== 播放信息 =====
状态: 正在播放
歌曲: 歌曲名称
艺术家: 歌手名称
专辑: 专辑名称
```

## 技术实现

使用Windows Media API通过PowerShell获取系统媒体信息：
- Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager
- 支持Spotify、网易云音乐、QQ音乐等所有支持系统媒体控制的播放器

## 注意事项

- 仅支持Windows 10/11系统
- 需要播放器支持系统媒体传输控制(SMTC)
- 部分播放器可能不完全支持所有功能
