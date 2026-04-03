---
name: duckduckgo
description: |
  🦆 使用 DuckDuckGo Instant Answers API 进行搜索。无需 API Key，免费使用。
  触发条件: 用户要求"使用 DuckDuckGo"、"ddg 搜索"、"search with duckduckgo"等。
---

# DuckDuckGo Search Skill

A professional web search skill for OpenClaw using DuckDuckGo Instant Answers API.

## 功能特性

- **网页搜索**：使用 DuckDuckGo 搜索引擎进行网页搜索
- **即时答案**：获取 Wikipedia 摘要、定义等即时答案
- **相关搜索**：返回相关的搜索建议
- **无需 API Key**：完全免费，无需任何认证
- **快速响应**：轻量级设计，响应速度快
- **安全搜索**：支持安全搜索过滤

## 触发词

- "search with duckduckgo"
- "duckduckgo search"
- "ddg search"
- "search the web"
- "联网搜索"
- "网上搜索"
- "搜索"

## 使用示例

```
用户：使用 DuckDuckGo 搜索 Python 教程
助手：[返回搜索结果]

用户：ddg 什么是 OpenClaw
助手：[返回即时答案和相关信息]

用户：搜索最新的 AI 新闻
助手：[返回最新的搜索结果]
```

## 输出格式

技能返回格式化的搜索结果，包含：
- 搜索结果数量
- 每个结果的标题、URL 和摘要
- 即时答案（如有）
- 相关搜索建议（如有）

## 技术实现

- 使用 DuckDuckGo Instant Answers API（JSON 格式）
- 支持 Wikipedia 摘要获取
- 支持 Related Topics 提取
- 支持安全搜索设置
- 包含错误处理和超时机制

## 依赖要求

- Python 3.8+
- requests 库（>= 2.28.0）

## 安装说明

1. 将此文件夹复制到 OpenClaw skills 目录
2. 确保已安装 requests 库：`pip install requests`
3. 重启 OpenClaw 即可使用

## 注意事项

- 搜索结果来自 DuckDuckGo 搜索引擎
- 部分查询可能返回即时答案而非网页链接
- 建议使用精确的搜索词以获得更好的结果
