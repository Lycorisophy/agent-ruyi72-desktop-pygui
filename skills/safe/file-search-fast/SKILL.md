---
name: file-search-fast
description: |
  快速文件搜索技能。
  功能: 使用Everything或Windows索引快速搜索本地文件。
  触发条件: 用户要求搜索文件、查找文件位置时。
---

# File Search Fast

让AI快速搜索本地文件。

## 功能概述

- **快速搜索**：使用Everything引擎（如果安装）
- **Windows搜索**：使用Windows索引搜索
- **按类型筛选**：支持按文件类型搜索

## 技能使用场景

当用户提到以下内容时使用此技能：
- "搜索xxx文件"
- "找一下xxx"
- "在哪里"

## 搜索示例

```
用户：搜索 报告
AI：[搜索文件]

用户：搜索 .pdf 文件
AI：[搜索PDF文件]
```

## 可用命令

```bash
# 搜索文件
python scripts/search.py "关键词"

# 搜索指定类型
python scripts/search.py "关键词" --type pdf

# 搜索目录
python scripts/search.py "关键词" --path "D:\下载"
```
