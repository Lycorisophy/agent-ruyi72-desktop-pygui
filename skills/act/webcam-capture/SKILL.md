---
name: webcam-capture
description: |
  📷 摄像头拍照技能。
  功能: 调用绿联4K摄像头拍照，支持智能连拍和定时拍照。
  触发条件: 用户说"拍张照"、"打开摄像头"、"让我看看"等。
---

# Webcam Capture - 摄像头调用技能

让AI能够调用摄像头拍照并进行视觉分析。

## 功能概述

- **智能连拍**：根据场景自动决定拍几张
- **可调间隔**：支持0.5秒快速连拍
- **定时拍照**：支持延时拍摄
- **无缝分析**：拍照后自动调用图像理解技能分析

## 技能使用场景

当用户提到以下内容时使用此技能：
- "拍张照"
- "打开摄像头"
- "让我看看"
- "拍照看看"
- "调用摄像头"
- "看看我这边"
- "拍个照片"

## 智能拍照指南（重要！）

### AI决策逻辑

**默认参数**：
- 拍照数量：5张
- 拍摄间隔：0.5秒

**根据场景调整**：

| 场景 | 建议张数 | 建议间隔 | 说明 |
|------|---------|---------|------|
| 常规查看 | 3-5张 | 0.5秒 | 捕捉自然表情 |
| 快速动作 | 5-10张 | 0.3秒 | 捕捉连续动作 |
| 静物/环境 | 1-3张 | 0秒 | 不需要连拍 |
| 需要准备 | 1张 | 3-5秒 | 给用户时间准备 |
| 多人场景 | 5-8张 | 0.5秒 | 捕捉不同角度 |

**示例决策**：
```
用户: 帮我拍张照
AI思考: 常规查看场景，默认5张0.5秒间隔
命令: --burst 5 --interval 0.5

用户: 等等，让我调整下
AI思考: 用户需要准备，增加延时
命令: --burst 1 --delay 5

用户: 看看我现在在干嘛
AI思考: 快速查看当前状态
命令: --burst 3 --interval 0.5
```

## 可用命令

### 基础拍照命令

```bash
# 默认拍照（1张）
python scripts/capture_photo.py

# 智能连拍（5张，0.5秒间隔）- 推荐默认使用
python scripts/capture_photo.py --burst 5 --interval 0.5

# 自定义连拍
python scripts/capture_photo.py --burst 10 --interval 0.3

# 延时拍照（5秒后拍1张）
python scripts/capture_photo.py --delay 5

# 延时连拍（3秒准备 + 3张连拍）
python scripts/capture_photo.py --delay 3 --burst 3 --interval 0.5
```

### 高级参数

```bash
# 指定摄像头设备（1=绿联4K摄像头）
python scripts/capture_photo.py --device 1 --burst 5

# 设置高分辨率
python scripts/capture_photo.py --burst 3 --resolution 1920x1080

# 列出可用摄像头
python scripts/capture_photo.py --list-devices
```

## AI使用指南

### 决策流程

```
1. 理解用户需求
   ├── 常规拍照 → 默认5张0.5秒
   ├── 需要等待 → 添加delay
   ├── 快速动作 → 增加张数缩短间隔
   └── 静物/简单 → 1-3张即可

2. 构造命令
   └── python capture_photo.py --burst X --interval Y --delay Z

3. 执行并告知用户
   └── "📸 正在拍照..." → "完成！共拍摄X张照片"

4. 分析照片
   └── 调用 image-understanding 技能分析
```

### 实际对话示例

```
用户: MIKU，拍张照看看
AI: [思考] 常规查看，默认连拍5张
     执行: python scripts/capture_photo.py --burst 5 --interval 0.5 --device 1
     📸 拍照成功！连拍5张，每张间隔0.5秒
     照片保存在: ~/.ruyi72/workspace/memory/webcam-capture/
     现在帮你分析一下？

用户: 好
AI: [分析照片]
     照片显示你正在...（详细描述）

---

用户: 等等，我先整理下
AI: [思考] 用户需要准备时间
     执行: python scripts/capture_photo.py --burst 1 --delay 5 --device 1
     📸 好的，5秒后拍照，准备好了吗？

---

用户: 看看我现在在干嘛
AI: [思考] 快速连拍捕捉当前动作
     执行: python scripts/capture_photo.py --burst 5 --interval 0.3 --device 1
     📸 连拍5张，捕捉你的动作中...
```

## 照片保存位置

```
~/.ruyi72/workspace/memory/webcam-capture/
├── photo_20260318_143000.jpg     # 单张
├── photo_20260318_143010_b1.jpg  # 连拍第1张
├── photo_20260318_143010_b2.jpg  # 连拍第2张
└── ...
```

## 技术实现

### 摄像头配置
- 设备1: 绿联4K摄像头（默认）
- 设备0: 内置摄像头/AMD摄像头

### 调用方式
- **opencv-python-headless**：无窗口计算机视觉库
- **directshow**：Windows视频捕获驱动

## 依赖安装

```bash
pip install opencv-python-headless pillow numpy
```

## 注意事项

- **推荐默认使用 `--burst 5 --interval 0.5`**
- 绿联4K摄像头是设备1
- 连拍可捕捉更自然的瞬间表情
- 照片会自动保存到memory目录
