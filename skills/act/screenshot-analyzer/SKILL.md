---
name: screenshot-analyzer
description: |
  🖥️ 截图分析技能。
  功能: 截取屏幕或指定区域，支持全屏、区域、窗口截图。
  触发条件: 用户说"截图"、"截个屏"、"看看屏幕上有什么"时。
---

# Screenshot Analyzer

让AI能够截取屏幕并进行视觉分析。

## 功能概述

- **智能截图**：截取当前屏幕或指定区域
- **截图管理**：列出、清理截图文件
- **无缝分析**：截图后自动调用图像理解技能分析

## 技能使用场景

当用户提到以下内容时使用此技能：
- "截图看看"
- "分析当前屏幕"
- "看看屏幕上有什么"
- "截个图"
- "帮我截屏"

## 可用命令

### 1. 截图命令

```bash
# 截取主屏幕（默认）
python scripts/capture_screen.py

# 截取指定显示器
python scripts/capture_screen.py --monitor 2

# 截取指定区域
python scripts/capture_screen.py --mode region --x 100 --y 100 --width 800 --height 600

# 截取当前活动窗口
python scripts/capture_screen.py --mode window

# 列出所有显示器
python scripts/capture_screen.py --mode list-monitors
```

### 2. 截图管理命令

```bash
# 列出所有截图
python scripts/analyze_screenshot.py --list

# 清理旧截图（保留最新5张）
python scripts/analyze_screenshot.py --cleanup

# 清理旧截图（保留最新10张）
python scripts/analyze_screenshot.py --cleanup --keep 10
```

## 使用流程

1. **用户请求截图** → AI执行 `capture_screen.py`
2. **截图完成** → 告诉用户截图保存位置
3. **用户要求分析** → AI使用 `image-understanding` 技能分析截图

## 实际使用示例

```
用户：帮我截个图看看
AI：[执行截图]
   截图成功！文件保存在: C:\Users\xxx\.openclaw\workspace\memory\screenshot-analyzer\screenshot_20260317_xxx.png
   现在帮你分析一下？

用户：好
AI：[使用image-understanding技能分析截图]
   这张图片显示的是...
```

## 技术实现

### 截图方式
- **全屏截图**：使用mss库截取显示器画面
- **区域截图**：截取指定坐标区域
- **窗口截图**：使用Win32 API截取活动窗口

### 分析方式
- 截图后调用OpenClaw已有的 `image-understanding` 技能进行视觉分析

## 数据存储

截图保存在：
- `~/.openclaw/workspace/memory/screenshot-analyzer/`

## 注意事项

- 首次使用需要安装依赖：`pip install mss pillow`
- Windows 10/11 系统可直接使用
- 建议定期使用 `--cleanup` 清理旧截图
