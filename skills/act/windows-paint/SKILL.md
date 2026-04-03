---
name: windows-paint
description: |
  🎨 Windows 画图技能，能够打开和使用 Windows 画图程序。
  功能: 打开画图、编辑图片、截图后编辑。
  触发条件: 用户要求"打开画图"、"用画图打开"、"编辑图片"等。
---

# Windows Paint Skill

Windows 画图技能。

## 功能特性

- **打开画图程序**：启动 Windows 自带的画图软件
- **打开图片到画图**：用画图打开指定的图片文件
- **快速截图编辑**：打开截图工具并导入画图编辑

## 触发词

- "打开画图"
- "用画图"
- "画图"
- "windows paint"
- "mspaint"

## 使用示例

```
用户：打开画图
助手：[打开 Windows 画图程序]

用户：用画图打开 C:\Users\LySoY\Pictures\photo.jpg
助手：[用画图打开指定图片]

用户：我想编辑这张图片
助手：[使用画图打开图片]
```

## 技术实现

使用 Python subprocess 调用 Windows 系统命令：
- `start mspaint` - 打开画图程序
- `start mspaint "图片路径"` - 用画图打开指定图片
- `snippingtool` - 打开截图工具

## 依赖要求

- Windows 操作系统
- Python 3.8+

## 使用说明

1. 用户请求打开画图或编辑图片
2. AI 使用 subprocess 启动 mspaint.exe
3. 返回操作结果

## 注意事项

- 只支持 Windows 操作系统
- 图片路径需要是本地电脑的有效路径
- 画图程序需要用户手动操作完成编辑
