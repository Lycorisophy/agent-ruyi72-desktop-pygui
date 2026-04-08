---
name: web-search
description: |
  🌐 使用 DuckDuckGo 进行网页搜索的技能。无需 API Key，直接联网搜索。
  触发条件: 用户要求"联网搜索"、"网上搜索"、"search the web"、"search for"等。
---

# 🌐 Web Search Skill

A simple and powerful web search skill for 如意72. Uses DuckDuckGo to perform web searches and extract results.

## Features

- **Web Search**: Search the web using DuckDuckGo
- **Content Extraction**: Extract titles, URLs, and snippets from search results
- **Fast Response**: Lightweight and quick results
- **No API Key Required**: Works without any external API keys

## Usage

Trigger phrases:
- "search the web"
- "web search"
- "search for"
- "find information about"
- "look up"
- "search online"
- "联网搜索"
- "网上搜索"
- "搜索"

## Examples

```
User: Search for 如意72 documentation
Assistant: [Performs web search and returns results]

User: Find information about Python web scraping
Assistant: [Returns relevant web search results]

User: Look up the latest AI news
Assistant: [Shows latest news from the web]
```

## Requirements

- Python 3.8+
- requests library

## Installation

Dependencies are automatically installed when the skill is loaded.
