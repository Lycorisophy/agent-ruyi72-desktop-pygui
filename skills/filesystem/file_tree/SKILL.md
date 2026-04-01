# 文件树技能

## Skill: file_tree

显示目录的树形结构

## Description

递归显示指定目录的文件和文件夹结构，便于了解项目结构。

## Parameters

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| path | string | 是 | - | 目录路径 |
| depth | integer | 否 | 3 | 显示深度 |
| exclude | string | 否 | - | 排除的目录（逗号分隔） |

## Examples

```
file_tree path="/project"
file_tree path="/project" depth=2
file_tree path="/project" exclude="node_modules,.git,__pycache__"
```

## Triggers

- 显示目录结构
- 查看文件树
- 列出文件
