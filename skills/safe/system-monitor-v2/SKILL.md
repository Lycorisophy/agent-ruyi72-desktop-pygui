---
name: system-monitor-v2
description: |
  系统监控技能。
  功能: CPU/内存/磁盘/网络/电池监控。
  触发条件: 用户要求查看系统状态、资源使用情况时。
---

# System Monitor V2

让AI能够监控系统状态，包括CPU、内存、磁盘、网络和电池信息。

## 功能概述

- **CPU监控**：使用率、温度、核心数
- **内存监控**：已用/可用内存
- **磁盘监控**：各分区使用情况
- **网络监控**：上传/下载速度
- **电池监控**：电量、充电状态

## 技能使用场景

当用户提到以下内容时使用此技能：
- "查看系统状态"
- "CPU使用率多少"
- "内存还够吗"
- "磁盘空间"
- "网速怎么样"
- "电池还有多少"

## 可用命令

```bash
# 查看完整系统状态
python scripts/get_system_info.py

# 仅查看CPU信息
python scripts/get_system_info.py --cpu

# 仅查看内存信息
python scripts/get_system_info.py --memory

# 仅查看磁盘信息
python scripts/get_system_info.py --disk

# 仅查看网络信息
python scripts/get_system_info.py --network

# 仅查看电池信息
python scripts/get_system_info.py --battery

# 简洁JSON输出
python scripts/get_system_info.py --json
```

## 输出示例

```
===== 系统状态 =====
主机名: DESKTOP-XXXXXX
运行时间: 2天 5小时 32分钟

【CPU】
  使用率: 23%
  核心数: 16

【内存】
  已用: 18.5 GB / 31.9 GB
  使用率: 58%

【磁盘】
  C: 234.5 GB / 475 GB (49%)
  D: 120.0 GB / 500 GB (24%)

【网络】
  下载: 1.2 MB/s
  上传: 0.3 MB/s

【电池】
  电量: 85%
  状态: 充电中
```

## 技术实现

使用Python的 `psutil` 库获取系统信息：
- CPU: psutil.cpu_percent()
- 内存: psutil.virtual_memory()
- 磁盘: psutil.disk_usage()
- 网络: psutil.net_io_counters()
- 电池: psutil.sensors_battery()

## 注意事项

- 首次使用需要安装依赖：`pip install psutil`
- 电池信息在台式机上可能不可用
- 网络速度需要一定时间采样计算
