---
name: cloud-sync
description: |
  ☁️ 云盘同步技能，支持 OneDrive、Dropbox 等。
  功能: 文件上传、下载、列出、创建文件夹、删除文件、生成分享链接。
  触发条件: 用户要求"上传云端"、"下载云盘"、"cloud sync"等。
---

# Cloud Sync Skill

云盘同步技能，支持 OneDrive、Dropbox 等。

## 功能特性

- **文件上传**：上传文件到云盘
- **文件下载**：从云盘下载文件
- **列出文件**：查看云盘文件列表
- **创建文件夹**：在云盘创建目录
- **删除文件**：删除云盘文件
- **同步状态**：查看同步状态
- **分享链接**：生成文件分享链接

## 触发词

- "上传云端"
- "下载云盘"
- "cloud sync"
- "OneDrive"
- "Dropbox"

## 使用示例

```
用户：将文件上传到 OneDrive
助手：[上传文件并返回链接]

用户：从云盘下载文件
助手：[下载指定文件]

用户：查看云盘文件列表
助手：[列出云盘根目录文件]

用户：生成分享链接
助手：[创建可分享的下载链接]
```

## 支持的平台

- **OneDrive**：微软云盘
- **Dropbox**：Dropbox 云盘
- **Google Drive**：Google 云盘（可选）

## 技术实现

使用各平台的官方 SDK：
- `onedrivesdk` - OneDrive API
- `dropbox` - Dropbox SDK
- `google-api-python-client` - Google Drive API

## 依赖要求

- Python 3.8+
- 对应平台的 SDK（按需安装）

## 安装说明

1. 将此文件夹复制到 如意72 skills 目录
2. 配置各平台的 API 凭证
3. 安装所需 SDK：
   ```
   pip install onedrivesdk dropbox
   ```
4. 重启 如意72 即可使用
