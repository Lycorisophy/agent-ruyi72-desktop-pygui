---
name: hot-news
description: |
  热点新闻技能。
  功能: 获取今日热点新闻、科技新闻、自定义关键词搜索。
  触发条件: 用户询问新闻、热搜或要求搜索新闻时。
---

# Hot News

让AI获取今日热点新闻。

## 功能概述

- **今日热点**：获取微博/知乎等平台热搜
- **科技新闻**：获取科技领域新闻
- **自定义搜索**：搜索特定关键词新闻

## 技能使用场景

当用户提到以下内容时使用此技能：
- "有什么新闻"
- "今日热搜"
- "科技新闻"
- "搜索xxx新闻"

## 可用命令

```bash
# 今日热点
python scripts/news.py --hot

# 科技新闻
python scripts/news.py --tech

# 搜索新闻
python scripts/news.py --search "关键词"
```
