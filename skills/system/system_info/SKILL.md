# 系统信息技能

## Skill: system_info

获取系统信息

## Description

获取当前系统的基本信息和资源使用情况。

## Parameters

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| info_type | string | 否 | all | 信息类型: all, cpu, memory, disk, os |

## Examples

```
system_info
system_info info_type="memory"
system_info info_type="disk"
```

## Triggers

- 系统信息
- 查看配置
- 资源使用
